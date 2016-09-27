from __future__ import unicode_literals

from django.contrib.auth.models import User
from django.db import models

# Create your models here.
class Document(models.Model):
    PENDING = 1
    READY = 2
    DOWNLOAD_STATUS = (
        (PENDING, 'Pending'),
        (READY, 'Ready'),
    )

    document_id = models.CharField(max_length=200)
    creation_date = models.DateTimeField(blank=True, null=True)
    last_synced = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(auto_now_add=True)
    content = models.TextField(blank=True, null=True)
    size = models.IntegerField(blank=True, null=True)
    download_status = models.IntegerField(choices=DOWNLOAD_STATUS, default=PENDING)
    requester = models.ForeignKey(User)

    def resync():
        content = None;
        size = 0;
        download_status = PENDING
        print("RESYNC")
