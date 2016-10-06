from __future__ import unicode_literals

from django.contrib.auth.models import User
from django.db import models

# Create your models here.
class Document(models.Model):
    PENDING = 1
    PROCESSING = 2
    READY = 3
    DOWNLOAD_STATUS = (
        (PENDING, 'Pending'),
        (PROCESSING, 'Processing'),
        (READY, 'Ready'),
    )

    document_id = models.CharField(max_length=200)
    title = models.CharField(max_length=500, blank=True, null=True)
    last_synced = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(auto_now_add=True)
    last_updated_ts = models.BigIntegerField(null=True)
    content = models.TextField(blank=True, null=True)
    download_status = models.IntegerField(choices=DOWNLOAD_STATUS, default=PENDING)
    requester = models.ForeignKey(User)
    webViewLink = models.CharField(max_length=500, blank=True, null=True)
    iconLink = models.CharField(max_length=500, blank=True, null=True)
    thumbnailLink = models.CharField(max_length=500, blank=True, null=True)
    owner_displayName = models.CharField(max_length=200, blank=True, null=True)
    owner_photoLink = models.CharField(max_length=500, blank=True, null=True)
    lastModifyingUser_displayName = models.CharField(max_length=200, blank=True, null=True)
    lastModifyingUser_photoLink = models.CharField(max_length=500, blank=True, null=True)
    mimeType = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        if self.title:
            return self.title
        else:
            return "Untitled document"

    def resync(self):
        content = None;
        download_status = Document.PENDING
