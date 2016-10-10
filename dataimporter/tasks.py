from __future__ import absolute_import
import sys
import traceback
from datetime import datetime, timezone
from dateutil.parser import parse as parse_date
import httplib2
import os

from apiclient import discovery
from celery import shared_task, subtask
from oauth2client.client import GoogleCredentials

from .models import Document

exportable_mimes = [
    'application/vnd.google-apps.spreadsheet',
    'application/vnd.google-apps.document',
    'application/vnd.google-apps.presentation',
    'text/'
]


@shared_task
def collect_gdrive_docs(requester, access_token, refresh_token):
    print("Collecting GDRIVE docs")
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
    page_token = None
    while True:
        param = {
          'q': 'mimeType != "application/vnd.google-apps.folder"',
          'pageSize': 300,
          'fields': 'files/name, files/id, files/mimeType, files/modifiedTime, files/webViewLink, files/thumbnailLink, files/iconLink, files/lastModifyingUser(displayName,photoLink), files/owners(displayName,photoLink), nextPageToken'
        }
        if page_token:
            param['pageToken'] = page_token
        files = service.files().list(**param).execute()
        for item in files.get('files', []):
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
                    subtask(download_gdrive_document).delay(credentials, doc)
            else:
                subtask(download_gdrive_document).delay(credentials, doc)

            doc.save()
        page_token = files.get('nextPageToken')
        if not page_token:
            break

@shared_task
def download_gdrive_document(credentials, doc):
    if not any(x for x in exportable_mimes if doc.mimeType.startswith(x)):
        doc.download_status = Document.READY
        doc.save()
        return

    doc.download_status = Document.PROCESSING
    doc.save()

    try:
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = discovery.build('drive', 'v3', http=http)
        
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


def start_synchronization(backend, user, response, *args, **kwargs):
    social = user.social_auth.get(provider='google-oauth2')
    access_token = social.extra_data['access_token']
    refresh_token = social.extra_data['refresh_token']
    collect_gdrive_docs.delay(user, access_token, refresh_token)


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
