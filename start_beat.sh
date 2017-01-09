#!/bin/sh

# start celery 'beat' - a scheduler for periodic tasks


rm -rf /etc/celery_beat*.pid
rm -rf /var/log/celery_beat*.log

cd /usr/src/app

celery -A cuely --detach --logfile=/var/log/celery_beat.log --pidfile=/etc/celery_beat.pid beat --loglevel=info
sleep 5
tail -F /var/log/celery_beat.log
