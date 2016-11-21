"""
Helpscout API integration.
The 'while True' loops are there because of how helpscout api library works when dealing with paged results.
"""
import json
import time
from datetime import datetime, timezone
from dateutil.parser import parse as parse_dt
from celery import shared_task, subtask

import helpscout
from dataimporter.task_util import should_sync
from dataimporter.models import Document
from social.apps.django_app.default.models import UserSocialAuth
import logging
logger = logging.getLogger(__name__)

HELPSCOUT_KEYWORDS = {
    'primary': 'helpscout',
    'secondary': 'customer,ticket,support'
}


def start_synchronization(user):
    """ Run initial syncing of deals data in pipedrive. """
    if should_sync(user, 'helpscout-apikeys', 'tasks.help_scout'):
        collect_customers.delay(requester=user)
    else:
        logger.info("Helpscout api key for user '%s' already in use, skipping sync ...", user.username)


@shared_task
def update_synchronization():
    """
    Run sync/update of all users' deals data in pipedrive.
    Should be run periodically to keep the data fresh in our db.
    """
    for us in UserSocialAuth.objects.filter(provider='helpscout-apikeys'):
        start_synchronization(user=us.user)


@shared_task
def collect_customers(requester):
    helpscout_client = init_helpscout_client(requester)
    # cache all mailboxes and their folders
    mailboxes = {m.id: m.name for m in helpscout_client.mailboxes()}
    folders = {}
    for box in mailboxes:
        helpscout_client.clearstate()
        while True:
            box_folders = helpscout_client.folders(box)
            if not box_folders or box_folders.count < 1:
                break
            folders[box] = {f.id: f.name for f in box_folders}
    # cache users
    users = {}
    while True:
        helpscout_users = helpscout_client.users()
        if not helpscout_users or helpscout_users.count < 1:
            break
        for u in helpscout_users:
            users[u.id] = {
                'id': u.id,
                'name': u.fullname,
                'email': u.email,
                'avatar': u.photourl
            }

    while True:
        customers = helpscout_client.customers()
        if not customers or customers.count < 1:
            break
        for customer in customers:
            if customer.id is None or (customer.emails is None and customer.fullname is None):
                # can't use customer with no data
                logger.debug("Customer '%s' for user '%s' cannot be used - no data",
                             (customer.id or customer.fullname), requester.username)
                continue
            db_customer, created = Document.objects.get_or_create(
                helpscout_customer_id=customer.id,
                requester=requester,
                user_id=requester.id
            )
            db_customer.helpscout_name = customer.fullname
            logger.debug("Processing Helpscout customer '%s' for user '%s'", customer.fullname, requester.username)
            db_customer.helpscout_title = 'User: {}'.format(customer.fullname)
            db_customer.last_updated = customer.modifiedat
            db_customer.last_updated_ts = parse_dt(customer.modifiedat).timestamp()
            db_customer.webview_link = 'https://secure.helpscout.net/customer/{}/0/'.format(customer.id)
            db_customer.primary_keywords = HELPSCOUT_KEYWORDS['primary']
            db_customer.secondary_keywords = HELPSCOUT_KEYWORDS['secondary']
            db_customer.helpscout_company = customer.organization
            db_customer.helpscout_emails = ', '.join(customer.emails) if customer.emails else None
            db_customer.save()
            subtask(process_customer).delay(requester, db_customer, mailboxes, folders, users)
            # add sleep of one second to avoid breaking API rate limits
            time.sleep(1)


@shared_task
def process_customer(requester, db_customer, mailboxes, folders, users):
    helpscout_client = init_helpscout_client(requester)
    db_customer.download_status = Document.PROCESSING
    db_customer.save()

    last_conversation = {}
    conversation_emails = set()
    conversations = []
    for box_id, box_name in mailboxes.items():
        logger.debug("Fetching Helpscout conversations for '%s' in mailbox '%s'", db_customer.helpscout_name, box_name)
        while True:
            box_conversations = helpscout_client.conversations_for_customer_by_mailbox(
                box_id, db_customer.helpscout_customer_id)
            if not box_conversations or box_conversations.count < 1:
                break
            for bc in box_conversations:
                conversation = {
                    'id': bc.id,
                    'mailbox': box_name,
                    'mailbox_id': box_id,
                    'folder': folders.get(bc.folderid),
                    'status': bc.status,
                    'owner': format_person(bc.owner),
                    'customer': format_person(bc.customer),
                    'subject': bc.subject,
                    'tags': bc.tags
                }
                last_updated = next(
                    (getattr(bc, x) for x in ['usermodifiedat', 'modifiedat', 'createdat'] if hasattr(bc, x)),
                    None
                )
                conversation['last_updated'] = last_updated
                if last_updated:
                    conversation['last_updated_ts'] = parse_dt(last_updated).timestamp()
                conversations.append(conversation)
                if bc.customer and 'email' in bc.customer:
                    conversation_emails.add(bc.customer.get('email'))
                if last_updated and \
                        conversation.get('last_updated_ts', 0) > last_conversation.get('last_updated_ts', 0):
                    last_conversation = conversation
        # add sleep of one second to avoid breaking API rate limits
        time.sleep(1)
        helpscout_client.clearstate()
    if db_customer.last_updated and db_customer.helpscout_status and \
            db_customer.last_updated >= last_conversation.get('last_updated_ts', 0):
        logger.info(
            "Helpscout customer '%s' for user '%s' seems unchanged, skipping further processing",
            db_customer.helpscout_name, requester.username
        )
        db_customer.download_status = Document.READY
        db_customer.save()
        return

    db_customer.last_updated = last_conversation.get('last_updated')
    db_customer.last_updated_ts = last_conversation.get('last_updated_ts')
    db_customer.helpscout_mailbox = last_conversation.get('mailbox')
    db_customer.helpscout_mailbox_id = last_conversation.get('mailbox_id')
    db_customer.helpscout_folder = last_conversation.get('folder')
    db_customer.helpscout_status = last_conversation.get('status')
    db_customer.helpscout_assigned = last_conversation.get('owner') is not None
    if conversation_emails:
        if db_customer.helpscout_emails:
            conversation_emails = conversation_emails.union(db_customer.helpscout_emails.split(', '))
        db_customer.helpscout_emails = ', '.join(conversation_emails)

    # build helpscout content json
    content = process_conversations(users, conversations, helpscout_client)
    db_customer.helpscout_content = json.dumps(content)
    db_customer.download_status = Document.READY
    db_customer.last_synced = _get_utc_timestamp()
    db_customer.save()


def format_person(person):
    if not person:
        return None
    return {
        'id': person.get('id'),
        'name': '{} {}'.format(person.get('firstName'), person.get('lastName')),
        'email': person.get('email')
    }


def process_conversations(users, conversations, helpscout_client):
    content = {
        'users': [],
        'conversations': []
    }
    active_users = {}
    # conversations
    for c in conversations:
        # load conversation threads
        threads = helpscout_client.conversation(c.get('id')).threads
        if threads:
            c['threads'] = []
            for t in threads:
                is_customer = (t['createdBy']['type'] == 'customer')
                if t.get('type', '') != 'lineitem' and t.get('body'):
                    p = format_person(t['createdBy'])
                    c['threads'].append({
                        'created': parse_dt(t.get('createdAt')).timestamp(),
                        'author': p.get('name'),
                        'author_id': p.get('id'),
                        'body': t.get('body'),
                        'is_customer': is_customer
                    })
                uid = t['createdBy'].get('id')
                if uid and uid in users and not is_customer:
                    active_users[uid] = users[uid]

            content['conversations'].insert(0, c)
        helpscout_client.clearstate()
    content['users'] = [v for k, v in active_users.items()]
    return content


def init_helpscout_client(user):
    social = user.social_auth.filter(provider='helpscout-apikeys').first()
    if not social:
        return None
    client = helpscout.Client()
    client.api_key = social.extra_data['api_key']
    return client


def _get_utc_timestamp():
    utc_dt = datetime.now(timezone.utc)
    return utc_dt.astimezone()