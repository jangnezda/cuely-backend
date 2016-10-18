from django.contrib.algoliasearch import AlgoliaIndex
import os


class DocumentIndex(AlgoliaIndex):
    index_name = os.environ["ALGOLIA_INDEX_NAME"]
    settings = {
        # list of attributes that are used for searching
        'attributesToIndex': [
            'unordered(primary_keywords)',
            'secondary_keywords',
            'unordered(title)',
            'owner_display_name',
            'modifier_display_name',
            'content',
            'path'
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
    # only following Document fields will be synced to Algolia
    fields = (
        'document_id',
        'title',
        'last_updated_ts',
        'last_updated',
        'content',
        'mime_type',
        'webview_link',
        'requester',
        'user_id',
        'icon_link',
        'owner_display_name',
        'owner_photo_link',
        'modifier_display_name',
        'modifier_photo_link',
        'thumbnail_link',
        'path',
        'primary_keywords',
        'secondary_keywords'
    )
