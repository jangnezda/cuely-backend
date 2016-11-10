from celery.task.control import inspect
from dataimporter.models import User


def get_social_data(user, provider, social_keys):
    social = user.social_auth.filter(provider=provider).first()
    if not social:
        return {}
    return {key: social.extra_data.get(key) for key in social_keys}


def get_api_creds(username, provider):
    u = User.objects.filter(username=username).first()
    if not u:
        return (None, None)
    api_data = get_social_data(u, provider, ['api_key', 'app_id'])
    return (api_data.get('app_id'), api_data.get('api_key'))


def get_active_api_keys(provider, package):
    active_tasks = inspect().active()
    active_keys = []
    for key, task_list in active_tasks.items():
        for task in (task_list or []):
            # unfortunately, celery inspect() returns arguments as string, so there has to be some hacky manipulation
            if package in task.get('name'):
                arg = next((task.get(x) for x in ['args', 'kwargs'] if '<User: ' in task.get(x)), None)
                if arg:
                    username = arg.split('<User: ')[1].split('>')[0]
                    api_key = get_api_creds(username, provider)[1]
                    if api_key:
                        active_keys.append(api_key)
    return active_keys


def should_sync(user, provider, package):
    keys = get_active_api_keys(provider, package)
    social = user.social_auth.filter(provider=provider).first()
    return social.extra_data.get('api_key') not in keys
