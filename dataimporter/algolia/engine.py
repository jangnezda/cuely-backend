from django.conf import settings
from algoliasearch import algoliasearch
from django.db.models.signals import pre_delete
from datetime import datetime, timezone

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

    def setup(self, index_model, sync_model, algolia_fields):
        self._index_model = index_model
        self._sync_model = sync_model
        self._fields = algolia_fields
        # check for any existing indices in the DB
        for idx in index_model.objects.all():
            self.register(idx.name, idx.settings)

    def register(self, index_name, index_settings):
        """ Registers the Algolia index. If the index doesn't exist yet, it will create a new one. """
        db_idx, created = self._index_model.objects.get_or_create(
            name=index_name,
            defaults={'settings': index_settings}
        )
        algolia_idx = self.client.init_index(index_name)
        if created and index_name not in self.existing_algolia_indexes:
            algolia_idx.set_settings(index_settings)
            logger.info("Created new Algolia index %s", index_name)

        self._indices[index_name] = (db_idx, algolia_idx)
        # Connect to the signalling for deletion
        pre_delete.connect(self._pre_delete_receiver, self._sync_model)
        logging.info("Registered Algolia index %s", index_name)

    def generate_new_search_key(self, user_id):
        # generate a new search key that is valid only for 'user_id' and for two hours
        search_key = settings.ALGOLIA['API_SEARCH_KEY']
        return self.client.generate_secured_api_key(
            search_key,
            {
                'filters': 'user_id={}'.format(user_id),
                'restrictIndices': settings.ALGOLIA['INDEX_NAME'],
                'validUntil': int(datetime.now(timezone.utc).timestamp()) + 7200
            }
        )

    # Signal hook for deleting a model instance
    def _pre_delete_receiver(self, instance, **kwargs):
        """ Signal handler for when a registered model has been deleted. """
        self.get_index(instance)[0].delete_object(instance.pk)

    def reconfigure(self, index_name, new_settings):
        """ Reconfigure an existing index """
        if index_name not in self._indices:
            raise AlgoliaEngineError('{} is unknown index. Register it first!'.format(index_name))

        db_idx, algolia_idx = self._indices.get(index_name, (None, None))
        algolia_idx.set_settings(new_settings)
        db_idx.settings = new_settings
        db_idx.save()

    def get_index(self, instance):
        # TODO: lookup index based on team_id (when teams are implemented)
        db_idx, algolia_idx = self._indices.get(instance.index_name)
        return (algolia_idx, self._fields)

    def _build_object(self, instance, fields, with_id=False):
        """ Build the JSON object. """
        tmp = {}
        if with_id:
            tmp['objectID'] = instance.pk
        for field in [x for x in fields if hasattr(instance, x)]:
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
