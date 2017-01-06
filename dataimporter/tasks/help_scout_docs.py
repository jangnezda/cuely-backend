"""
Helpscout Docs API integration.
The 'while True' loops are there because of how helpscout api library works when dealing with paged results.
"""
import time
from datetime import datetime, timezone
from dateutil.parser import parse as parse_dt
from celery import shared_task, subtask

import helpscout
from dataimporter.task_util import should_sync, cut_utf_string, queue_full
from dataimporter.models import Document
from social.apps.django_app.default.models import UserSocialAuth
import logging
logger = logging.getLogger(__name__)

HELPSCOUT_DOCS_KEYWORDS = {
    'primary': 'helpscout',
    'secondary': 'article,document,doc'
}


def start_synchronization(user):
    """ Run initial syncing of deals data in pipedrive. """
    if should_sync(user, 'helpscout-docs-apikeys', 'tasks.help_scout_docs'):
        collect_articles.delay(requester=user)
    else:
        logger.info("Helpscout DOCS api key for user '%s' already in use, skipping sync ...", user.username)


@shared_task
def update_synchronization():
    """
    Run sync/update of all users' deals data in pipedrive.
    Should be run periodically to keep the data fresh in our db.
    """
    if queue_full(__name__.split('.')[-1]):
        logger.debug("help_scout_docs queue is full, skipping this beat")
        return

    for us in UserSocialAuth.objects.filter(provider='helpscout-docs-apikeys'):
        start_synchronization(user=us.user)


@shared_task
def collect_articles(requester):
    helpscout_client = init_helpscout_client(requester)
    docs_client = init_helpscout_docs_client(requester)
    if not docs_client:
        logger.warn("User %s is missing Helpscout Docs API key", requester.username)
        return
    # cache users
    users = {}
    if helpscout_client:
        while True:
            helpscout_users = helpscout_client.users()
            if not helpscout_users or helpscout_users.count < 1:
                break
            for u in helpscout_users:
                users[u.id] = {
                    'name': u.fullname,
                    'avatar': u.photourl
                }

    # cache categories
    cats = dict()
    while True:
        collections = docs_client.collections()
        if not collections or collections.count < 1:
            break
        for collection in collections:
            while True:
                categories = docs_client.categories(collection.id)
                if not categories or categories.count < 1:
                    break
                for category in categories:
                    cats[category.id] = (category.name, collection.name)

    for cat_id, names in cats.items():
        while True:
            articles = docs_client.articles(cat_id, status='published')
            if not articles or articles.count < 1:
                break
            for article in articles:
                db_doc, created = Document.objects.get_or_create(
                    helpscout_document_id=article.id,
                    requester=requester,
                    user_id=requester.id
                )
                logger.debug("Processing Helpscout article '%s' for user '%s'", article.name, requester.username)
                db_doc.helpscout_document_title = 'Doc: {}'.format(article.name)
                new_updated = article.updatedat or article.createdat
                new_updated_ts = parse_dt(new_updated).timestamp() if new_updated else _get_utc_timestamp()
                if not created and db_doc.last_updated_ts:
                    new_updated_ts = db_doc.last_updated_ts \
                        if db_doc.last_updated_ts > new_updated_ts else new_updated_ts
                    if db_doc.last_updated_ts >= new_updated_ts:
                        logger.info("Helpscout article '%s' for user '%s' is unchanged",
                                    article.name, requester.username)
                        continue

                db_doc.last_updated = datetime.utcfromtimestamp(new_updated_ts).isoformat() + 'Z'
                db_doc.last_updated_ts = new_updated_ts
                db_doc.webview_link = 'https://secure.helpscout.net/docs/{}/article/{}/'.format(
                    article.collectionid, article.id)
                db_doc.helpscout_document_public_link = article.publicurl
                db_doc.primary_keywords = HELPSCOUT_DOCS_KEYWORDS['primary']
                db_doc.secondary_keywords = HELPSCOUT_DOCS_KEYWORDS['secondary']
                db_doc.helpscout_document_collection = names[1]
                db_doc.helpscout_document_categories = [names[0]] if not names[0] == 'Uncategorized' else []
                db_doc.helpscout_document_status = article.status
                db_doc.helpscout_document_keywords = article.keywords or []
                db_doc.helpscout_document_users = \
                    [users.get(x) for x in set([article.createdby, article.updatedby])] if users else []
                db_doc.save()
                subtask(process_article).delay(requester, db_doc, cats)
                time.sleep(1)


@shared_task
def process_article(requester, db_doc, cats):
    docs_client = init_helpscout_docs_client(requester)
    db_doc.download_status = Document.PROCESSING
    db_doc.save()

    article_details = docs_client.article(db_doc.helpscout_document_id)
    db_doc.helpscout_document_categories = \
        [c for c in [cats.get(x, [None])[0] for x in article_details.categories] if c and c != 'Uncategorized']
    db_doc.helpscout_document_content = cut_utf_string(article_details.text, 9000, 300)

    db_doc.download_status = Document.READY
    db_doc.last_synced = _get_utc_timestamp()
    db_doc.save()


def init_helpscout_client(user):
    return _init_client(user, 'helpscout-apikeys', False)


def init_helpscout_docs_client(user):
    return _init_client(user, 'helpscout-docs-apikeys', True)


def _init_client(user, provider, is_docs=False):
    social = user.social_auth.filter(provider=provider).first()
    if social:
        client = helpscout.ClientDocs() if is_docs else helpscout.Client()
        client.api_key = social.extra_data['api_key']
        return client
    return None


def _get_utc_timestamp():
    utc_dt = datetime.now(timezone.utc)
    return utc_dt.astimezone()
