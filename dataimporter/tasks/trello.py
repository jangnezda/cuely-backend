"""
Trello API integration. Indexing (open) boards, lists and cards.
"""
from collections import defaultdict
from operator import itemgetter
from trello import TrelloClient, Board
from trello.exceptions import ResourceUnavailable
import time
from dateutil.parser import parse as parse_dt
from celery import shared_task, subtask
from django.conf import settings
import markdown

from dataimporter.task_util import should_sync, should_queue, cut_utf_string, get_utc_timestamp
from dataimporter.models import Document
from dataimporter.algolia.engine import algolia_engine
from social.apps.django_app.default.models import UserSocialAuth
import logging
logger = logging.getLogger(__name__)

TRELLO_PRIMARY_KEYWORDS = 'trello'
TRELLO_SECONDARY_KEYWORDS = {
    'board': 'board',
    'card': 'card,task,issue'
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

    for board in trello_client.list_boards(board_filter='open,closed'):
        db_board, created = Document.objects.get_or_create(
            trello_board_id=board.id,
            trello_card_id__isnull=True,
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
        if not created and db_board.download_status == Document.READY and \
                (db_board.last_updated_ts and db_board.last_updated_ts >= last_activity_ts):
            logger.debug("Trello board '%s' for user '%s' hasn't changed", board.name[:50], requester.username)
            continue
        logger.debug("Processing board '%s' for user '%s'", board.name[:50], requester.username)
        db_board.primary_keywords = TRELLO_PRIMARY_KEYWORDS
        db_board.secondary_keywords = TRELLO_SECONDARY_KEYWORDS['board']
        db_board.last_updated = last_activity
        db_board.last_updated_ts = last_activity_ts
        db_board.trello_title = 'Board: {}'.format(board.name)
        db_board.webview_link = board.url
        db_board._trello_description = board.description
        db_board.trello_board_status = 'Closed' if board.closed else 'Open'

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

        build_list = lambda l: {
            'id': l.id,
            'name': l.name,
            'closed': l.closed,
            'pos': l.pos
        }
        all_lists = {l.id: build_list(l) for l in board.all_lists()}
        db_board.trello_content = {
            'description': _to_html(board.description),
            'lists': sorted(
                filter(lambda x: not x.get('closed'), all_lists.values()),
                key=itemgetter('pos')
            )
        }

        build_member = lambda m: {
            'name': m.full_name,
            'url': m.url,
            'avatar': 'https://trello-avatars.s3.amazonaws.com/{}/30.png'.format(m.avatar_hash)
        }
        all_members = {m.id: build_member(m) for m in board.all_members()}
        db_board.trello_board_members = list(all_members.values())

        db_board.last_synced = get_utc_timestamp()
        db_board.download_status = Document.READY
        db_board.save()
        algolia_engine.sync(db_board, add=created)
        subtask(collect_cards).delay(requester, db_board, board.name, all_members, all_lists)
        # add sleep of 30s to avoid breaking api limits
        time.sleep(30)


@shared_task
def collect_cards(requester, db_board, board_name, board_members, all_lists):
    trello_client = init_trello_client(requester)
    # make an instance of py-trello's Board object to have access to relevant api calls
    board = Board(client=trello_client, board_id=db_board.trello_board_id)
    board.name = board_name
    # load all checklists
    checklists = defaultdict(list)
    for cl in board.get_checklists():
        checklists[cl.card_id].append(cl)
    open_cards = collect_cards_internal(requester, board, board_members, checklists, all_lists, card_status='open')
    # request closed cards separately to have a better chance to index all open cards
    # (thus avoiding hitting rate limits already in open cards indexing)
    collect_cards_internal(requester, board, board_members, checklists, all_lists, card_status='closed')

    # update board lists with a list of cards
    lists_with_cards = defaultdict(list)
    for ac in open_cards:
        lists_with_cards[ac.idList].append({
            'id': ac.id,
            'name': ac.name,
            'pos': ac.pos,
            'url': ac.url
        })
    board_lists = db_board.trello_content.get('lists', [])
    for bl in board_lists:
        bl.update({
            'cards': sorted(lists_with_cards[bl['id']], key=itemgetter('pos'))
        })
    db_board.trello_content = {
        'description': db_board.trello_content.get('description'),
        'lists': board_lists
    }
    db_board.save()
    algolia_engine.sync(db_board, add=False)


def collect_cards_internal(requester, board, board_members, checklists, lists, card_status):
    collected_cards = []
    last_card_id = None
    while True:
        filters = {'filter': 'all', 'fields': 'all', 'limit': '1000'}
        if last_card_id:
            # Trello api supports paging by using the id of the last card in the previous batch as 'before' parameter
            filters['before'] = last_card_id
        cards = board.get_cards(filters=filters, card_filter=card_status)
        for card in cards:
            db_card, created = Document.objects.get_or_create(
                trello_board_id=board.id,
                trello_card_id=card.id,
                requester=requester,
                user_id=requester.id
            )
            card_last_activity = card.raw.get('dateLastActivity')
            last_activity = parse_dt(card_last_activity).isoformat()
            last_activity_ts = int(parse_dt(card_last_activity).timestamp())
            collected_cards.append(card)
            if not created and db_card.last_updated_ts and db_card.last_updated_ts >= last_activity_ts:
                logger.debug("Trello card '%s' for user '%s' hasn't changed", card.name[:50], requester.username)
                continue
            logger.debug("Processing card '%s' for user '%s'", card.name[:50], requester.username)
            db_card.primary_keywords = TRELLO_PRIMARY_KEYWORDS
            db_card.secondary_keywords = TRELLO_SECONDARY_KEYWORDS['card']
            db_card.last_updated = last_activity
            db_card.last_updated_ts = last_activity_ts
            db_card.trello_title = 'Card: {}'.format(card.name)
            db_card.webview_link = card.url
            db_card.trello_content = {
                'description': _to_html(card.description),
                'checklists': [
                    {
                        'id': cl.id,
                        'name': cl.name,
                        'items': cl.items
                    }
                    for cl in checklists[card.id]
                ]
            }
            db_card.trello_card_status = 'Archived' if card.closed else 'Open'
            db_card.trello_card_members = [board_members.get(m) for m in card.idMembers if m in board_members]
            db_card.trello_board_name = board.name
            db_card.trello_list = lists.get(card.idList)
            db_card.last_synced = get_utc_timestamp()
            db_card.download_status = Document.READY
            db_card.save()
            algolia_engine.sync(db_card, add=created)
            last_card_id = card.id
        if len(cards) < 1000:
            break
    return collected_cards


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


def _to_html(markdown_text, max_len=8000):
    if not markdown_text:
        return None
    # convert markdown to html (replace any <em> tags with bold tags, because <em> is reserved by Algolia
    md = markdown.markdown(cut_utf_string(markdown_text, max_len, step=100))
    return md.replace('<em>', '<b>').replace('</em>', '</b>')
