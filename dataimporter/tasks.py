import os
import sys
import traceback
import httplib2
from datetime import datetime, timezone
from dateutil.parser import parse as parse_date

from apiclient import discovery
from celery import shared_task, subtask
from oauth2client.client import GoogleCredentials

from .models import Document, SocialAttributes

exportable_mimes = [
    'application/vnd.google-apps.spreadsheet',
    'application/vnd.google-apps.document',
    'application/vnd.google-apps.presentation',
    'text/'
]
file_fieldset = 'name,id,mimeType,modifiedTime,webViewLink,thumbnailLink,iconLink,trashed,lastModifyingUser(displayName,photoLink),owners(displayName,photoLink)'


def start_synchronization(user):
    """ Run initial syncing of user's data in external systems. Gdrive-only at the moment. """
    access_token, refresh_token = get_google_tokens(user)

    ### gdrive ###################
    # 1. Set the marker to have a reference point for later calls to gdrive changes api.
    #    Without setting this starting point, changes api won't return any changes.
    service = connect_to_gdrive(access_token, refresh_token)
    response = service.changes().getStartPageToken().execute()
    SocialAttributes.objects.update_or_create(user=user, defaults={'start_page_token': response.get('startPageToken')})

    # 2. Start the synchronization
    collect_gdrive_docs.delay(user, access_token, refresh_token)


@shared_task
def update_synchronization():
    """
    Check for new/updated files in external systems for all users. Should be called periodically after initial syncing.
    Gdrive-only at the moment.
    """
    print("Update synchronizations started")
    for sa in SocialAttributes.objects.filter(start_page_token__isnull=False):
        access_token, refresh_token = get_google_tokens(sa.user)
        subtask(sync_gdrive_changes).delay(sa.user, access_token, refresh_token, sa.start_page_token)


@shared_task
def collect_gdrive_docs(requester, access_token, refresh_token):
    print("Collecting all GDRIVE docs")

    def _call_gdrive(service, page_token):
        params = {
          'q': 'mimeType != "application/vnd.google-apps.folder"',
          'pageSize': 300,
          'fields': 'files({}),nextPageToken'.format(file_fieldset)
        }
        if page_token:
            params['pageToken'] = page_token
        return service.files().list(**params).execute()

    process_gdrive_docs(requester, access_token, refresh_token, files_fn=_call_gdrive, json_key='files')


@shared_task
def sync_gdrive_changes(requester, access_token, refresh_token, start_page_token):
    print("Collecting changed GDRIVE docs")

    def _call_gdrive(service, page_token):
        params = {
          'pageSize': 300,
          'fields': 'changes(file({})),newStartPageToken,nextPageToken'.format(file_fieldset),
          'pageToken': page_token or start_page_token,
          'spaces': 'drive',
          'includeRemoved': True,
          'restrictToMyDrive': False
        }
        return service.changes().list(**params).execute()

    new_start_page_token = process_gdrive_docs(requester, access_token, refresh_token, files_fn=_call_gdrive, json_key='changes')
    if new_start_page_token:
        SocialAttributes.objects.update_or_create(user=requester, defaults={'start_page_token': new_start_page_token})
        

def process_gdrive_docs(requester, access_token, refresh_token, files_fn, json_key):
    service = connect_to_gdrive(access_token, refresh_token)
    page_token = None
    new_start_page_token = None
    while True:
        files = files_fn(service, page_token)
        new_start_page_token = files.get('newStartPageToken', new_start_page_token)
        for item in files.get(json_key, []):
            if 'file' in item:
                item = item['file']
            if item.get('trashed'):
                # file was removed
                Document.objects.filter(document_id=item['id']).delete()
                continue

            doc, created = Document.objects.get_or_create(document_id=item['id'], requester=requester, user_id=requester.id)
            doc.title = item.get('name')
            doc.mimeType = item.get('mimeType')
            doc.webViewLink = item.get('webViewLink')
            doc.iconLink = item.get('iconLink')
            doc.thumbnailLink = item.get('thumbnailLink')
            doc.last_updated = item.get('modifiedTime')
            last_modified_on_server = parse_date(doc.last_updated)
            doc.last_updated_ts = last_modified_on_server.timestamp()
            doc.lastModifyingUser_displayName = item.get('lastModifyingUser', {}).get('displayName')
            doc.lastModifyingUser_photoLink = item.get('lastModifyingUser', {}).get('photoLink')
            doc.owner_displayName = item['owners'][0]['displayName']
            doc.owner_photoLink = item.get('owners', [{}])[0].get('photoLink')
            if not created:
                if doc.download_status is Document.READY and (doc.last_synced is None or last_modified_on_server > doc.last_synced):
                    doc.resync()
                    subtask(download_gdrive_document).delay(doc, access_token, refresh_token)
            else:
                subtask(download_gdrive_document).delay(doc, access_token, refresh_token)

            doc.save()

        page_token = files.get('nextPageToken')
        if not page_token:
            break
    return new_start_page_token


@shared_task
def download_gdrive_document(doc, access_token, refresh_token):
    if not any(x for x in exportable_mimes if doc.mimeType.startswith(x)):
        doc.download_status = Document.READY
        doc.save()
        return

    doc.download_status = Document.PROCESSING
    doc.save()

    try:
        service = connect_to_gdrive(access_token, refresh_token)
        
        request = None
        if doc.mimeType.startswith('application/vnd.google-apps.'): 
            export_mime = 'text/csv' if 'spreadsheet' in doc.mimeType else 'text/plain'
            request = service.files().export_media(fileId=doc.document_id, mimeType=export_mime)
        else:
            request = service.files().get_media(fileId=doc.document_id)
        response = request.execute()
        print("Done downloading {} [{}]".format(doc.title, doc.document_id))

        content = cutUtfString(response.decode('UTF-8'), 9000, step=10)
        doc.content = content
        utc_dt = datetime.now(timezone.utc)
        doc.last_synced = utc_dt.astimezone()
        doc.download_status = Document.READY
        doc.save()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        print("Deleting file {},{} because it couldn't be exported".format(doc.title, doc.document_id))
        doc.delete()


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

def cutUtfString(s, bytes_len_max, step=1):
    """
    Algolia has record limit of 10 kilobytes. Therefore, we need to cut file content to less than that.
    Unfortunately, there is no easy way to cut a UTF string to exact bytes length (characters may be in
    different byte sizes, i.e. usually up to 4 bytes).
    """
    # worst case, every character is 1 byte, so we first cut the string to max bytes length
    s = s[:bytes_len_max]
    l = len(s.encode('UTF-8'))
    while l > bytes_len_max:
        s = s[:-step]
        l = len(s.encode('UTF-8'))
    return s
