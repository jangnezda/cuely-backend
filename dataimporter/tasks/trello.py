"""
Trello API integration. Indexing (open) boards, lists and cards.
"""
from trello import TrelloClient
from trello.exceptions import ResourceUnavailable
import time
from datetime import datetime, timezone
from dateutil.parser import parse as parse_dt
from celery import shared_task, subtask
from django.conf import settings

from dataimporter.task_util import should_sync, should_queue
from dataimporter.models import Document
from dataimporter.algolia.engine import algolia_engine
from social.apps.django_app.default.models import UserSocialAuth
import logging
logger = logging.getLogger(__name__)

TRELLO_PRIMARY_KEYWORDS = 'trello'
TRELLO_SECONDARY_KEYWORDS = {
    'board': 'board',
    'card': 'card'
}


def start_synchronization(user):
    """ Run initial syncing of boards data in trello. """
    if should_sync(user, 'trello', 'tasks.trello'):
        collect_boards.delay(requester=user)
    else:
        logger.info("Trello oauth token for user '%s' already in use, skipping sync ...", user.username)


@shared_task
@should_queue
def update_synchronization():
    """
    Run sync/update of all users' boards data in trello.
    Should be run periodically to keep the data fresh in our db.
    """
    for us in UserSocialAuth.objects.filter(provider='trello'):
        start_synchronization(user=us.user)


@shared_task
def collect_boards(requester):
    trello_client = init_trello_client(requester)
    orgs = dict()

    i = 0
    for board in trello_client.list_boards(board_filter='open'):
        db_board, created = Document.objects.get_or_create(
            trello_board_id=board.id,
            requester=requester,
            user_id=requester.id
        )
        board_last_activity = board.raw.get('dateLastActivity')
        if not board_last_activity:
            # this nasty hack is needed, becuse some Trello boards don't have 'dateLastActivity' timestamp
            # -> looks like it's those boards that have been inactive for some time
            if not created:
                board_last_activity = db_board.last_updated.isoformat()
            else:
                # Trello was established in 2011, so we use 01.01.2011 as epoch
                actions = board.fetch_actions(action_filter='all', action_limit=1, since='2011-01-01T00:00:00.000Z')
                if actions:
                    board_last_activity = actions[0].get('date')

        last_activity = parse_dt(board_last_activity).isoformat()
        last_activity_ts = int(parse_dt(board_last_activity).timestamp())
        if not created and db_board.last_updated_ts and db_board.last_updated_ts >= last_activity_ts:
            logger.debug("Trello board '%s' for user '%s' hasn't changed", board.name, requester.username)
            continue
        logger.debug("Processing board '%s' for user '%s'", board.name, requester.username)
        db_board.primary_keywords = TRELLO_PRIMARY_KEYWORDS
        db_board.secondary_keywords = TRELLO_SECONDARY_KEYWORDS['board']
        db_board.last_updated = last_activity
        db_board.last_updated_ts = last_activity_ts
        db_board.trello_title = board.name
        db_board.webview_link = board.url
        db_board.trello_content = board.description
        db_board.trello_board_lists = [l.name for l in board.open_lists()]
        orgId = board.raw.get('idOrganization')
        if orgId and orgId not in orgs:
            try:
                org = trello_client.get_organization(orgId).raw
                orgs[orgId] = {
                    'name': org.get('displayName'),
                    'logo': 'https://trello-logos.s3.amazonaws.com/{}/30.png'.format(orgId),
                    'url': org.get('url')
                }
            except ResourceUnavailable:
                # defunct/deleted organization, assume that board is personal
                orgId = None
        db_board.trello_board_org = orgs[orgId] if orgId else None
        db_board.trello_board_members = [
            {
                'name': m.full_name,
                'url': m.url,
                'avatar': 'https://trello-avatars.s3.amazonaws.com/{}/30.png'.format(m.avatar_hash)
            }
            for m in board.all_members()
        ]
        db_board.last_synced = _get_utc_timestamp()
        db_board.download_status = Document.READY
        db_board.save()
        algolia_engine.sync(db_board, add=created)
        time.sleep(5)
        i = i + 1
        subtask(collect_cards).apply_async(
            args=[requester, db_board],
            countdown=180 * i
        )


@shared_task
def collect_cards(requester, board):
    pass


def init_trello_client(user):
    social = user.social_auth.filter(provider='trello').first()
    if not social:
        return None
    return TrelloClient(
        api_key=settings.SOCIAL_AUTH_TRELLO_KEY,
        api_secret=settings.SOCIAL_AUTH_TRELLO_SECRET,
        token=social.extra_data['access_token']['oauth_token'],
        token_secret=social.extra_data['access_token']['oauth_token_secret']
    )


def _get_utc_timestamp():
    utc_dt = datetime.now(timezone.utc)
    return utc_dt.astimezone()
