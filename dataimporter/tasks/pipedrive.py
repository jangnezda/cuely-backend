"""
Pipedrive API integration. At the moment there is no special optimization or work division,
we simply list all deals and store them to database.
"""
from pypedriver import Client
import time
from dateutil.parser import parse as parse_dt
from celery import shared_task

from dataimporter.task_util import should_sync, should_queue, get_utc_timestamp
from dataimporter.models import Document
from dataimporter.algolia.engine import algolia_engine
from social.apps.django_app.default.models import UserSocialAuth
import logging
logger = logging.getLogger(__name__)

PIPEDRIVE_KEYWORDS = {
    'primary': 'pipedrive',
    'secondary': 'deal,opportunity'
}


def start_synchronization(user):
    """ Run initial syncing of deals data in pipedrive. """
    if should_sync(user, 'pipedrive-apikeys', 'tasks.pipedrive'):
        collect_deals.delay(requester=user)
    else:
        logger.info("Pipedrive api key for user '%s' already in use, skipping sync ...", user.username)


@shared_task
@should_queue
def update_synchronization():
    """
    Run sync/update of all users' deals data in pipedrive.
    Should be run periodically to keep the data fresh in our db.
    """
    for us in UserSocialAuth.objects.filter(provider='pipedrive-apikeys'):
        start_synchronization(user=us.user)


@shared_task
def collect_deals(requester):
    pipe_client = init_pipedrive_client(requester)
    stages = {s.id: s.name for s in pipe_client.Stage.fetch_all()}
    users = {u.id: u for u in pipe_client.User.fetch_all()}
    # fallback domain
    org_domain = None

    for deal in pipe_client.Deal.fetch_all():
        if deal.org_id:
            org_domain = deal.org_id.get('cc_email', '').split('@')[0]
        if not org_domain:
            # cannot associate a deal to a company
            logger.debug("Deal '%s' for user '%s' cannot be associated to a company", deal.title, requester.username)
            continue
        db_deal, created = Document.objects.get_or_create(
            pipedrive_deal_id=deal.id,
            requester=requester,
            user_id=requester.id
        )
        if not created and db_deal.last_updated_ts:
            # compare timestamps and skip the deal if it hasn't been updated
            if db_deal.last_updated_ts >= parse_dt(deal.update_time).timestamp():
                logger.debug("Deal '%s' for user '%s' hasn't changed", deal.title, requester.username)
                continue

        db_deal.primary_keywords = PIPEDRIVE_KEYWORDS['primary']
        db_deal.secondary_keywords = PIPEDRIVE_KEYWORDS['secondary']
        db_deal.pipedrive_title = deal.title
        logger.debug("Processing deal '%s' for user '%s'", deal.title, requester.username)
        db_deal.pipedrive_deal_company = deal.org_id.get('name') if deal.org_id else None
        db_deal.pipedrive_deal_value = deal.value
        db_deal.pipedrive_deal_currency = deal.currency
        db_deal.pipedrive_deal_status = deal.status
        db_deal.pipedrive_deal_stage = stages.get(deal.stage_id)
        db_deal.webview_link = 'https://{}.pipedrive.com/deal/{}'.format(org_domain, deal.id)
        db_deal.last_updated = parse_dt(deal.update_time).isoformat() + 'Z'
        db_deal.last_updated_ts = parse_dt(deal.update_time).timestamp()
        db_deal.pipedrive_content = build_deal_content(deal, users, org_domain, pipe_client)
        db_deal.last_synced = get_utc_timestamp()
        db_deal.download_status = Document.READY
        db_deal.save()
        algolia_engine.sync(db_deal, add=created)
        # add sleep of one second to avoid breaking API rate limits
        time.sleep(1)


def build_deal_content(deal, users, org_domain, pipe_client):
    # build content: contacts, users and activities
    content = {
        'contacts': [],
        'users': [],
        'activities': []
    }
    # contacts
    person_name = ''
    if hasattr(deal, 'person_id') and deal.person_id:
        person_name = deal.person_id.get('name')
        content['contacts'].append({
            'name': person_name,
            'email': deal.person_id.get('email', [{}])[0].get('value') or None,
            'url': 'https://{}.pipedrive.com/person/{}'.format(org_domain, deal.person_id.get('value'))
        })
    if deal.participants_count > 1:
        for participant in pipe_client.Participant.fetch_all(filter_id=deal.id):
            if participant.person.get('name') != person_name:
                # person's email can be a string or a list (of dicts)
                email = participant.person.get('email')
                if not isinstance(email, str):
                    email = email[0].get('value') if len(email) > 0 else None
                content['contacts'].append({
                    'name': participant.person.get('name'),
                    'email': email,
                    'url': 'https://{}.pipedrive.com/person/{}'.format(org_domain, participant.id)
                })
    # users ... another Pipedrive api weirdness: sometimes user_id is integer, sometimes dict
    pipe_user = users.get(deal.user_id.get('id', 0) if isinstance(deal.user_id, dict) else deal.user_id)
    if pipe_user:
        content['users'].append({
            'name': pipe_user.name,
            'email': pipe_user.email,
            'icon_url': pipe_user.icon_url,
            'url': 'https://{}.pipedrive.com/users/details/{}'.format(org_domain, pipe_user.id)
        })
        if deal.followers_count > 1:
            for follower in pipe_client.FollowerDeal.fetch_all(filter_id=deal.id):
                if follower.user_id != deal.user_id.get('id'):
                    pipe_user = users.get(follower.user_id)
                    content['users'].append({
                        'name': pipe_user.name,
                        'email': pipe_user.email,
                        'icon_url': pipe_user.icon_url,
                        'url': 'https://{}.pipedrive.com/users/details/{}'.format(org_domain, follower.user_id)
                    })
    # activities
    if deal.done_activities_count > 0:
        for activity in pipe_client.ActivityDeal.fetch_all(filter_id=deal.id):
            if activity.done and activity.marked_as_done_time:
                new_activity = {
                    'subject': activity.subject,
                    'type': activity.type,
                    'contact': activity.person_name,
                    'done_time': parse_dt(activity.marked_as_done_time).isoformat() + 'Z'
                }
                if activity.assigned_to_user_id in users:
                    new_activity['user_name'] = users.get(activity.assigned_to_user_id).name
                content['activities'].insert(0, new_activity)
    return content


def init_pipedrive_client(user):
    social = user.social_auth.filter(provider='pipedrive-apikeys').first()
    if not social:
        return None
    api_key = social.extra_data['api_key']
    return Client(api_key)
