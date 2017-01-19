from django.apps import AppConfig

import logging
logger = logging.getLogger(__name__)


class DataimporterConfig(AppConfig):
    name = 'dataimporter'
    verbose_name = "Data importer"

    def ready(self):
        try:
            from dataimporter.algolia.engine import algolia_engine
            from dataimporter.algolia.index import index_list
            AlgoliaIndex = self.get_model("AlgoliaIndex")
            algolia_engine.register_db_model(AlgoliaIndex)
            for idx in index_list():
                algolia_engine.register(idx.name, idx.settings, idx.model_type)
        except:
            logger.exception("Could not initialize Algolia Engine")
