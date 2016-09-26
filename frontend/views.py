from django.shortcuts import render
from django.template import RequestContext


def index(request):
    request_context = RequestContext(request)
    return render(request, 'frontend/index.html', {"user": request.user})
