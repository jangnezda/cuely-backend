import os
from datetime import datetime, timezone
from django.http import HttpResponseForbidden, JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.conf import settings

from dataimporter.models import Document, UserAttributes, DeletedUser
from dataimporter.tasks.gdrive import start_synchronization as gdrive_sync
from dataimporter.tasks.pipedrive import start_synchronization as pipedrive_sync
from dataimporter.tasks.help_scout import start_synchronization as helpscout_sync
from dataimporter.tasks.help_scout_docs import start_synchronization as helpscout_docs_sync
from dataimporter.tasks.jira import start_synchronization as jira_sync
from dataimporter.tasks.github import start_synchronization as github_sync
from dataimporter.tasks.trello import start_synchronization as trello_sync
from dataimporter.tasks.admin import purge_documents

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


def index(request):
    backends = []
    if request.user.is_authenticated:
        for sa in request.user.social_auth.all():
            backends.append(sa.provider)

    return render(request, 'frontend/index.html', {'backends': backends})


def pipedrive_apikeys(request):
    return render(request, 'frontend/pipedrive_apikeys.html', {})


def helpscout_apikeys(request):
    return render(request, 'frontend/helpscout_apikeys.html', {})


def helpscout_docs_apikeys(request):
    return render(request, 'frontend/helpscout_docs_apikeys.html', {})


def jira_oauth(request):
    return render(request, 'frontend/jira_oauth.html', {})


def auth_complete(request):
    return render(request, 'frontend/auth_complete.html', {})


@require_POST
def start_synchronization(request):
    if request.user.is_authenticated:
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


def sync_status(request):
    user = request.user
    if user.is_authenticated:
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
            'document_id__isnull': not gdrive,
            'pipedrive_deal_id__isnull': not pipedrive,
            'helpscout_customer_id__isnull': not helpscout,
            'helpscout_document_id__isnull': not helpscout_docs,
            'jira_issue_key__isnull': not jira,
            'github_repo_id__isnull': not github,
            'trello_board_id__isnull': not trello
        }
        documents_count = Document.objects.filter(**filter_args).count()
        filter_args['download_status'] = Document.READY
        documents_ready_count = Document.objects.filter(**filter_args).count()
        # to avoid premature 'integration synced' notification, check also that the
        # last synced document is at least 5 minutes old
        document_last_synced = Document.objects.filter(**filter_args).order_by('-last_synced').first()
        ts_done = False
        if document_last_synced and document_last_synced.last_synced:
            last_synced = document_last_synced.last_synced.timestamp()
            now = datetime.now(timezone.utc).astimezone().timestamp()
            ts_done = (now - last_synced) / 60.0 >= 5

        return JsonResponse({
            "documents": documents_count,
            "ready": documents_ready_count,
            "in_progress": documents_count - documents_ready_count > 0 or not ts_done,
            "has_started": documents_count > 0
        })
    else:
        return HttpResponseForbidden()


def get_algolia_key(request):
    if request.user.is_authenticated:
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
            'searchKey': request.user.userattributes.algolia_key,
            'segmentKey': os.environ['SEGMENT_KEY'],
            'segmentIdentified': ua.segment_identify,
            'integrations': integrations
        })
    else:
        return HttpResponseForbidden()


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
def update_segment_status(request):
    if request.user.is_authenticated:
        try:
            ua = request.user.userattributes
        except UserAttributes.DoesNotExist:
            ua = UserAttributes()
            ua.user = request.user
        ua.segment_identify = request.GET.get('identified', '0').lower() in ['1', 't', 'true', 'y', 'yes']
        ua.save()
        return JsonResponse({
            'status': 'Ok',
            'message': 'Saved segment status'
        })
    else:
        return HttpResponseForbidden()


@require_POST
def delete_user(request):
    if request.user.is_authenticated:
        _delete_user_internal(request.user)
        return JsonResponse({
            'status': 'Ok',
            'message': 'Removed user with id {}'.format(request.user.id)
        })
    else:
        return HttpResponseForbidden()


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
    purge_documents.delay(user, remove_user=True)
