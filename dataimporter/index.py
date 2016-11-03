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
            'owner_display_name',
            'modifier_display_name',
            'path',
            'content',
            'intercom_content'
        ],
        # adjust ranking formula
        'ranking': [
            'typo',
            'filters',
            'proximity',
            'exact',
            'attribute',
            'desc(last_updated_ts)',
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
        'intercom_company'
    )
