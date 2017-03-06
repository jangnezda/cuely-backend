import os
from dataimporter.models import AlgoliaIndex, Document


class DocumentIndex(object):
    def __init__(self, name):
        self.name = name
        self.model_type = AlgoliaIndex.DOCUMENT

    fields = [
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
        'jira_project_link',

        # Github
        'github_repo_id',
        'github_title',
        'github_repo_owner',
        'github_repo_full_name',
        'github_repo_description',
        'github_repo_contributors',
        'github_repo_content',
        'github_repo_readme',
        'github_repo_commit_count',
        'github_commit_id',
        'github_commit_content',
        'github_commit_committer',
        'github_commit_files',
        'github_file_id',
        'github_file_committers',
        'github_file_path',
        'github_issue_content',
        'github_issue_state',
        'github_issue_labels',
        'github_issue_reporter',
        'github_issue_assignees',

        # Trello
        'trello_title',
        'trello_board_id',
        'trello_board_status',
        'trello_board_org',
        'trello_board_members',
        'trello_card_id',
        'trello_card_status',
        'trello_card_members',
        'trello_list',
        'trello_board_name',
        'trello_content'
    ]

    settings = {
        # list of attributes that are used for searching
        'attributesToIndex': [
            'unordered(primary_keywords)',
            'unordered(secondary_keywords)',
            'unordered(title)',
            'unordered(pipedrive_title)',
            'unordered(helpscout_title)',
            'unordered(helpscout_document_title)',
            'unordered(jira_issue_title)',
            'owner_display_name',
            'modifier_display_name',
            'unordered(path)',
            'jira_issue_key',
            'helpscout_company',
            'helpscout_emails',
            'helpscout_mailbox',
            'jira_issue_type',
            'jira_issue_priority',
            'jira_issue_labels',
            'jira_issue_assignee.name',
            'jira_issue_reporter.name',
            'helpscout_document_users.name',
            'helpscout_document_categories',
            'helpscout_document_collection',
            'helpscout_status',
            'pipedrive_deal_status',
            'pipedrive_deal_stage',
            'helpscout_content',
            'content',
            'pipedrive_content',
            'helpscout_document_content',
            'jira_issue_description'
        ],
        # adjust ranking formula
        'ranking': [
            'typo',
            'words',
            'filters',
            'exact',
            'attribute',
            'proximity'
        ],
        'customRanking': [
            'desc(last_updated_ts)'
        ],
        'allowTyposOnNumericTokens': False,
        'removeStopWords': True,
        'separatorsToIndex': '#',
        'advancedSyntax': True
    }


def index_list():
    # only auto-initialize default index (other indices are initialized dynamically
    # via DB AlgoliaIndex model)
    default_index_name = os.environ["ALGOLIA_INDEX_NAME"]
    default_index = DocumentIndex(default_index_name)
    return [default_index]

INDEX_MODEL_MAP = {
    AlgoliaIndex.DOCUMENT: (Document, DocumentIndex.fields)
}
