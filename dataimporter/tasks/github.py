"""
Github API integration. Indexing repos, repo dirs/files (not file contents), commits, issues.
"""
import time
from github import Github
from github.GithubException import UnknownObjectException
from datetime import datetime, timezone
from celery import shared_task

from dataimporter.task_util import should_sync, should_queue, cut_utf_string
from dataimporter.models import Document
from dataimporter.algolia.engine import algolia_engine
from social.apps.django_app.default.models import UserSocialAuth
import logging
logger = logging.getLogger(__name__)

GITHUB_KEYWORDS = {
    'primary': 'github',
    'secondary': 'repo,file,issue,commit'
}


def start_synchronization(user):
    """ Run initial syncing of repo and issues data in pipedrive. """
    if should_sync(user, 'github', 'tasks.github'):
        collect_data.delay(requester=user)
    else:
        logger.info("Github Pipedrive api key for user '%s' already in use, skipping sync ...", user.username)


@shared_task
@should_queue
def update_synchronization():
    """
    Run sync/update of all users' deals data in pipedrive.
    Should be run periodically to keep the data fresh in our db.
    """
    for us in UserSocialAuth.objects.filter(provider='github'):
        start_synchronization(user=us.user)


@shared_task
def collect_data(requester):
    github_client = init_github_client(requester)

    for repo in github_client.get_user().get_repos():
        if not (repo.id or repo.full_name):
            logger.debug("Skipping github repo '%s' for user '%s'", repo.full_name, requester.username)
            # seems like broken data, skip it
            continue
        db_repo, created = Document.objects.get_or_create(
            github_repo_id=repo.id,
            requester=requester,
            user_id=requester.id
        )
        db_repo.primary_keywords = GITHUB_KEYWORDS['primary']
        db_repo.secondary_keywords = GITHUB_KEYWORDS['secondary']
        db_repo.github_repo_title = 'Repo: {}'.format(repo.name)
        db_repo.github_repo_owner = repo.owner.login
        db_repo.github_repo_description = repo.description
        logger.debug("Processing github repo '%s' for user '%s'", repo.full_name, requester.username)
        new_timestamp = max(repo.updated_at, repo.pushed_at)
        if created or new_timestamp > (db_repo.last_updated_ts or 0):
            try:
                # fetch contributors
                contributors = []
                for cnt in repo.get_contributors():
                    contributors.append({
                        'name': cnt.name,
                        'url': cnt.html_url,
                        'avatar': cnt.avatar_url
                    })
                    if len(contributors) >= 10:
                        break
                db_repo.github_repo_contributors = contributors
            except UnknownObjectException:
                # most probably, this repo is disabled
                if created:
                    logger.debug("Removing github repo '%s' for user '%s'", repo.full_name, requester.username)
                    db_repo.delete()
                continue
            db_repo.last_updated_ts = new_timestamp.timestamp()
            db_repo.last_updated = new_timestamp.isoformat() + 'Z'
            db_repo.webview_link = repo.html_url
            # fetch readme file
            try:
                readme = repo.get_readme()
                readme_content = cut_utf_string(
                    readme.decoded_content.decode('UTF-8', errors='replace'),
                    9000,
                    step=100
                )
                db_repo.github_repo_content = github_client.render_markdown(
                    text=readme_content).decode('UTF-8', errors='replace')
                db_repo.github_repo_readme = readme.name
            except:
                # readme does not exist
                db_repo.github_repo_content = None
            algolia_engine.sync(db_repo, add=created)
            if created:
                # TODO: sync files and commits
                pass
        db_repo.last_synced = _get_utc_timestamp()
        db_repo.download_status = Document.READY
        db_repo.save()
        # add sleep of three second to avoid breaking API rate limits
        time.sleep(1)


def init_github_client(user):
    social = user.social_auth.filter(provider='github').first()
    if not social:
        return None
    oauth_token = social.extra_data['access_token']
    return Github(oauth_token)


def _get_utc_timestamp():
    utc_dt = datetime.now(timezone.utc)
    return utc_dt.astimezone()
