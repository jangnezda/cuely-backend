from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'update_segment/?$', views.update_segment_status),
    url(r'algolia_key/?$', views.get_algolia_key),
    url(r'sync/?$', views.start_synchronization),
    url(r'sync_status/?', views.sync_status),
    url(r'delete_user/?', views.delete_user),
    url(r'auth_complete/.*/?', views.auth_complete),
    url(r'pipedrive_apikeys/?', views.pipedrive_apikeys),
    url(r'helpscout_apikeys/?', views.helpscout_apikeys),
    url(r'helpscout_docs_apikeys/?', views.helpscout_docs_apikeys),
    url(r'jira_oauth/?', views.jira_oauth),
    url(r'login/?', views.login, name='login'),
    url(r'', views.index, name='index'),
]
