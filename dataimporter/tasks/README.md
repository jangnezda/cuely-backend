## Tasks
Tasks in this directory contain the implementation for fetching/syncing data with external services. They are run as Celery workers. Exactly how and when they run depends on Celery settings (see configuration in `settings.py`).

One glaring hack left in these tasks is how we control rate limiting. It's done either by adding `time.sleep()` calls or rescheduling if rate limit was reached. Proper way would be to write a separate piece of code that tracks all external API calls and throttles the workers as necessary.
