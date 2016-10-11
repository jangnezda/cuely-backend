#! /bin/sh


rm -rf /etc/celery_worker*.pid
rm -rf /var/log/celery_worker*.log

cd /usr/src/app

celery -A cuely --detach --logfile=/var/log/celery_worker.log --pidfile=/etc/celery_worker.pid worker --concurrency=1 --loglevel=info
# celery -A cuely --detach --logfile=/var/log/celery_beat.log --pidfile=/etc/celery_beat.pid beat --loglevel=info
sleep 5
tail -F /var/log/celery_worker.log
