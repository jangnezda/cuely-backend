from __future__ import absolute_import
from datetime import datetime, timezone
import httplib2
import io
import os

from apiclient import discovery
from celery import shared_task, subtask
import oauth2client
from oauth2client.client import GoogleCredentials
from oauth2client import client
from oauth2client import tools
from apiclient.http import MediaIoBaseDownload

from .models import Document

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
        'q': 'mimeType = "application/vnd.google-apps.document"',
        'fields': 'files/name, files/id, files/mimeType, files/modifiedTime, files/webViewLink, files/iconLink, files/lastModifyingUser(displayName,photoLink), files/owners(displayName,photoLink)'
      }
      if page_token:
          param['pageToken'] = page_token
      files = service.files().list(**param).execute()
      for item in files['files']:
          doc, created = Document.objects.get_or_create(document_id=item['id'], requester=requester)
          doc.title = item['name']
          doc.mimeType = item['mimeType']
          doc.webViewLink = item['webViewLink']
          doc.iconLink = item['iconLink']
          doc.lastModifyingUser_displayName = item['lastModifyingUser']['displayName']
          if 'photoLink' in item['lastModifyingUser']:
              doc.lastModifyingUser_photoLink = item['lastModifyingUser']['photoLink']
          doc.owner_displayName = item['owners'][0]['displayName']
          if 'photoLink' in item['owners'][0]:
              doc.owner_photoLink = item['owners'][0]['photoLink']
          if not created:
              last_modified_on_server = datetime.strptime(item['modifiedTime'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
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
    doc.download_status = Document.PROCESSING
    doc.save()

    http = httplib2.Http()
    http = credentials.authorize(http)
    service = discovery.build('drive', 'v3', http=http)
    request = service.files().export_media(fileId=doc.document_id,
                                                 mimeType='text/plain')
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()

    content = fh.getvalue().decode('UTF-8')
    doc.content = content
    utc_dt = datetime.now(timezone.utc)
    doc.last_synced = utc_dt.astimezone()
    doc.download_status = Document.READY
    doc.save()
