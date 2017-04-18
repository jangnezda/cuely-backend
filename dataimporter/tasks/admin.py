"""
Admin tasks for user accounts, teams, etc.
"""
import os
import redis
import json
from celery import shared_task

from dataimporter.models import SyncedObject
from dataimporter.tasks.gdrive import fetch_folders, is_hidden_in_folder
import logging
logger = logging.getLogger(__name__)


@shared_task
def purge_objects(user, remove_user=False):
    # this can take a long time, if the user has many objects ...
    # reason is that for every deleted row we also call delete on Algolia index
    logger.info("Purging all objects for user %s/%s", user.id, user.username)
    SyncedObject.objects.filter(user_id=user.id).delete()
    if remove_user:
        logger.info("Deleting account for user %s/%s", user.id, user.username)
        user.delete()


@shared_task
def cache_gdrive_folders(user, auth_id):
    logger.info("Fetching Google Drive folders for user %s/%s", user.id, user.username)
    folders = fetch_folders(user, auth_id)
    folders = {k: v for k, v in folders.items() if not is_hidden_in_folder(k, folders)}
    logger.debug("Caching Google Drive folders for user %s/%s", user.id, user.username)
    r = _redis()
    r.set('{}_gdrive_folders'.format(user.id), json.dumps(folders), ex=600) # expire the key after 10 minutes
    r.delete('{}_gdrive_folders_caching'.format(user.id))


def get_gdrive_folders(user):
    r = _redis()
    folders = r.get('{}_gdrive_folders'.format(user.id))
    if folders:
        # check for roots, i.e. parents that don't exist
        folders = json.loads(folders.decode('utf-8'))
        for k, v in folders.items():
            if v.get('parent') not in folders:
                v['parent'] = None
        return folders.values()
    return {}


def is_gdrive_folders_syncing(user):
    r = _redis()
    flag = r.get('{}_gdrive_folders_caching'.format(user.id))
    if not flag:
        flag = True
        r.set('{}_gdrive_folders_caching'.format(user.id), flag, ex=600)
    return flag is True


def _redis():
    return redis.StrictRedis(host=os.environ['REDIS_ENDPOINT'], port=6379, db=0)
