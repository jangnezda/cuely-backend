from __future__ import unicode_literals

from django.apps import AppConfig
from django.contrib import algoliasearch



class DataimporterConfig(AppConfig):
    name = 'dataimporter'

    def ready(self):
        DocumentModel = self.get_model('document')
        algoliasearch.register(DocumentModel)
