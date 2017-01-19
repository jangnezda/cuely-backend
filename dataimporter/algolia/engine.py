import os
from django.conf import settings
from algoliasearch import algoliasearch
from django.db.models.signals import pre_delete
from dataimporter.algolia.index import INDEX_MODEL_MAP

import logging
logger = logging.getLogger(__name__)


class AlgoliaEngineError(Exception):
    """ Something went wrong with Algolia engine. """


class AlgoliaEngine(object):
    def __init__(self, app_id=None, api_key=None):
        """ Initializes Algolia client and indexes. """
        if not app_id:
            app_id = settings.ALGOLIA['APPLICATION_ID']
            api_key = settings.ALGOLIA['API_KEY']

        self._indices = {}
        self.client = algoliasearch.Client(app_id, api_key)
        self.client.set_extra_header('User-Agent', 'Cuely Backend')
        self.existing_algolia_indexes = [x.get('name') for x in self.client.list_indexes().get('items', [])]

    def register_db_model(self, index_model):
        self._index_model = index_model
        # check for any existing indices in the DB
        for idx in index_model.objects.all():
            self.register(idx.name, idx.settings, idx.model_type)

    def register(self, index_name, index_settings, model_type):
        """ Registers the Algolia index. If the index doesn't exist yet, it will create a new one. """
        db_idx, created = self._index_model.objects.get_or_create(
            name=index_name,
            defaults={'settings': index_settings}
        )
        algolia_idx = self.client.init_index(index_name)
        if created and index_name not in self.existing_algolia_indexes:
            algolia_idx.set_settings(index_settings)

        self._indices[index_name] = (db_idx, algolia_idx, INDEX_MODEL_MAP[model_type][1])
        # Connect to the signalling for deletion
        pre_delete.connect(self._pre_delete_receiver, INDEX_MODEL_MAP[model_type][0])
        logging.info("Registered Algolia index %s", index_name)

    # Signal hook for deleting a model instance
    def _pre_delete_receiver(self, instance, **kwargs):
        """ Signal handler for when a registered model has been deleted. """
        self.get_index(instance)[0].delete_object(instance.pk)

    def reconfigure(self, index_name, new_settings):
        """ Reconfigure an existing index """
        if index_name not in self._indices:
            raise AlgoliaEngineError('{} is unknown index. Register it first!'.format(index_name))

        db_idx, algolia_idx, fields = self._indices.get(index_name, (None, None, None))
        algolia_idx.set_settings(new_settings)
        db_idx.settings = new_settings
        db_idx.save()

    def get_index(self, instance):
        # TODO: lookup index based on team_id (when teams are implemented)
        db_idx, algolia_idx, fields = self._indices.get(os.environ["ALGOLIA_INDEX_NAME"])
        return (algolia_idx, fields)

    def _build_object(self, instance, fields, with_id=False):
        """ Build the JSON object. """
        tmp = {}
        if with_id:
            tmp['objectID'] = instance.pk
        for field in fields:
            attr = getattr(instance, field)
            if callable(attr):
                attr = attr()
            tmp[field] = attr
        return tmp

    def sync(self, instance, add=True):
        idx, fields = self.get_index(instance)
        obj = self._build_object(instance, fields, not add)
        if add:
            idx.add_object(obj, instance.pk)
        else:
            idx.save_object(obj)
        logger.debug("Saved object %s to Algolia index %s", instance.pk, idx.index_name)


# Algolia engine
algolia_engine = AlgoliaEngine()
