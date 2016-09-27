from __future__ import absolute_import
from datetime import datetime
import httplib2
import os

from apiclient import discovery
from celery import shared_task
import oauth2client
from oauth2client.client import GoogleCredentials
from oauth2client import client
from oauth2client import tools

from .models import Document

@shared_task
def collect_gdrive_docs(requester, access_token, refresh_token):
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
        'fields': 'files/name, files/id, files/mimeType, files/modifiedTime'
      }
      if page_token:
          param['pageToken'] = page_token
      files = service.files().list(**param).execute()
      for item in files['files']:
          doc, created = Document.objects.get_or_create(document_id=item['id'], requester=requester)
          if not created:
              last_modified_on_server = datetime.strptime(item['modifiedTime'], '%Y-%m-%dT%H:%M:%S.%fZ')
              if doc.download_status is not Document.PENDING and last_modified_on_server > last_synced:
                  doc.resync()
                  download_gdrive_document.delay(doc)
          else:
              download_gdrive_document.delay(doc)
          doc.save()
      page_token = files.get('nextPageToken')
      if not page_token:
          break

@shared_task
def download_gdrive_document(doc):
    print("Downloading document #" + doc.document_id)
