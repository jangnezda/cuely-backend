from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'update_segment/?$', views.update_segment_status),
    url(r'algolia_key/?$', views.get_algolia_key),
    url(r'sync/?$', views.start_synchronization),
    url(r'sync_status/?', views.sync_status),
    url(r'intercom_hook/?', views.intercom_callback),
    url(r'intercom_apikeys/?', views.intercom_apikeys),
    url(r'pipedrive_apikeys/?', views.pipedrive_apikeys),
    url(r'helpscout_apikeys/?', views.helpscout_apikeys),
    url(r'helpscout_docs_apikeys/?', views.helpscout_docs_apikeys),
    url(r'', views.index, name='index'),
]
