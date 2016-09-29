from __future__ import unicode_literals

from django.apps import AppConfig
from django.contrib import algoliasearch
from dataimporter.index import DocumentIndex


class DataimporterConfig(AppConfig):
    name = 'dataimporter'

    def ready(self):
        Document = self.get_model("Document")
        algoliasearch.register(Document, DocumentIndex)
