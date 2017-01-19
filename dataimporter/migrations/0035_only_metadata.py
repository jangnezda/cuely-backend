# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2017-01-19 13:34
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dataimporter', '0034_algolia_index'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='document',
            name='content',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_assigned',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_company',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_content',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_document_categories',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_document_collection',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_document_content',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_document_keywords',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_document_public_link',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_document_status',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_document_users',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_emails',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_folder',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_mailbox',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_mailbox_id',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_name',
        ),
        migrations.RemoveField(
            model_name='document',
            name='helpscout_status',
        ),
        migrations.RemoveField(
            model_name='document',
            name='icon_link',
        ),
        migrations.RemoveField(
            model_name='document',
            name='intercom_avatar_link',
        ),
        migrations.RemoveField(
            model_name='document',
            name='intercom_company',
        ),
        migrations.RemoveField(
            model_name='document',
            name='intercom_content',
        ),
        migrations.RemoveField(
            model_name='document',
            name='intercom_email',
        ),
        migrations.RemoveField(
            model_name='document',
            name='intercom_monthly_spend',
        ),
        migrations.RemoveField(
            model_name='document',
            name='intercom_plan',
        ),
        migrations.RemoveField(
            model_name='document',
            name='intercom_segments',
        ),
        migrations.RemoveField(
            model_name='document',
            name='intercom_session_count',
        ),
        migrations.RemoveField(
            model_name='document',
            name='intercom_status',
        ),
        migrations.RemoveField(
            model_name='document',
            name='jira_issue_assignee',
        ),
        migrations.RemoveField(
            model_name='document',
            name='jira_issue_description',
        ),
        migrations.RemoveField(
            model_name='document',
            name='jira_issue_duedate',
        ),
        migrations.RemoveField(
            model_name='document',
            name='jira_issue_labels',
        ),
        migrations.RemoveField(
            model_name='document',
            name='jira_issue_priority',
        ),
        migrations.RemoveField(
            model_name='document',
            name='jira_issue_reporter',
        ),
        migrations.RemoveField(
            model_name='document',
            name='jira_issue_status',
        ),
        migrations.RemoveField(
            model_name='document',
            name='jira_issue_type',
        ),
        migrations.RemoveField(
            model_name='document',
            name='jira_project_key',
        ),
        migrations.RemoveField(
            model_name='document',
            name='jira_project_link',
        ),
        migrations.RemoveField(
            model_name='document',
            name='jira_project_name',
        ),
        migrations.RemoveField(
            model_name='document',
            name='mime_type',
        ),
        migrations.RemoveField(
            model_name='document',
            name='modifier_display_name',
        ),
        migrations.RemoveField(
            model_name='document',
            name='modifier_photo_link',
        ),
        migrations.RemoveField(
            model_name='document',
            name='owner_display_name',
        ),
        migrations.RemoveField(
            model_name='document',
            name='owner_photo_link',
        ),
        migrations.RemoveField(
            model_name='document',
            name='path',
        ),
        migrations.RemoveField(
            model_name='document',
            name='thumbnail_link',
        ),
        migrations.RemoveField(
            model_name='document',
            name='webview_link',
        ),
    ]
