"""
Github API integration. Indexing repos, repo dirs/files (not file contents), commits, issues.
"""
import time
from github import Github
from github.GithubException import UnknownObjectException
from datetime import datetime, timezone
from celery import shared_task, subtask

from dataimporter.task_util import should_sync, should_queue, cut_utf_string
from dataimporter.models import Document
from dataimporter.algolia.engine import algolia_engine
from social.apps.django_app.default.models import UserSocialAuth
import logging
logger = logging.getLogger(__name__)

GITHUB_PRIMARY_KEYWORDS = 'git, github'
GITHUB_SECONDARY_KEYWORDS = {
    'repo': 'repo',
    'commit': 'commit,log',
    'issue': 'issue,ticket,task',
    'file': 'file,dir,'
}


def start_synchronization(user):
    """ Run initial syncing of repo and issues data in pipedrive. """
    if should_sync(user, 'github', 'tasks.github'):
        collect_repos.delay(requester=user)
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
def collect_repos(requester):
    github_client = init_github_client(requester)
    # simple check if we are approaching api rate limits
    if github_client.rate_limiting[0] < 500:
        logger.debug("Skipping github sync for user '%s' due to rate limits", requester.username)
        return

    for repo in github_client.get_user().get_repos():
        if not (repo.id or repo.full_name):
            logger.debug("Skipping github repo '%s' for user '%s'", repo.full_name, requester.username)
            # seems like broken data, skip it
            continue
        db_repo, created = Document.objects.get_or_create(
            github_repo_id=repo.id,
            github_commit_id__isnull=True,
            requester=requester,
            user_id=requester.id
        )
        db_repo.primary_keywords = GITHUB_PRIMARY_KEYWORDS
        db_repo.secondary_keywords = GITHUB_SECONDARY_KEYWORDS['repo']
        db_repo.github_repo_title = 'Repo: {}'.format(repo.name)
        db_repo.github_repo_owner = repo.owner.login
        db_repo.github_repo_description = repo.description
        logger.debug("Processing github repo '%s' for user '%s'", repo.full_name, requester.username)
        commit_count = 0
        contributors = []
        try:
            # fetch contributors
            for cnt in repo.get_contributors():
                commit_count = commit_count + cnt.contributions
                if len(contributors) <= 10:
                    contributors.append({
                        'name': cnt.name,
                        'url': cnt.html_url,
                        'avatar': cnt.avatar_url
                    })
        except UnknownObjectException:
            # most probably, this repo is disabled
            if created:
                logger.debug("Removing github repo '%s' for user '%s'", repo.full_name, requester.username)
                db_repo.delete()
            continue
        db_repo.github_repo_commit_count = commit_count
        db_repo.github_repo_contributors = contributors
        new_timestamp = max(repo.updated_at, repo.pushed_at)
        if created or new_timestamp.timestamp() > (db_repo.last_updated_ts or 0):
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
            except UnknownObjectException:
                # readme does not exist
                db_repo.github_repo_content = None
            algolia_engine.sync(db_repo, add=created)
        # sync commits
        subtask(collect_commits).delay(requester, repo.id, repo.full_name, commit_count)

        db_repo.last_synced = _get_utc_timestamp()
        db_repo.download_status = Document.READY
        db_repo.save()
        # add sleep of one second to avoid breaking API rate limits
        time.sleep(1)


@shared_task
def collect_commits(requester, repo_id, repo_name, commit_count):
    """
    Sync repository commits - up to the last commit that we've already synced or
    max 150 recent commits (whichever comes first).
    This is possible to do, because Github api returns commits
    sorted by commit timestamp and that old commits don't change
    (at least should not in a normally run repository).
    """
    github_client = init_github_client(requester)
    # simple check if we are approaching api rate limits
    if github_client.rate_limiting[0] < 500:
        logger.debug("Skipping github sync for user '%s' due to rate limits", requester.username)
        return
    max_commits = 200
    was_synced = Document.objects.filter(
        user_id=requester.id,
        github_repo_id=repo_id,
        github_commit_id__isnull=False).count() >= min(commit_count, max_commits)
    i = 0
    for cmt in github_client.get_repo(full_name_or_id=repo_name).get_commits():
        if i >= max_commits:
            break
        i = i + 1
        db_commit, created = Document.objects.get_or_create(
            github_commit_id=cmt.sha,
            github_repo_id=repo_id,
            requester=requester,
            user_id=requester.id
        )
        if not created and was_synced:
            logger.debug("Found already synced commit, skipping further commits syncing for user '%s' and repo '%s'",
                         requester.username, repo_name)
            break
        logger.debug("Processing github commit for user '%s' and repo '%s' with message: %s",
                     requester.username, repo_name, cmt.commit.message[:30])
        db_commit.primary_keywords = GITHUB_PRIMARY_KEYWORDS
        db_commit.secondary_keywords = GITHUB_SECONDARY_KEYWORDS['commit']
        db_commit.last_updated_ts = cmt.commit.committer.date.timestamp()
        db_commit.last_updated = cmt.commit.committer.date.isoformat() + 'Z'
        db_commit.webview_link = cmt.html_url
        db_commit.github_commit_title = 'Commit: {}'.format(cmt.commit.message[:50])
        db_commit.github_commit_content = cmt.commit.message
        db_commit.github_commit_repo_name = repo_name
        db_commit.github_commit_committer = {
            'name': cmt.commit.committer.name,
        }
        if cmt.committer:
            db_commit.github_commit_committer['url'] = cmt.committer.html_url
            db_commit.github_commit_committer['avatar'] = cmt.committer.avatar_url
        # get the changed/added files in this commit (up to 100 files)
        files = []
        for f in cmt.files:
            files.append({
                'filename': f.filename,
                'url': f.blob_url,
                'additions': f.additions,
                'deletions': f.deletions
            })
            if len(files) >= 100:
                break
        db_commit.github_commit_files = files
        algolia_engine.sync(db_commit, add=created)

        db_commit.last_synced = _get_utc_timestamp()
        db_commit.download_status = Document.READY
        db_commit.save()
        # add sleep of half a second to avoid breaking API rate limits
        time.sleep(0.5)


def init_github_client(user):
    social = user.social_auth.filter(provider='github').first()
    if not social:
        return None
    oauth_token = social.extra_data['access_token']
    return Github(oauth_token, per_page=100)


def _get_utc_timestamp():
    utc_dt = datetime.now(timezone.utc)
    return utc_dt.astimezone()
