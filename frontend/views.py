from django.shortcuts import render
from django.template import RequestContext
from pprint import pprint

from dataimporter.models import Document
from dataimporter.tasks import collect_gdrive_docs

def index(request):
    print(request.user.email)
    social = request.user.social_auth.get(provider='google-oauth2')
    access_token = social.extra_data['access_token']
    refresh_token = social.extra_data['refresh_token']
    collect_gdrive_docs.delay(request.user, access_token, refresh_token)
    documents = Document.objects.filter(requester=request.user)
    return render(request, 'frontend/index.html', {"user": request.user, "documents": documents})
