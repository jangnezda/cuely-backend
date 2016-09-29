from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'sync/?$', views.start_synchronization),
    url(r'sync_status/?', views.sync_status),
    url(r'', views.index, name='index'),
]
