from django.contrib.algoliasearch import AlgoliaIndex
import os

class DocumentIndex(AlgoliaIndex):
    index_name = os.environ["ALGOLIA_INDEX_NAME"]
