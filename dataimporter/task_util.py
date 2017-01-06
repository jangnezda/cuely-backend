import os
import redis
from celery.task.control import inspect
from dataimporter.models import User


auth_fields = ['api_key', 'access_token', 'oauth_toke']


def get_social_data(user, provider, social_keys):
    social = user.social_auth.filter(provider=provider).first()
    if not social:
        return {}
    return {key: social.extra_data.get(key) for key in social_keys}


def get_api_creds(username, provider):
    u = User.objects.filter(username=username).first()
    if not u:
        return (None, None)
    api_data = get_social_data(u, provider, auth_fields)
    return filter(None, [api_data.get(x) for x in auth_fields])


def get_active_api_keys(provider, package):
    active_tasks = inspect().active()
    active_keys = []
    for key, task_list in (active_tasks.items() or []):
        for task in (task_list or []):
            # unfortunately, celery inspect() returns arguments as string, so there has to be some hacky manipulation
            if package in task.get('name'):
                arg = next((task.get(x) for x in ['args', 'kwargs'] if '<User: ' in task.get(x)), None)
                if arg:
                    username = arg.split('<User: ')[1].split('>')[0]
                    for auth_value in get_api_creds(username, provider):
                        active_keys.append(auth_value)
    return active_keys


def should_sync(user, provider, package):
    keys = get_active_api_keys(provider, package)
    social = user.social_auth.filter(provider=provider).first()
    if social:
        return not any(social.extra_data.get(x) in keys for x in auth_fields)
    else:
        return True


def queue_full(name, treshold=100):
    r = redis.StrictRedis(host=os.environ['REDIS_ENDPOINT'], port=6379, db=0)
    return r.llen(name) > treshold


def cut_utf_string(s, bytes_len_max, step=1):
    """
    Algolia has record limit of 10 kilobytes. Therefore, we need to cut file content to less than that.
    Unfortunately, there is no easy way to cut a UTF string to exact bytes length (characters may be in
    different byte sizes, i.e. usually up to 4 bytes).
    """
    # worst case, every character is 1 byte, so we first cut the string to max bytes length
    s = s[:bytes_len_max]
    l = len(s.encode('UTF-8'))
    while l > bytes_len_max:
        s = s[:-step]
        l = len(s.encode('UTF-8'))
    return s
