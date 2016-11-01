"""
Intercom API integration. A note about date/time manipulation: python-intercom library which is used for this
integration  naively translates timestamps to dates, therefore we try to access the underlying data directly.
"""
import json
from datetime import datetime, timezone
from celery import shared_task, subtask
from intercom import Event, Intercom, User, Admin, Company, Segment, Conversation, AuthenticationError

from dataimporter.models import Document
import logging
logger = logging.getLogger(__name__)

INTERCOM_KEYWORDS = {
    'primary': 'inter,intercom',
    'secondary': 'user,event,conversation,chat'
}


def start_synchronization(user):
    """ Run initial syncing of user's data in intercom. """
    collect_users.delay(requester=user)


@shared_task
def collect_users(requester):
    """ Fetch all users for this account from Intercom """
    init_intercom(requester)
    for u in User.all():
        db_user, created = Document.objects.get_or_create(
            intercom_user_id=u.id,
            requester=requester,
            user_id=requester.id
        )
        db_user.intercom_email = u.email
        db_user.intercom_title = 'User: {}'.format(u.name)
        db_user.last_updated_ts = u.__dict__.get('last_request_at', u.__dict__.get('updated_at'))
        ddd = datetime.utcfromtimestamp(db_user.last_updated_ts).isoformat() + 'Z'
        logger.info('SINICA %s %s', type(ddd), ddd)
        db_user.last_updated = datetime.utcfromtimestamp(db_user.last_updated_ts).isoformat() + 'Z'
        db_user.webview_link = 'https://app.intercom.io/a/apps/{}/users/{}'.format(u.app_id, u.id)
        db_user.primary_keywords = INTERCOM_KEYWORDS['primary']
        db_user.secondary_keywords = INTERCOM_KEYWORDS['secondary']
        db_user.intercom_session_count = u.session_count
        db_user.intercom_avatar_link = u.avatar.image_url
        db_user.save()
        # can't pickle whole Intercom user object, because it contains helper methods like 'load', 'find', etc.
        # therefore, let's just copy the data we're interested in
        intercom_user = {
            'id': u.id,
            'name': u.name,
            'segments': list(map(lambda x: x.id, u.segments)),
            'companies': list(map(lambda x: x.id, u.companies))
        }
        subtask(process_user).delay(requester, intercom_user, db_user)


@shared_task
def process_user(requester, user, db_user):
    """ Further processing of the user, e.g. load events, companies, conversations """
    init_intercom(requester)
    db_user.download_status = Document.PROCESSING
    db_user.save()

    print ("Processing user '{}' with data: {}".format(user['name'], user))
    # companies ... only use first one, add others when/if necessary
    if user['companies']:
        c = Company.find(id=user['companies'][0])
        if c:
            db_user.intercom_plan = c.plan.get('name')
            db_user.intercom_monthly_spend = c.monthly_spend
    # segments
    segments = []
    for sid in user['segments']:
        s = Segment.find(id=sid)
        if s:
            segments.append(s.name)
    if segments:
        db_user.intercom_segments = ', '.join(segments)
    # build json for content -> events and conversations
    content = {
        'events': [],
        'conversations': []
    }
    for e in Event.find(type='user', intercom_user_id=user['id'], per_page=10).events:
        content['events'].insert(0, {
            'name': e['event_name'],
            'timestamp': e['created_at']
        })

    content['conversations'] = process_conversations(user['id'], user['name'])
    db_user.content = json.dumps(content)
    db_user.last_synced = _get_utc_timestamp()
    db_user.download_status = Document.READY
    db_user.save()


def process_conversations(user_id, user_name):
    result = []
    # cached participants
    users = {user_id: user_name}

    def _find_user(id):
        if id in users:
            return users[id]
        u = fetch_user(id)
        users[id] = u['name']
        return u['name']

    try:
        conversations = Conversation.find(type='user', intercom_user_id=user_id).conversations
        for conversation in conversations:
            # A conversation is an entity composed of two parts: initiating/first message + all replies
            # (it also includes assignments, etc., but we're only interested in comments)
            first_message = conversation.get('conversation_message', {})
            items = [{
                'timestamp': conversation['created_at'],
                'author': _find_user(first_message.get('author', {}).get('id')),
                'body': first_message.get('body', '')
            }]
            parts = Conversation.find(id=conversation['id'])
            for part in parts.conversation_parts:
                items.append({
                    'timestamp': part.__dict__['created_at'],
                    'author': _find_user(part.author.id),
                    'body': part.body
                })
            result.append({
                'subject': conversation.get('conversation_message', {}).get('subject', ''),
                'items': items
            })
    except AuthenticationError:
        # conversations are only available on paid accounts that have 'Engage' plan
        # ... or in other words, has to be an account that has enabled in-app messaging
        print ("Could not fetch conversations for user '{}' with id: {}".format(user_name, user_id))
    return result


def fetch_user(user_or_admin_id):
    user = None
    if isinstance(user_or_admin_id, int) or user_or_admin_id.isdigit():
        user = Admin.find(id=user_or_admin_id)
    else:
        user = User.find(id=user_or_admin_id)
    return {'id': user_or_admin_id, 'name': user.name, 'email': user.email}


def init_intercom(user):
    social = user.social_auth.get(provider='intercom-oauth')
    access_token = social.extra_data['access_token']
    Intercom.app_id = access_token


def _get_utc_timestamp():
    utc_dt = datetime.now(timezone.utc)
    return utc_dt.astimezone()
