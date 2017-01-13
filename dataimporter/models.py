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
    # path = models.CharField(max_length=2000, blank=True, null=True)
    path = JSONField(default=list)
    primary_keywords = models.CharField(max_length=500, blank=True, null=True)
    secondary_keywords = models.CharField(max_length=500, blank=True, null=True)
    intercom_user_id = models.CharField(max_length=200, null=True)
    intercom_email = models.CharField(max_length=200, null=True)
    intercom_title = models.CharField(max_length=500, blank=True, null=True)
    intercom_avatar_link = models.CharField(max_length=500, blank=True, null=True)
    intercom_session_count = models.IntegerField(null=True)
    intercom_segments = models.CharField(max_length=500, blank=True, null=True)
    intercom_company = models.CharField(max_length=100, blank=True, null=True)
    intercom_plan = models.CharField(max_length=100, blank=True, null=True)
    intercom_monthly_spend = models.IntegerField(null=True)
    # intercom_content = models.TextField(blank=True, null=True)
    intercom_content = JSONField(default=dict)
    intercom_status = models.CharField(max_length=50, blank=True, null=True)
    pipedrive_deal_id = models.CharField(max_length=50, blank=True, null=True)
    pipedrive_title = models.CharField(max_length=500, blank=True, null=True)
    pipedrive_deal_company = models.CharField(max_length=100, blank=True, null=True)
    pipedrive_deal_value = models.IntegerField(null=True)
    pipedrive_deal_currency = models.CharField(max_length=10, blank=True, null=True)
    pipedrive_deal_status = models.CharField(max_length=50, blank=True, null=True)
    pipedrive_deal_stage = models.CharField(max_length=100, blank=True, null=True)
    # pipedrive_content = models.TextField(blank=True, null=True)
    pipedrive_content = JSONField(default=dict)
    helpscout_customer_id = models.CharField(max_length=50, blank=True, null=True)
    helpscout_title = models.CharField(max_length=500, blank=True, null=True)
    helpscout_name = models.CharField(max_length=100, blank=True, null=True)
    helpscout_company = models.CharField(max_length=100, blank=True, null=True)
    helpscout_emails = models.CharField(max_length=500, blank=True, null=True)
    helpscout_mailbox = models.CharField(max_length=100, blank=True, null=True)
    helpscout_mailbox_id = models.CharField(max_length=50, blank=True, null=True)
    helpscout_folder = models.CharField(max_length=100, blank=True, null=True)
    helpscout_status = models.CharField(max_length=50, blank=True, null=True)
    helpscout_assigned = models.BooleanField(blank=False, null=False, default=False)
    # helpscout_content = models.TextField(blank=True, null=True)
    helpscout_content = JSONField(default=dict)
    helpscout_document_id = models.CharField(max_length=50, blank=True, null=True)
    helpscout_document_title = models.CharField(max_length=500, blank=True, null=True)
    helpscout_document_collection = models.CharField(max_length=100, blank=True, null=True)
    helpscout_document_categories = JSONField(default=list)
    helpscout_document_content = models.TextField(blank=True, null=True)
    helpscout_document_users = JSONField(default=dict)
    helpscout_document_keywords = JSONField(default=list)
    helpscout_document_status = models.CharField(max_length=50, blank=True, null=True)
    helpscout_document_public_link = models.CharField(max_length=500, blank=True, null=True)
    jira_issue_key = models.CharField(max_length=50, blank=True, null=True)
    jira_issue_title = models.CharField(max_length=500, blank=True, null=True)
    jira_issue_status = models.CharField(max_length=50, blank=True, null=True)
    jira_issue_type = models.CharField(max_length=50, blank=True, null=True)
    jira_issue_priority = models.CharField(max_length=50, blank=True, null=True)
    jira_issue_description = models.TextField(blank=True, null=True)
    jira_issue_duedate = models.DateTimeField(blank=True, null=True, auto_now_add=False)
    jira_issue_assignee = JSONField(default=dict)
    jira_issue_reporter = JSONField(default=dict)
    jira_issue_labels = JSONField(default=list)
    jira_project_name = models.CharField(max_length=500, blank=True, null=True)
    jira_project_key = models.CharField(max_length=50, blank=True, null=True)
    jira_project_link = models.CharField(max_length=500, blank=True, null=True)

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
