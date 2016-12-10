import os
import json
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from dataimporter.models import Document, UserAttributes
from dataimporter.tasks.gdrive import start_synchronization as gdrive_sync
from dataimporter.tasks.intercom import start_synchronization as intercom_sync
from dataimporter.tasks.pipedrive import start_synchronization as pipedrive_sync
from dataimporter.tasks.help_scout import start_synchronization as helpscout_sync
from dataimporter.tasks.help_scout_docs import start_synchronization as helpscout_docs_sync
from dataimporter.tasks.jira import start_synchronization as jira_sync

import logging
logger = logging.getLogger(__name__)
sync_mapping = {
    'google-oauth2': gdrive_sync,
    'intercom-oauth': intercom_sync,
    'intercom-apikeys': intercom_sync,
    'pipedrive-apikeys': pipedrive_sync,
    'helpscout-apikeys': helpscout_sync,
    'helpscout-docs-apikeys': helpscout_docs_sync,
    'jira-oauth': jira_sync
}


def index(request):
    backends = []
    if request.user.is_authenticated:
        for sa in request.user.social_auth.all():
            backends.append(sa.provider)

    return render(request, 'frontend/index.html', {'backends': backends})


def intercom_apikeys(request):
    return render(request, 'frontend/intercom_apikeys.html', {})


def pipedrive_apikeys(request):
    return render(request, 'frontend/pipedrive_apikeys.html', {})


def helpscout_apikeys(request):
    return render(request, 'frontend/helpscout_apikeys.html', {})


def helpscout_docs_apikeys(request):
    return render(request, 'frontend/helpscout_docs_apikeys.html', {})


def jira_oauth(request):
    return render(request, 'frontend/jira_oauth.html', {})


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
        intercom = 'intercom' in provider
        pipedrive = 'pipedrive' in provider
        gdrive = 'google' in provider
        helpscout_docs = 'helpscout-docs' in provider
        helpscout = 'helpscout' in provider and not helpscout_docs
        jira = 'jira' in provider
        documents_count = Document.objects.filter(
            requester=user,
            document_id__isnull=not gdrive,
            intercom_user_id__isnull=not intercom,
            pipedrive_deal_id__isnull=not pipedrive,
            helpscout_customer_id__isnull=not helpscout,
            helpscout_document_id__isnull=not helpscout_docs,
            jira_issue_key__isnull=not jira
        ).count()
        documents_ready_count = Document.objects.filter(
            requester=user,
            document_id__isnull=not gdrive,
            intercom_user_id__isnull=not intercom,
            pipedrive_deal_id__isnull=not pipedrive,
            helpscout_customer_id__isnull=not helpscout,
            helpscout_document_id__isnull=not helpscout_docs,
            jira_issue_key__isnull=not jira,
            download_status=Document.READY).count()
        return JsonResponse({
            "documents": documents_count,
            "ready": documents_ready_count,
            "in_progress": documents_count - documents_ready_count > 0,
            "has_started": documents_count > 0
        })
    else:
        return HttpResponseForbidden()


def get_algolia_key(request):
    if request.user.is_authenticated:
        ua = get_or_create_user_attributes(request.user)
        return JsonResponse({
            'userid': request.user.id,
            'username': request.user.username,
            'name': request.user.first_name + ' ' + request.user.last_name,
            'email': request.user.email,
            'appId': 'OPDWYH4IR4',
            'searchKey': '0b28a5913167a1618773992171c04344',
            'segmentKey': os.environ['SEGMENT_KEY'],
            'segmentIdentified': ua.segment_identify
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


@csrf_exempt
def intercom_callback(request):
    """
    Accept notifications from Intercom.
    Documentation: https://developers.intercom.com/v2.0/reference#webhooks-and-notifications
    """
    if 'json' not in request.META.get('CONTENT_TYPE', ''):
        return _bad_json_response()

    try:
        body = json.loads(request.body.decode("utf8"))
        logger.debug(json.dumps(body))
        return JsonResponse({
            'status': 'Ok',
            'message': 'Notification accepted'
        })
    except Exception as e:
        logger.error(e)
        # could not parse json
        return _bad_json_response()


def _bad_json_response():
    return HttpResponse(
        content="""{ "status": "Failed", "message": "Request body must be in json format" }""",
        status=400,
        content_type='application/json'
    )
