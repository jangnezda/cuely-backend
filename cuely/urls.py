"""cuely URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    url(r'^$', RedirectView.as_view(url='/home/')),
    url(r'^ping/?$', views.ping),
    url(r'^admin/', admin.site.urls),
    url(r'^home/', include('frontend.urls')),
    url(r'^accounts/profile/?$', RedirectView.as_view(url='/home/')),
    url(r'^accounts/', include('registration.backends.simple.urls')),
    url('', include('social.apps.django_app.urls', namespace='social')),
    url('', include('social.apps.django_app.urls', namespace='auth')),
    url('', include('django.contrib.auth.urls'))
]
