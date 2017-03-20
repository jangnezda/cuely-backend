# Cuely backend

This repo contains the code and configurations to run the backend part of Cuely service.

## Overview

Cuely is a service that indexes your cloud app accounts (Goggle Drive, Github, Trello, ...) and makes all the indexed data available in one place.
Aim is to have the searches as fast as possible, while still having a structured view of the data. Therefore, the client(s) can be made fast,
informative and showing the data that is up to date.

Cuely backend is a Python/Django app that uses MySql to store data and Redis + Celery for worker queues. Aside from using workers to sync cloud app
accounts, backend is also used for user management, oauth sessions and api for Cuely search app. Experience with Docker, Python, Django and Celery is expected
to work comfortably with the code and environemnt.

The search index is not part of the backend. Instead, [Algolia](https://www.algolia.com) is used by Cuely service. It is pretty trivial to replace Algolia
with something else here in the backend, however a lot more work needs to be done to replace this dependency in the frontend.

## Development
Please make sure that you have docker and docker-compose installed (and working). For first-time setup do the following:

1. Copy the `env-TEMPLATE` file to `.env` and fill out missing addresses, tokens, paswords.
2. Run the setup docker compose:
```
docker-compose -f docker-compose.setup.yml up build
docker-compose -f docker-compose.setup.yml up run
```
3. After all the containers have been initialized and running, one needs to run the database migrations:
```
docker exec -it cuelybackend_backend_1 ./manage.py migrate
```
4. Stop the setup environment:
```
docker-compose -f docker-compose.setup.yml stop
```

Now that the database is ready, run the dev environment:
```
docker-compose -f docker-compose.dev.yml up
```

Use django shell for quick testing and debugging:
```
docker exec -ti cuelybackend_backend_1 ./manage.py shell_plus --ipython
```

## Production
Backend and workers can be run on one instance for testing/staging/alpha/etc purposes. However, it's advisable to run backend on one instance and workers on another (or spread them out to multiple instances). This is easy to do, because they are docker images. Just remember to provide `.env` file wherever they are running.

For more complicated deploys, like load-balancing of the backend, I advise the following:
1. Deploy the backend to two instances.
2. Then deploy nginx in front of them (preferably on separate machines).
3. Then use a load balancer to route the traffic to both nginx instances.
4. Deploy the workers to separate instances, one for each integration type. So you have gdrive workers on one, trello workers on another, etc. It's then easier manage/update/scale based on what your users need the most.

This is possible, because backend doesn't hold any state, so a random request may be processed by whatever instance gets it. Any queues/workers information is offloaded to Celery which uses Redis to store the data. 
