#!/bin/sh

# start celery 'beat' - a scheduler for periodic tasks


rm -rf /etc/celery_beat*.pid
rm -rf /var/log/celery_beat*.log

cd /usr/src/app

celery -A cuely --pidfile=/etc/celery_beat.pid beat --loglevel=info &
wait
