from django.contrib.algoliasearch import AlgoliaIndex

class DocumentIndex(AlgoliaIndex):
    index_name = "cuely_documents"
