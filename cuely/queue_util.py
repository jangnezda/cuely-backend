import os
import redis


def queue_full(name, threshold=100, r=None):
    if not r:
        r = _redis()
    return r.llen(name) > threshold


def queues_full(queues, threshold=100):
    r = _redis()
    return any(queue_full(q, threshold, r) for q in queues)


def _redis():
    return redis.StrictRedis(host=os.environ['REDIS_ENDPOINT'], port=6379, db=0)
