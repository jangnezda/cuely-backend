import os
from django.http import HttpResponseForbidden, JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from dataimporter.models import Document, UserAttributes
from dataimporter.tasks.gdrive import start_synchronization as gdrive_sync
from dataimporter.tasks.intercom import start_synchronization as intercom_sync

sync_mapping = {
    'google-oauth2': gdrive_sync,
    'intercom-oauth': intercom_sync
}


def index(request):
    backends = []
    if request.user.is_authenticated:
        for sa in request.user.social_auth.all():
            backends.append(sa.provider)

    return render(request, 'frontend/index.html', {'backends': backends})


@require_POST
def start_synchronization(request):
    if request.user.is_authenticated:
        provider = request.GET.get('provider', '').lower()
        if not provider:
            return HttpResponseBadRequest("Missing 'provider' parameter")

        auth_backend = request.user.social_auth.find(provider=provider).first()
        if not auth_backend:
            return HttpResponseBadRequest("Provider '{}' not yet authorized".format(provider))
        sync_mapping[provider](user=request.user)
    return redirect('/home/')


def sync_status(request):
    user = request.user
    if user.is_authenticated:
        documents_count = Document.objects.filter(requester=user).count()
        documents_ready_count = Document.objects.filter(requester=user).filter(download_status=Document.READY).count()
        return JsonResponse({
            "documents": documents_count,
            "ready": documents_ready_count,
            "in_progress": documents_count - documents_ready_count > 0
        })
    else:
        return HttpResponseForbidden()


def get_algolia_key(request):
    if request.user.is_authenticated:
        try:
            ua = request.user.userattributes
        except UserAttributes.DoesNotExist:
            ua = UserAttributes()
            ua.segment_identify = False
            ua.user = request.user
            ua.save()

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
