from django.apps import AppConfig

import logging
logger = logging.getLogger(__name__)


class DataimporterConfig(AppConfig):
    name = 'dataimporter'
    verbose_name = "Data importer"

    def ready(self):
        try:
            from dataimporter.algolia.engine import algolia_engine
            from dataimporter.algolia.index import default_index
            # have to use name-based lookup, because models definitions
            # weren't configured/injected yet at this point
            AlgoliaIndex = self.get_model('AlgoliaIndex')
            SyncedObject = self.get_model('SyncedObject')
            name, fields, settings = default_index()
            algolia_engine.setup(AlgoliaIndex, SyncedObject, fields)
            algolia_engine.register(name, settings)
        except:
            # should not happen, except on initial Django project setup,
            # when the db models haven't been migrated yet
            logger.exception("Could not initialize Algolia Engine")
