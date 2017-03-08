#! /bin/sh


rm -rf /etc/celery_worker*.pid
rm -rf /var/log/celery_worker*.log

cd /usr/src/app

celery -A cuely --pidfile=/etc/celery_worker.pid worker --concurrency=1 --loglevel=info -Q $1,default &
wait
