from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.template import RequestContext
from django.contrib.auth import authenticate
from django.http import HttpResponseForbidden

from dataimporter.models import Document
from dataimporter.tasks import collect_gdrive_docs, start_synchronization as docs_sync

def index(request):
    documents = []
    backends = []
    if request.user.is_authenticated:
        try:
            social = request.user.social_auth.get(provider='google-oauth2')
            backends.append("google-oauth2")
            access_token = social.extra_data['access_token']
            refresh_token = social.extra_data['refresh_token']
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
        documents_ready_count = Document.objects.filter(requester=user).filter(download_status = Document.READY).count()
        return JsonResponse({
            "documents": documents_count,
            "ready": documents_ready_count,
            "in_progress": documents_count - documents_ready_count > 0
        })
    else:
        return HttpResponseForbidden()


def get_algolia_key(request):
    if request.user.is_authenticated:
        return JsonResponse({
            'userid': request.user.id,
            'username': request.user.username,
            'appId': 'OPDWYH4IR4',
            'searchKey': '0b28a5913167a1618773992171c04344'
        })
    else:
        return HttpResponseForbidden()
