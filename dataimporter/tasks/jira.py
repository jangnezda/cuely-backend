"""
Jira API integration.
"""
from jira.client import JIRA
import time
from datetime import datetime, timezone
from dateutil.parser import parse as parse_dt
from celery import shared_task

from django.conf import settings
from dataimporter.task_util import should_sync, cut_utf_string
from dataimporter.models import Document
from social.apps.django_app.default.models import UserSocialAuth
import logging
logger = logging.getLogger(__name__)

JIRA_KEYWORDS = {
    'primary': 'jira',
    'secondary': 'issue,task,bug,feature'
}


def start_synchronization(user, update=False):
    """ Run initial syncing of issues data in Jira. """
    if should_sync(user, 'jira-oauth', 'tasks.jira'):
        collect_issues.delay(requester=user, sync_update=update)
    else:
        logger.info("Jira oauth token for user '%s' already in use, skipping sync ...", user.username)


@shared_task
def update_synchronization():
    """
    Run sync/update of all users' issues data in Jira.
    Should be run periodically to keep the data fresh in our db.
    """
    for us in UserSocialAuth.objects.filter(provider='jira-oauth'):
        start_synchronization(user=us.user, update=True)


@shared_task
def collect_issues(requester, sync_update=False):
    jira = init_jira_client(requester)

    for project in jira.projects():
        project_name = project.raw.get('name')
        project_key = project.raw.get('key')
        project_url = '{}/projects/{}'.format(project._options.get('server'), project_key)
        logger.debug("Processing Jira project %s for user %s", project_key, requester.username)

        jql = 'project={}'.format(project_key)
        if sync_update:
            # only fetch those issues that were updated in the last day
            jql = "{} and updated > '-1d'".format(jql)
        i = 0
        old_i = -1
        while True:
            # manually page through results (using 'maxResults=None' should page automatically, but it doesn't work)
            if i == old_i:
                break
            old_i = i
            for issue in jira.search_issues(jql, startAt=i, maxResults=25):
                i = i + 1
                db_issue, created = Document.objects.get_or_create(
                    jira_issue_key=issue.key,
                    requester=requester,
                    user_id=requester.id
                )
                logger.debug("Processing Jira issue %s for user %s", issue.key, requester.username)
                updated = issue.fields.updated or issue.fields.created or _get_utc_timestamp()
                updated_ts = parse_dt(updated).timestamp()
                if not created and db_issue.last_updated_ts:
                    # compare timestamps and skip the deal if it hasn't been updated
                    if db_issue.last_updated_ts >= updated_ts:
                        logger.debug("Issue '%s' for user '%s' hasn't changed", issue.key, requester.username)
                        continue
                i = i + 1
                db_issue.primary_keywords = JIRA_KEYWORDS['primary']
                db_issue.secondary_keywords = JIRA_KEYWORDS['secondary']
                db_issue.last_updated = updated
                db_issue.last_updated_ts = updated_ts
                db_issue.webview_link = '{}/browse/{}'.format(project._options.get('server'), issue.key)
                db_issue.jira_issue_title = '{}: {}'.format(issue.key, issue.fields.summary)
                db_issue.jira_issue_status = issue.fields.status.name
                db_issue.jira_issue_type = issue.fields.issuetype.name
                db_issue.jira_issue_priority = issue.fields.priority.name
                if issue.fields.description:
                    db_issue.jira_issue_description = cut_utf_string(issue.fields.description, 9000, 100)
                db_issue.jira_issue_duedate = issue.fields.duedate
                db_issue.jira_issue_labels = issue.fields.labels
                db_issue.jira_issue_assignee = {
                    'name': issue.fields.assignee.displayName,
                    'avatar': issue.fields.assignee.raw.get('avatarUrls', {})
                } if issue.fields.assignee else {}
                reporter = issue.fields.reporter or issue.fields.creator
                db_issue.jira_issue_reporter = {
                    'name': reporter.displayName,
                    'avatar': reporter.raw.get('avatarUrls', {})
                }
                db_issue.jira_project_name = project_name
                db_issue.jira_project_key = project_key
                db_issue.jira_project_link = project_url
                db_issue.download_status = Document.READY
                db_issue.save()
            time.sleep(2)

        # add sleep of five seconds to avoid breaking API rate limits
        time.sleep(5)


def init_jira_client(user):
    social = user.social_auth.filter(provider='jira-oauth').first()
    if not social:
        return None

    return JIRA(
        options={'server': user.userattributes.jira_server},
        oauth={
            'access_token': social.extra_data.get('oauth_token'),
            'access_token_secret': social.extra_data.get('oauth_token_secret'),
            'consumer_key': user.userattributes.jira_consumer_key,
            'key_cert': _get_cert()
        }
    )


def _get_cert():
    path = settings.AUTH_FILES_DIR + '/jira.pem'
    cert = None
    with open(path) as f:
        cert = f.read()
    return cert


def _get_utc_timestamp():
    utc_dt = datetime.now(timezone.utc)
    return utc_dt.astimezone()
