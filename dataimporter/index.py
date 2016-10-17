from django.contrib.algoliasearch import AlgoliaIndex
import os


class DocumentIndex(AlgoliaIndex):
    index_name = os.environ["ALGOLIA_INDEX_NAME"]
    settings = {
        # list of attributes that are used for searching
        'attributesToIndex': [
            'unordered(title)',
            'owner_displayName',
            'lastModifyingUser_displayName',
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
        'mimeType',
        'webViewLink',
        'requester',
        'user_id',
        'iconLink',
        'owner_displayName',
        'owner_photoLink',
        'lastModifyingUser_displayName',
        'lastModifyingUser_photoLink',
        'thumbnailLink',
        'path'
    )
