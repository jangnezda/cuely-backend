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
    user_id = models.IntegerField()
    webview_link = models.CharField(max_length=500, blank=True, null=True)
    icon_link = models.CharField(max_length=500, blank=True, null=True)
    thumbnail_link = models.CharField(max_length=500, blank=True, null=True)
    owner_display_name = models.CharField(max_length=200, blank=True, null=True)
    owner_photo_link = models.CharField(max_length=500, blank=True, null=True)
    modifier_display_name = models.CharField(max_length=200, blank=True, null=True)
    modifier_photo_link = models.CharField(max_length=500, blank=True, null=True)
    mime_type = models.CharField(max_length=200, blank=True, null=True)
    path = models.CharField(max_length=2000, blank=True, null=True)
    primary_keywords = models.CharField(max_length=500, blank=True, null=True)
    secondary_keywords = models.CharField(max_length=500, blank=True, null=True)

    def __str__(self):
        if self.title:
            return self.title
        else:
            return "Untitled document"

    def resync(self):
        self.content = None
        self.download_status = Document.PENDING


class SocialAttributes(models.Model):
    start_page_token = models.CharField(max_length=100, blank=True, null=True)
    user = models.ForeignKey(User)
