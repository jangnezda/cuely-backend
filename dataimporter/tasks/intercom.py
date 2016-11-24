"""
Intercom API integration. A note about date/time manipulation: python-intercom library which is used for this
integration  naively translates timestamps to dates, therefore we try to access the underlying data directly.
"""
import json
import time
from datetime import datetime, timezone
from celery import shared_task, subtask
from intercom import Event, Intercom, User, Admin, Company, Segment, Conversation, AuthenticationError, ResourceNotFound

from dataimporter.models import Document
from dataimporter.task_util import should_sync
from social.apps.django_app.default.models import UserSocialAuth
import logging
logger = logging.getLogger(__name__)

INTERCOM_KEYWORDS = {
    'primary': 'inter,intercom',
    'secondary': 'user,event,conversation,chat'
}


def start_synchronization(user, update=False):
    """ Run initial syncing of user's data in intercom. """
    if should_sync(user, 'intercom-apikeys', 'tasks.intercom'):
        collect_users.delay(requester=user, sync_update=update)
    else:
        logger.info("Intercom api key for user '%s' already in use, skipping sync ...", user.username)


@shared_task
def update_synchronization():
    """ Run re-syncing of user's data in intercom. """
    for us in UserSocialAuth.objects.filter(provider='intercom-apikeys'):
        start_synchronization(user=us.user, update=True)


@shared_task
def collect_users(requester, sync_update=False):
    """ Fetch all users for this account from Intercom """
    init_intercom(requester)
    for u in User.find_all(sort='updated_at', order='desc'):
        if not (u.name or u.email):
            # empty/rubbish data, can happen with Intercom API
            continue

        db_user, created = Document.objects.get_or_create(
            intercom_user_id=u.id,
            requester=requester,
            user_id=requester.id
        )
        new_updated_ts = u.__dict__.get('updated_at') or u.__dict__.get('last_request_at')
        if sync_update and (new_updated_ts < datetime.now().timestamp() - 12 * 3600):
            # user has been updated more than 12h ago, stop syncing other (older) users
            break
        old_updated_ts = 1
        if not created and db_user.last_updated_ts:
            old_updated_ts = db_user.last_updated_ts
            new_updated_ts = db_user.last_updated_ts if db_user.last_updated_ts > new_updated_ts else new_updated_ts
        db_user.last_updated_ts = new_updated_ts
        db_user.last_updated = datetime.utcfromtimestamp(db_user.last_updated_ts).isoformat() + 'Z'
        db_user.intercom_email = u.email
        db_user.intercom_title = 'User: {}'.format(u.name or u.email)
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
            'app_id': u.app_id,
            'name': u.name,
            'segments': list(map(lambda x: x.id, u.segments)),
            'companies': list(map(lambda x: x.id, u.companies)),
            'old_updated_ts': old_updated_ts
        }
        subtask(process_user).delay(requester, intercom_user, db_user)
        # quick hack to avoid Intercom api rate limits
        time.sleep(3)


@shared_task
def process_user(requester, user, db_user):
    """ Further processing of the user, e.g. load events, companies, conversations """
    init_intercom(requester)
    db_user.download_status = Document.PROCESSING
    db_user.save()

    logger.info("Processing user '%s' with data: %s", user['name'], user)
    # build json for content -> events and conversations
    content = {
        'events': [],
        'conversations': []
    }
    for e in Event.find(type='user', intercom_user_id=user['id'], per_page=10).events:
        content['events'].append({
            'name': e['event_name'],
            'timestamp': e['created_at']
        })
    if len(content['events']) > 0:
        db_user.last_updated_ts = max(db_user.last_updated_ts, content['events'][0].get('timestamp', 0))
        db_user.last_updated = datetime.utcfromtimestamp(db_user.last_updated_ts).isoformat() + 'Z'

    # check if the last event timestamp/seen timestamp is different than old one
    user_updated_ts = user.get('old_updated_ts')
    if user_updated_ts and db_user.intercom_content and user_updated_ts >= db_user.last_updated_ts:
        logger.info("User '%s' seems unchanged, skipping further processing", user['name'])
        db_user.download_status = Document.READY
        db_user.save()
        return

    conversations = process_conversations(user['id'], user['name'])
    # work around algolia 10k bytes limit
    while len(json.dumps(conversations).encode('UTF-8')) > 9000:
        conversations = conversations[:-1]

    content['conversations'] = conversations
    db_user.intercom_content = json.dumps(content)

    # companies ... only use first one, add others when/if necessary
    if user['companies']:
        c = Company.find(id=user['companies'][0])
        if c and hasattr(c, 'name'):
            db_user.intercom_company = c.name
            db_user.intercom_plan = c.plan.name if c.plan else None
            db_user.intercom_monthly_spend = c.monthly_spend
    # segments
    segments = []
    for sid in user['segments']:
        s = None
        try:
            s = Segment.find(id=sid)
        except ResourceNotFound:
            pass
        if s:
            segments.append('{}::{}/{}'.format(s.name, user['app_id'], sid))
    if segments:
        db_user.intercom_segments = ', '.join(segments)

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
                items.insert(0, {
                    'timestamp': part.__dict__['created_at'],
                    'author': _find_user(part.author.id),
                    'author_id': part.author.id,
                    'body': part.body
                })
            result.append({
                'subject': conversation.get('conversation_message', {}).get('subject', ''),
                'open': conversation.get('open', False),
                'items': items
            })
    except AuthenticationError:
        # conversations are only available on paid accounts that have 'Engage' plan
        # ... or in other words, has to be an account that has enabled in-app messaging
        logger.warn("Could not fetch conversations for user '%s' with id: %s", user_name, user_id)
    return result


def fetch_user(user_or_admin_id):
    try:
        user = None
        if isinstance(user_or_admin_id, int) or user_or_admin_id.isdigit():
            user = Admin.find(id=user_or_admin_id)
        else:
            user = User.find(id=user_or_admin_id)
        return {'id': user_or_admin_id, 'name': user.name, 'email': user.email}
    except ResourceNotFound:
        # probably trying to get user/admin that doesn't exist anymore
        return {'id': user_or_admin_id, 'name': None, 'email': None}


def init_intercom(user):
    social = user.social_auth.filter(provider='intercom-apikeys').first()
    if social:
        Intercom.app_id = social.extra_data['app_id']
        Intercom.app_api_key = social.extra_data['api_key']
    else:
        social = user.social_auth.get(provider='intercom-oauth')
        Intercom.app_id = social.extra_data['access_token']


def _get_utc_timestamp():
    utc_dt = datetime.now(timezone.utc)
    return utc_dt.astimezone()
