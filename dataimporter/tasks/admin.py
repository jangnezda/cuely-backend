"""
Admin tasks for user accounts, teams, etc.
"""
from celery import shared_task

from dataimporter.models import Document
import logging
logger = logging.getLogger(__name__)


@shared_task
def purge_documents(user, remove_user=False):
    # this can take a long time, if the user has many documents
    # reason is that for every deleted row we also call delete on Algolia index
    logger.info("Purging all documents for user %s/%s", user.id, user.username)
    Document.objects.filter(user_id=user.id).delete()
    if remove_user:
        logger.info("Deleting account for user %s/%s", user.id, user.username)
        user.delete()
