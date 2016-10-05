from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.template import RequestContext

from dataimporter.models import Document
from dataimporter.tasks import collect_gdrive_docs

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
            social = request.user.social_auth.get(provider='google-oauth2')
            access_token = social.extra_data['access_token']
            refresh_token = social.extra_data['refresh_token']
            print("Collecting docs")
            collect_gdrive_docs.delay(request.user, access_token, refresh_token)
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
        return JsonResponse({
            "documents": 0,
            "ready": 0,
            "in_progress": False
        })
