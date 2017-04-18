import os
from functools import wraps
from datetime import datetime, timezone
from django.http import HttpResponseForbidden, JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.conf import settings

from dataimporter.models import SyncedObject, UserAttributes, DeletedUser, TeamIntegration, UserIntegration
from dataimporter.tasks.gdrive import start_synchronization as gdrive_sync
from dataimporter.tasks.pipedrive import start_synchronization as pipedrive_sync
from dataimporter.tasks.help_scout import start_synchronization as helpscout_sync
from dataimporter.tasks.help_scout_docs import start_synchronization as helpscout_docs_sync
from dataimporter.tasks.jira import start_synchronization as jira_sync
from dataimporter.tasks.github import start_synchronization as github_sync
from dataimporter.tasks.trello import start_synchronization as trello_sync
from dataimporter.tasks.admin import purge_objects, get_gdrive_folders, cache_gdrive_folders, is_gdrive_folders_syncing
from dataimporter.algolia.engine import algolia_engine

import logging
logger = logging.getLogger(__name__)
sync_mapping = {
    'google-oauth2': gdrive_sync,
    'pipedrive-apikeys': pipedrive_sync,
    'helpscout-apikeys': helpscout_sync,
    'helpscout-docs-apikeys': helpscout_docs_sync,
    'jira-oauth': jira_sync,
    'github': github_sync,
    'trello': trello_sync,
}


def require_user(fn):
    """ Decorator that checks if a user is logged-in. If not, then it returns 403 error code """
    @wraps(fn)
    def check_user(request, *args, **kwargs):
        if request.user.is_authenticated:
            return fn(*args, **kwargs)
        return HttpResponseForbidden()

    return check_user


def index(request, **kwargs):
    backends = []
    if request.user.is_authenticated:
        for sa in request.user.social_auth.all():
            backends.append(sa.provider)

    return render(request, 'frontend/index.html', {'backends': backends, 'error': kwargs.get('error')})


@require_user
def admin_signup(request):
    team_name = request.user.userattributes.team.name
    social_id = request.GET.get('social_id', -1)
    return render(request, 'frontend/admin_signup.html', {'team_name': team_name, 'social_id': social_id})


def login(request):
    return render(request, 'frontend/login.html')


def pipedrive_apikeys(request):
    return render(request, 'frontend/pipedrive_apikeys.html', {})


def helpscout_apikeys(request):
    return render(request, 'frontend/helpscout_apikeys.html', {})


def helpscout_docs_apikeys(request):
    return render(request, 'frontend/helpscout_docs_apikeys.html', {})


def jira_oauth(request):
    return render(request, 'frontend/jira_oauth.html', {})


@require_user
def auth_complete(request):
    signup = _param_true(request.GET.get('signup', '0'))
    if signup:
        return admin_signup(request)
    return render(request, 'frontend/auth_complete.html', {})


@require_POST
@require_user
def add_integration(request):
    social_auth = _get_social(request)
    if not social_auth:
        return HttpResponseBadRequest("Could not find matching auth data")

    excluded_folders = [x for x in request.GET.get('excluded_folders', '').split(',') if x]
    is_team = _param_true(request.GET.get('team_integration', '0'))
    integration = None
    if is_team:
        integration = TeamIntegration()
        integration.team = request.user.userattributes.team
    else:
        integration = UserIntegration()
        integration.user = request.user
    integration.social_auth = social_auth
    integration.settings = {'excluded_folders': excluded_folders}
    integration.save()
    return redirect('/home/auth_complete/{}'.format(social_auth.provider))


@require_POST
@require_user
def start_synchronization(request):
    # if google oauth, then remove segment flag to force segment re-identify
    ua = get_or_create_user_attributes(request.user)
    if ua.segment_identify:
        ua.segment_identify = False
        ua.save()

    provider = request.GET.get('provider', 'google-oauth2').lower()
    if not provider:
        return HttpResponseBadRequest("Missing 'provider' parameter")

    auth_backend = request.user.social_auth.filter(provider=provider).first()
    if not auth_backend:
        return HttpResponseBadRequest("Provider '{}' not yet authorized".format(provider))
    sync_mapping[provider](user=request.user)
    return redirect('/home/')


@require_user
def fetch_gdrive_folders(request):
    folders = get_gdrive_folders(request.user)
    if folders:
        return JsonResponse({
            'ready': True,
            'folders': [f for f in folders if not f.get('hidden', False)]
        })
    syncing = is_gdrive_folders_syncing(request.user)
    if not syncing:
        social_auth = _get_social(request)
        if not social_auth:
            return HttpResponseBadRequest("Could not find matching auth data")
        cache_gdrive_folders.delay(user=request.user, auth_id=social_auth.id)

    return JsonResponse({
        'ready': False,
        'folders': []
    })


def _get_social(request):
    sid = request.GET.get('social_id')
    return request.user.social_auth.filter(id=sid).first()


@require_user
def sync_status(request):
    user = request.user
    provider = request.GET.get('provider', 'google-oauth2').lower()
    pipedrive = 'pipedrive' in provider
    gdrive = 'google' in provider
    helpscout_docs = 'helpscout-docs' in provider
    helpscout = 'helpscout' in provider and not helpscout_docs
    jira = 'jira' in provider
    github = 'github' in provider
    trello = 'trello' in provider
    filter_args = {
        'requester': user,
        'gdrive_document_id__isnull': not gdrive,
        'pipedrive_deal_id__isnull': not pipedrive,
        'helpscout_customer_id__isnull': not helpscout,
        'helpscout_document_id__isnull': not helpscout_docs,
        'jira_issue_key__isnull': not jira,
        'github_repo_id__isnull': not github,
        'trello_board_id__isnull': not trello
    }
    objects_count = SyncedObject.objects.filter(**filter_args).count()
    filter_args['download_status'] = SyncedObject.READY
    objects_ready_count = SyncedObject.objects.filter(**filter_args).count()
    # to avoid premature 'integration synced' notification, check also that the
    # last synced object is at least 5 minutes old
    object_last_synced = SyncedObject.objects.filter(**filter_args).order_by('-last_synced').first()
    ts_done = False
    if object_last_synced and object_last_synced.last_synced:
        last_synced = object_last_synced.last_synced.timestamp()
        now = datetime.now(timezone.utc).astimezone().timestamp()
        ts_done = (now - last_synced) / 60.0 >= 5

    return JsonResponse({
        "objects": objects_count,
        "ready": objects_ready_count,
        "in_progress": objects_count - objects_ready_count > 0 or not ts_done,
        "has_started": objects_count > 0
    })


@require_user
def get_algolia_key(request):
    ua = get_or_create_user_attributes(request.user)
    integrations = []
    for sa in request.user.social_auth.all().order_by('provider'):
        sap = sa.provider
        if '-' in sap:
            sap = '-'.join(sap.split('-')[:-1])
        integrations.append(sap)

    return JsonResponse({
        'userid': request.user.id,
        'username': request.user.username,
        'name': request.user.first_name + ' ' + request.user.last_name,
        'email': request.user.email,
        'appId': settings.ALGOLIA['APPLICATION_ID'],
        'searchKey': algolia_engine.generate_new_search_key(request.user.id),
        'segmentKey': os.environ['SEGMENT_KEY'],
        'segmentIdentified': ua.segment_identify,
        'integrations': integrations
    })


def get_or_create_user_attributes(user):
    ua = None
    try:
        ua = user.userattributes
    except UserAttributes.DoesNotExist:
        ua, created = UserAttributes.objects.get_or_create(user=user)
        ua.segment_identify = False
        ua.save()
    return ua


@require_POST
@require_user
def update_segment_status(request):
    try:
        ua = request.user.userattributes
    except UserAttributes.DoesNotExist:
        ua = UserAttributes()
        ua.user = request.user
    ua.segment_identify = _param_true(request.GET.get('identified', '0'))
    ua.save()
    return JsonResponse({
        'status': 'Ok',
        'message': 'Saved segment status'
    })


@require_POST
@require_user
def delete_user(request):
    _delete_user_internal(request.user)
    return JsonResponse({
        'status': 'Ok',
        'message': 'Removed user with id {}'.format(request.user.id)
    })


def _delete_user_internal(user):
    user.is_active = False
    user.save()

    user.social_auth.all().delete()
    user.socialattributes_set.all().delete()
    user.userattributes.delete()

    du = DeletedUser()
    du.user_id = user.id
    du.email = user.email
    du.save()

    # wipe the associated documents in a separate task
    # (can take a long time, but we need to return from this function asap)
    purge_objects.delay(user, remove_user=True)


def _param_true(param):
    if not param:
        return False
    return param.lower() in ['1', 't', 'true', 'y', 'yes']
