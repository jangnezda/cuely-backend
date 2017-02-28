from __future__ import unicode_literals

from django.contrib.auth.models import User
from django.db import models
from django_mysql.models import JSONField


class Document(models.Model):
    PENDING = 1
    PROCESSING = 2
    READY = 3
    DOWNLOAD_STATUS = (
        (PENDING, 'Pending'),
        (PROCESSING, 'Processing'),
        (READY, 'Ready'),
    )

    document_id = models.CharField(max_length=200, null=True)
    title = models.CharField(max_length=500, blank=True, null=True)
    last_synced = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(auto_now_add=True)
    last_updated_ts = models.BigIntegerField(null=True)
    download_status = models.IntegerField(choices=DOWNLOAD_STATUS, default=PENDING)
    requester = models.ForeignKey(User)
    user_id = models.IntegerField()
    primary_keywords = models.CharField(max_length=500, blank=True, null=True)
    secondary_keywords = models.CharField(max_length=500, blank=True, null=True)

    pipedrive_deal_id = models.CharField(max_length=50, blank=True, null=True)
    pipedrive_title = models.CharField(max_length=500, blank=True, null=True)
    pipedrive_deal_company = models.CharField(max_length=100, blank=True, null=True)
    pipedrive_deal_value = models.IntegerField(null=True)
    pipedrive_deal_currency = models.CharField(max_length=10, blank=True, null=True)
    pipedrive_deal_status = models.CharField(max_length=50, blank=True, null=True)
    pipedrive_deal_stage = models.CharField(max_length=100, blank=True, null=True)
    pipedrive_content = JSONField(default=dict)
    helpscout_customer_id = models.CharField(max_length=50, blank=True, null=True)
    helpscout_title = models.CharField(max_length=500, blank=True, null=True)
    helpscout_document_id = models.CharField(max_length=50, blank=True, null=True)
    helpscout_document_title = models.CharField(max_length=500, blank=True, null=True)
    jira_issue_key = models.CharField(max_length=50, blank=True, null=True)
    jira_issue_title = models.CharField(max_length=500, blank=True, null=True)
    github_title = models.CharField(max_length=500, blank=True, null=True)
    github_repo_id = models.CharField(max_length=50, blank=True, null=True)
    github_commit_id = models.CharField(max_length=50, blank=True, null=True)
    github_file_id = models.CharField(max_length=50, blank=True, null=True)
    github_issue_id = models.CharField(max_length=50, blank=True, null=True)
    trello_title = models.CharField(max_length=500, blank=True, null=True)
    trello_board_id = models.CharField(max_length=50, blank=True, null=True)
    trello_card_id = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return str(self.id) if self.id else "Not saved to DB"


class SocialAttributes(models.Model):
    start_page_token = models.CharField(max_length=100, blank=True, null=True)
    user = models.ForeignKey(User)


class UserAttributes(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    segment_identify = models.BooleanField(blank=False, null=False, default=True)
    jira_server = models.CharField(max_length=500, blank=True, null=True)
    jira_consumer_key = models.CharField(max_length=500, blank=True, null=True)
    jira_oauth_token = models.CharField(max_length=500, blank=True, null=True)
    jira_oauth_verifier = models.CharField(max_length=500, blank=True, null=True)
    algolia_key = models.CharField(max_length=1000, blank=True, null=True)


class DeletedUser(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    user_id = models.IntegerField()
    email = models.CharField(max_length=200, blank=True, null=True)


class AlgoliaIndex(models.Model):
    DOCUMENT = 0
    MODEL_TYPE = (
        (DOCUMENT, 'Document'),
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=100, blank=False, null=False, unique=True)
    settings = JSONField(default=dict)
    model_type = models.IntegerField(choices=MODEL_TYPE, default=DOCUMENT)
