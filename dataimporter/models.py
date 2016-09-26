from __future__ import unicode_literals

from django.db import models

# Create your models here.
class Document(models.Model):
    document_id = models.CharField(max_length=200)
    creation_date = models.DateTimeField()
    last_updated = models.DateTimeField()
    document_type = models.CharField(max_length=100)
    content = models.TextField()
