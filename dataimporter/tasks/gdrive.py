import os
import httplib2
import re
from dateutil.parser import parse as parse_date

from apiclient import discovery
from celery import shared_task, subtask
from oauth2client.client import GoogleCredentials

from dataimporter.models import Document, SocialAttributes
from dataimporter.algolia.engine import algolia_engine
from dataimporter.task_util import should_sync, should_queue, cut_utf_string, get_utc_timestamp
import logging
logger = logging.getLogger(__name__)

EXPORTABLE_MIMES = [
    'application/vnd.google-apps.spreadsheet',
    'application/vnd.google-apps.document',
    'application/vnd.google-apps.presentation',
    'text/'
]
# list of ignored mime types for gdrive api calls
IGNORED_MIMES_API = [
    'image/',
    'audio/',
    'video/'
]
# list of ignored mime types for filtering the gdrive api results (file listings)
ignored_mimes_regex = [
    r'.*[-+/](zip|tar|gzip|bz2|rar|octet-stream).*',
    r'image/.*',
    r'video/.*',
    r'audio/.*'
]
IGNORED_MIMES = [re.compile(x, re.UNICODE | re.IGNORECASE) for x in ignored_mimes_regex]
FILE_FIELDSET = ','.join([
    'name',
    'id',
    'mimeType',
    'modifiedTime',
    'webViewLink',
    'thumbnailLink',
    'iconLink',
    'trashed',
    'lastModifyingUser(displayName,photoLink)',
    'owners(displayName,photoLink)',
    'parents',
    'description',
    'capabilities'
])
GDRIVE_KEYWORDS = {
    'primary': 'gdrive,google drive',
    'secondary': {
        'application/pdf': 'pdf',
        'application/vnd.google-apps.document': 'google docs,docs,documents',
        'application/vnd.google-apps.spreadsheet': 'google sheets,sheets,spreadsheets',
        'application/postscript': 'postscript',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'word,documents',
        'application/vnd.google-apps.presentation': 'google slides,presentations,prezos,slides',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'excel,sheets,spreadsheets',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation':
            'ppt,powerpoint,presentations slides,prezos',
        'text/xml': 'xml',
        'text/plain': 'text file',
        'application/x-iwork-numbers-sffnumbers': 'iwork,numbers',
        'application/msword': 'word,documents',
        'application/illustrator': 'illustrator',
        'application/x-iwork-pages-sffpages': 'iwork,pages',
        'application/vnd.ms-excel': 'excel,sheets,spreadsheets',
        'application/vnd.ms-powerpoint': 'ppt,powerpoint,presentations slides,prezos',
        'text/csv': 'csv',
        'application/vnd.google-apps.drawing': 'google drawing,drawings',
        'application/x-iwork-keynote-sffkey': 'keynote,slides,presentations,prezos',
        'application/vnd.google-apps.form': 'google form,forms',
        'text/html': 'html',
        'application/x-javascript': 'javascript',
        'application/xml': 'xml',
        'application/rtf': 'rtf',
        'text/css': 'css,stylesheets',
        'application/vnd.ms-excel.sheet.macroenabled.12': 'excel,sheets,spreadsheets',
        'application/vnd.google-apps.folder': 'folders,dirs'
    }
}


def start_synchronization(user):
    """ Run initial syncing of user's data in external systems. Gdrive-only at the moment. """
    if should_sync(user, 'google-oauth2', 'tasks.gdrive'):
        access_token, refresh_token = get_google_tokens(user)

        # ## gdrive ###################
        # 1. Set the marker to have a reference point for later calls to gdrive changes api.
        #    Without setting this starting point, changes api won't return any changes.
        service = connect_to_gdrive(access_token, refresh_token)
        response = service.changes().getStartPageToken().execute()
        SocialAttributes.objects.update_or_create(
            user=user, defaults={'start_page_token': response.get('startPageToken')})

        # 2. Start the synchronization
        collect_gdrive_docs.delay(user, access_token, refresh_token)
    else:
        logger.info("Gdrive oauth token for user '%s' already in use, skipping sync ...", user.username)


@shared_task
@should_queue
def update_synchronization():
    """
    Check for new/updated files in external systems for all users. Should be called periodically after initial syncing.
    Gdrive-only at the moment.
    """
    logger.debug("Update synchronizations started")
    for sa in SocialAttributes.objects.filter(start_page_token__isnull=False):
        if should_sync(sa.user, 'google-oauth2', 'tasks.gdrive'):
            if sa.user.social_auth.filter(provider='google-oauth2').first():
                access_token, refresh_token = get_google_tokens(sa.user)
                subtask(sync_gdrive_changes).delay(sa.user, access_token, refresh_token, sa.start_page_token)
        else:
            logger.info("Gdrive oauth token for user '%s' already in use, skipping sync ...", sa.user.username)


@shared_task
def collect_gdrive_docs(requester, access_token, refresh_token):
    logger.debug("LIST gdrive files")

    def _call_gdrive(service, page_token):
        # want to produce 'q' filter like this:
        #    "pageSize = 300 and fields = '...' and not (mimeType contains 'image/' or mimeType contains ...)"
        ignore_mime_types = ' or '.join(["mimeType contains '{}'".format(x) for x in IGNORED_MIMES_API])
        params = {
            'q': "not ({})".format(ignore_mime_types),
            'pageSize': 300,
            'fields': 'files({}),nextPageToken'.format(FILE_FIELDSET)
        }
        if page_token:
            params['pageToken'] = page_token
        return service.files().list(**params).execute()

    process_gdrive_docs(requester, access_token, refresh_token, files_fn=_call_gdrive, json_key='files')


@shared_task
def collect_gdrive_folders(requester, access_token, refresh_token):
    logger.debug("LIST gdrive folders")

    def _call_gdrive(service, page_token):
        params = {
            'q': "mimeType = 'application/vnd.google-apps.folder'",
            'pageSize': 300,
            'fields': 'files({}),nextPageToken'.format(FILE_FIELDSET)
        }
        if page_token:
            params['pageToken'] = page_token
        return service.files().list(**params).execute()

    process_gdrive_docs(requester, access_token, refresh_token, files_fn=_call_gdrive, json_key='files')


@shared_task
def sync_gdrive_changes(requester, access_token, refresh_token, start_page_token):
    logger.debug("CHANGES gdrive files")

    def _call_gdrive(service, page_token):
        params = {
            'pageSize': 300,
            'fields': 'changes(file({})),newStartPageToken,nextPageToken'.format(FILE_FIELDSET),
            'pageToken': page_token or start_page_token,
            'spaces': 'drive',
            'includeRemoved': True,
            'restrictToMyDrive': False
        }
        return service.changes().list(**params).execute()

    new_start_page_token = process_gdrive_docs(
        requester,
        access_token,
        refresh_token,
        files_fn=_call_gdrive,
        json_key='changes'
    )
    if new_start_page_token:
        SocialAttributes.objects.update_or_create(user=requester, defaults={'start_page_token': new_start_page_token})


def process_gdrive_docs(requester, access_token, refresh_token, files_fn, json_key):
    service = connect_to_gdrive(access_token, refresh_token)
    folders = {}

    page_token = None
    new_start_page_token = None
    while True:
        files = files_fn(service, page_token)
        new_start_page_token = files.get('newStartPageToken', new_start_page_token)
        items = files.get(json_key, [])
        if not folders and len(items) > 0:
            # retreive all folders to be able to get file path more easily in the file listing(s)
            folders = get_gdrive_folders(service)
            # check if any folder was marked as hidden and we already have it synced ...
            # if we do, then remove it (plus all children) from our indexing
            for folder_id, folder in folders.items():
                if folder.get('hidden') is True:
                    desync_folder(folder.get('id'), folders, requester, service)

        for item in items:
            if 'file' in item:
                item = item['file']
            # check for ignored mime types
            if any(x.match(item.get('mimeType', '')) for x in IGNORED_MIMES):
                continue
            parents = item.get('parents', [])
            hidden = is_hidden(item.get('description')) or any(is_hidden_in_folder(f, folders) for f in parents)
            if item.get('trashed') or hidden:
                # file was removed or hidden
                Document.objects.filter(
                    document_id=item['id'],
                    requester=requester,
                    user_id=requester.id
                ).delete()
                continue

            # handle file path within gdrive
            parent = parents[0] if parents else None
            path = get_gdrive_path(parent, folders)

            doc, created = Document.objects.get_or_create(
                document_id=item['id'],
                requester=requester,
                user_id=requester.id
            )
            doc.mime_type = item.get('mimeType').lower()
            doc.title = item.get('name')
            doc.webview_link = item.get('webViewLink')
            doc.icon_link = item.get('iconLink')
            doc.thumbnail_link = item.get('thumbnailLink')
            doc.last_updated = item.get('modifiedTime')
            doc.path = path
            last_modified_on_server = parse_date(doc.last_updated)
            doc.last_updated_ts = last_modified_on_server.timestamp()
            doc.modifier_display_name = item.get('lastModifyingUser', {}).get('displayName')
            doc.modifier_photo_link = item.get('lastModifyingUser', {}).get('photoLink')
            doc.owner_display_name = item['owners'][0]['displayName']
            doc.owner_photo_link = item.get('owners', [{}])[0].get('photoLink')
            doc.primary_keywords = GDRIVE_KEYWORDS['primary']
            doc.secondary_keywords = GDRIVE_KEYWORDS['secondary'][doc.mime_type] \
                if doc.mime_type in GDRIVE_KEYWORDS['secondary'] else None
            can_download = item.get('capabilities', {}).get('canDownload', True)
            if not created:
                if doc.download_status is Document.READY and can_download and \
                        (doc.last_synced is None or last_modified_on_server > doc.last_synced):
                    doc.download_status = Document.PENDING
                    subtask(download_gdrive_document).delay(doc, access_token, refresh_token)
            else:
                algolia_engine.sync(doc, add=created)
                if can_download:
                    subtask(download_gdrive_document).delay(doc, access_token, refresh_token)
                else:
                    doc.last_synced = get_utc_timestamp()
                    doc.download_status = Document.READY

            doc.save()

        page_token = files.get('nextPageToken')
        if not page_token:
            break
    return new_start_page_token


def desync_folder(folder_id, folders, requester, service):
    db_folder = Document.objects.filter(document_id=folder_id, user_id=requester.id)
    if db_folder.exists():
        page_token = None
        while True:
            params = {
                'q': "'{}' in parents".format(folder_id),
                'pageSize': 100,
                'fields': 'files(id),nextPageToken'
            }
            if page_token:
                params['pageToken'] = page_token
            children = service.files().list(**params).execute()
            child_ids = [c.get('id') for c in children.get('files', [])]
            for cid in child_ids:
                if cid in folders:
                    desync_folder(cid, folders, requester, service)
            Document.objects.filter(document_id__in=child_ids, user_id=requester.id).delete()
            page_token = children.get('nextPageToken')
            if not page_token:
                break
        db_folder.delete()


def get_gdrive_folders(service):
    page_token = None
    lookup = {}
    while True:
        params = {
            'q': "mimeType = 'application/vnd.google-apps.folder'",
            'pageSize': 100,
            'fields': 'files(id,name,parents,description),nextPageToken'
        }
        if page_token:
            params['pageToken'] = page_token
        files = service.files().list(**params).execute()
        for item in files.get('files', []):
            parents = item.get('parents', [])
            lookup[item.get('id')] = {
                'id': item.get('id'),
                'parent': parents[0] if parents else None,
                'name': item.get('name'),
                'hidden': is_hidden(item.get('description'))
            }
        page_token = files.get('nextPageToken')
        if not page_token:
            break
    return lookup


def is_hidden(item_description):
    if not item_description:
        return False
    return '!cuely' in item_description.lower()


def is_hidden_in_folder(file_id, folders):
    if not (file_id and folders and file_id in folders):
        return []
    while file_id is not None:
        f = folders.get(file_id)
        if f.get('hidden') is True:
            return True
        file_id = f.get('parent')
        if file_id not in folders:
            file_id = None
    return False


def get_gdrive_path(file_id, folders):
    if not (file_id and folders and file_id in folders):
        return []
    path = []
    while file_id is not None:
        f = folders.get(file_id)
        path.append(f.get('name'))
        file_id = f.get('parent')
        if file_id not in folders:
            file_id = None
    path.reverse()
    return path


@shared_task
def download_gdrive_document(doc, access_token, refresh_token):
    if not any(x for x in EXPORTABLE_MIMES if doc.mime_type.startswith(x)):
        doc.download_status = Document.READY
        doc.last_synced = get_utc_timestamp()
        doc.save()
        algolia_engine.sync(doc, add=False)
        return

    doc.download_status = Document.PROCESSING
    doc.save()

    try:
        service = connect_to_gdrive(access_token, refresh_token)

        request = None
        if doc.mime_type.startswith('application/vnd.google-apps.'):
            export_mime = 'text/csv' if 'spreadsheet' in doc.mime_type else 'text/plain'
            request = service.files().export_media(fileId=doc.document_id, mimeType=export_mime)
        else:
            request = service.files().get_media(fileId=doc.document_id)
        response = request.execute()
        logger.info("Done downloading {} [{}]".format(doc.title, doc.document_id))

        content = cut_utf_string(response.decode('UTF-8', errors='replace'), 9000, step=10)
        doc.content = content
        doc.last_synced = get_utc_timestamp()
        algolia_engine.sync(doc, add=False)
    finally:
        doc.download_status = Document.READY
        doc.save()


def get_google_tokens(user):
    social = user.social_auth.get(provider='google-oauth2')
    access_token = social.extra_data['access_token']
    refresh_token = social.extra_data['refresh_token']
    return (access_token, refresh_token)


def connect_to_gdrive(access_token, refresh_token):
    credentials = GoogleCredentials(
        access_token,
        os.environ['GDRIVE_API_CLIENT_ID'],
        os.environ['GDRIVE_API_CLIENT_SECRET'],
        refresh_token,
        None,
        "https://www.googleapis.com/oauth2/v4/token",
        "cuely/1.0"
    )
    http = httplib2.Http()
    http = credentials.authorize(http)
    service = discovery.build('drive', 'v3', http=http)
    return service
