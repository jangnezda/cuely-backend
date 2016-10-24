import os
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from dataimporter.models import Document, UserAttributes
from dataimporter.tasks import start_synchronization as docs_sync


def index(request):
    documents = []
    backends = []
    if request.user.is_authenticated:
        try:
            backends.append("google-oauth2")
            documents = Document.objects.filter(requester=request.user)
        except:
            pass
    return render(request, 'frontend/index.html', {"user": request.user, "documents": documents, "backends": backends})


def start_synchronization(request):
    try:
        if request.user.is_authenticated:
            docs_sync(user=request.user)
    except:
        pass
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
        ua.segment_identify = request.POST.get('identified', '0').lower() in ['1', 't', 'true', 'y', 'yes']
        ua.save()
        return JsonResponse({
            'status': 'Ok',
            'message': 'Saved segment status'
        })
    else:
        return HttpResponseForbidden()
