from __future__ import absolute_import

import os
import logging
logger = logging.getLogger(__name__)

from celery import Celery

from django.conf import settings  # noqa
from cuely.queue_util import queue_full
# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cuely.settings')

app = Celery('cuely')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

from opbeat.contrib.django.models import client, register_handlers
from opbeat.contrib.celery import register_signal

try:
    register_signal(client)
except Exception as e:
    logger.exception('Failed installing celery hook: %s' % e)

if 'opbeat.contrib.django' in settings.INSTALLED_APPS:
    register_handlers()


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))


class IntegrationsRouter(object):
    def route_for_task(self, task, args=None, kwargs=None):
        if any(task.startswith(x) for x in settings.CELERY_IMPORTS):
            queue = task.split('.')[-2]
            if queue_full(queue):
                logger.debug("Queue %s is full, routing %s to default queue", queue, task)
                return 'default'
            else:
                logger.debug("Routing %s to queue %s", task, queue)
                return queue
        logger.debug("Route for task %s not found, feeding to default queue", task)
        return 'default'
