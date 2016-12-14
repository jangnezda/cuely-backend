from django.contrib.algoliasearch import AlgoliaIndex
import os


class DocumentIndex(AlgoliaIndex):
    index_name = os.environ["ALGOLIA_INDEX_NAME"]
    settings = {
        # list of attributes that are used for searching
        'attributesToIndex': [
            'unordered(primary_keywords)',
            'unordered(secondary_keywords)',
            'unordered(title)',
            'unordered(intercom_title)',
            'unordered(pipedrive_title)',
            'unordered(helpscout_title)',
            'unordered(helpscout_document_title)',
            'unordered(jira_issue_title)',
            'owner_display_name',
            'modifier_display_name',
            'unordered(path)',
            'intercom_company',
            'intercom_email',
            'intercom_status',
            'helpscout_company',
            'helpscout_emails',
            'helpscout_mailbox',
            'helpscout_document_users.name',
            'helpscout_document_categories',
            'helpscout_document_collection',
            'helpscout_status',
            'pipedrive_deal_status',
            'helpscout_content',
            'content',
            'intercom_content',
            'pipedrive_content',
            'intercom_segments',
            'helpscout_document_content',
        ],
        # adjust ranking formula
        'ranking': [
            'typo',
            'proximity',
            'exact',
            'filters',
            'desc(last_updated_ts)',
            'attribute',
            'words'
        ]
    }
    # only following fields will be synced to Algolia
    fields = (
        # Common
        'last_updated_ts',
        'last_updated',
        'webview_link',
        'user_id',
        'requester',
        'primary_keywords',
        'secondary_keywords',

        # Document
        'document_id',
        'title',
        'content',
        'mime_type',
        'icon_link',
        'owner_display_name',
        'owner_photo_link',
        'modifier_display_name',
        'modifier_photo_link',
        'thumbnail_link',
        'path',

        # IntercomUser
        'intercom_user_id',
        'intercom_email',
        'intercom_title',
        'intercom_content',
        'intercom_session_count',
        'intercom_segments',
        'intercom_plan',
        'intercom_monthly_spend',
        'intercom_company',
        'intercom_status',

        # Pipedrive
        'pipedrive_deal_id',
        'pipedrive_title',
        'pipedrive_deal_company',
        'pipedrive_deal_value',
        'pipedrive_deal_currency',
        'pipedrive_deal_status',
        'pipedrive_deal_stage',
        'pipedrive_content',

        # Helpscout
        'helpscout_customer_id',
        'helpscout_title',
        'helpscout_name',
        'helpscout_company',
        'helpscout_emails',
        'helpscout_mailbox',
        'helpscout_mailbox_id',
        'helpscout_folder',
        'helpscout_status',
        'helpscout_assigned',
        'helpscout_content',
        'helpscout_document_id',
        'helpscout_document_title',
        'helpscout_document_collection',
        'helpscout_document_categories',
        'helpscout_document_content',
        'helpscout_document_users',
        'helpscout_document_keywords',
        'helpscout_document_status',
        'helpscout_document_public_link',

        # Jira
        'jira_issue_key',
        'jira_issue_title',
        'jira_issue_status',
        'jira_issue_type',
        'jira_issue_priority',
        'jira_issue_description',
        'jira_issue_duedate',
        'jira_issue_assignee',
        'jira_issue_reporter',
        'jira_issue_labels',
        'jira_project_name',
        'jira_project_key',
        'jira_project_link'
    )
