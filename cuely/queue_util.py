import os
import redis


def queue_full(name, threshold=100):
    r = redis.StrictRedis(host=os.environ['REDIS_ENDPOINT'], port=6379, db=0)
    return r.llen(name) > threshold
