"""
Github API integration. Indexing repos, repo dirs/files (not file contents), commits, issues.
"""
import time
import json
import hashlib
from github import Github
from github.GithubException import UnknownObjectException
from datetime import datetime, timezone, timedelta
from celery import shared_task, subtask
import markdown
from mdx_gfm import GithubFlavoredMarkdownExtension

from dataimporter.task_util import should_sync, should_queue, cut_utf_string, get_utc_timestamp
from dataimporter.models import Document
from dataimporter.algolia.engine import algolia_engine
from social.apps.django_app.default.models import UserSocialAuth
import logging
logger = logging.getLogger(__name__)

GITHUB_PRIMARY_KEYWORDS = 'git,github'
GITHUB_SECONDARY_KEYWORDS = {
    'repo': 'repo',
    'commit': 'commit,log',
    'issue': 'issue,ticket,task',
    'file': 'file,dir'
}


def start_synchronization(user):
    """ Run initial syncing of repo and issues data in pipedrive. """
    if should_sync(user, 'github', 'tasks.github'):
        collect_repos.delay(requester=user)
    else:
        logger.info("Github oauth token for user '%s' already in use, skipping sync ...", user.username)


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
        logger.debug("Skipping github repos sync for user '%s' due to rate limits", requester.username)
        return

    i = 0
    for repo in github_client.get_user().get_repos():
        if not (repo.id or repo.full_name):
            logger.debug("Skipping github repo '%s' for user '%s'", repo.full_name, requester.username)
            # seems like broken data, skip it
            continue
        db_repo, created = Document.objects.get_or_create(
            github_repo_id=repo.id,
            github_commit_id__isnull=True,
            github_file_id__isnull=True,
            github_issue_id__isnull=True,
            requester=requester,
            user_id=requester.id
        )
        db_repo.primary_keywords = GITHUB_PRIMARY_KEYWORDS
        db_repo.secondary_keywords = GITHUB_SECONDARY_KEYWORDS['repo']
        db_repo.github_title = 'Repo: {}'.format(repo.name)
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
        db_repo.github_repo_full_name = repo.full_name
        new_timestamp = max(repo.updated_at, repo.pushed_at)
        if created or new_timestamp.timestamp() > (db_repo.last_updated_ts or 0):
            i = i + 1
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
                md = github_client.render_markdown(text=readme_content).decode('UTF-8', errors='replace')
                # also replace <em> tags, because they are used by Algolia highlighting
                db_repo.github_repo_content = md.replace('<em>', '<b>').replace('</em>', '</b>')
                db_repo.github_repo_readme = readme.name
            except UnknownObjectException:
                # readme does not exist
                db_repo.github_repo_content = None
            algolia_engine.sync(db_repo, add=created)
            if created:
                # sync files
                subtask(collect_files).delay(
                    requester, repo.id, repo.full_name, repo.html_url, repo.default_branch, enrichment_delay=i * 300)
        # sync commits
        subtask(collect_commits).apply_async(
            args=[requester, repo.id, repo.full_name, repo.html_url, repo.default_branch, commit_count],
            countdown=240 * i if created else 1
        )
        # sync issues
        subtask(collect_issues).apply_async(
            args=[requester, repo.id, repo.full_name, created],
            countdown=180 * i if created else 1
        )

        db_repo.last_synced = get_utc_timestamp()
        db_repo.download_status = Document.READY
        db_repo.save()


@shared_task
def collect_issues(requester, repo_id, repo_name, created):
    """
    Fetch the issues for a 'repo_name'.
    Note that Github API considers Pull Requests as issues. Therefore, when iterating through
    repo's issues, we get pull requests as well. At the moment, we also treat PRs as issues.
    TODO: handle pull requests properly (changed files, commits in this PR, possibly diffs ...)
    """
    github_client = init_github_client(requester)
    # simple check if we are approaching api rate limits
    if github_client.rate_limiting[0] < 500:
        logger.debug("Skipping github issues sync for user '%s' due to rate limits", requester.username)
        return

    repo = github_client.get_repo(full_name_or_id=repo_name)
    search_args = {'state': 'all', 'sort': 'updated'}
    if not created:
        # if we are processing already synced repo, then just look for newly updated issues
        search_args['since'] = datetime.now(timezone.utc) - timedelta(hours=6)

    i = 0
    for issue in repo.get_issues(**search_args):
        db_issue, created = Document.objects.get_or_create(
            github_issue_id=issue.id,
            github_repo_id=repo_id,
            requester=requester,
            user_id=requester.id
        )
        if not created and db_issue.last_updated_ts and db_issue.last_updated_ts >= issue.updated_at.timestamp():
            continue
        logger.debug("Processing github issue #%s for user '%s' and repo '%s'",
                     issue.number, requester.username, repo_name)
        db_issue.primary_keywords = GITHUB_PRIMARY_KEYWORDS
        db_issue.secondary_keywords = GITHUB_SECONDARY_KEYWORDS['issue']
        db_issue.last_updated_ts = issue.updated_at.timestamp()
        db_issue.last_updated = issue.updated_at.isoformat() + 'Z'
        db_issue.webview_link = issue.html_url
        db_issue.github_title = '#{}: {}'.format(issue.number, issue.title)
        if '/pull/' in issue.html_url:
            # pull request
            db_issue.github_title = 'PR {}'.format(db_issue.github_title)
        comments = []
        if issue.comments > 0:
            for comment in issue.get_comments():
                comments.append({
                    'body': _to_html(comment.body),
                    'timestamp': comment.updated_at.timestamp(),
                    'author': {
                        'name': comment.user.login,
                        'avatar': comment.user.avatar_url,
                        'url': comment.user.html_url
                    }
                })
                # only list up to 20 comments
                if len(comments) >= 20:
                    break

        content = {
            'body': _to_html(issue.body),
            'comments': comments
        }
        # take care of Algolia 10k limit
        while len(json.dumps(content).encode('UTF-8')) > 9000:
            if len(content['comments']) < 1:
                content['body'] = cut_utf_string(content['body'], 9000, step=100)
                break
            content['comments'] = content['comments'][:-1]

        db_issue.github_issue_content = content
        db_issue.github_repo_full_name = repo_name
        db_issue.github_issue_state = issue.state
        db_issue.github_issue_labels = [x.name for x in issue.labels]
        db_issue.github_issue_reporter = {
            'name': issue.user.login,
            'avatar': issue.user.avatar_url,
            'url': issue.user.html_url
        }
        db_issue.github_issue_assignees = []
        for assignee in issue.assignees:
            db_issue.github_issue_assignees.append({
                'name': assignee.login,
                'avatar': assignee.avatar_url,
                'url': assignee.html_url
            })

        algolia_engine.sync(db_issue, add=created)
        db_issue.last_synced = get_utc_timestamp()
        db_issue.download_status = Document.READY
        db_issue.save()
        # add sleep every 50 issues to avoid breaking API rate limits
        i = i + 1
        if i % 50 == 0:
            time.sleep(20)


@shared_task
def collect_files(requester, repo_id, repo_name, repo_url, default_branch, enrichment_delay):
    """
    List all files in a repo - should be called once, after first sync of a repo. Subsequent syncing is handled
    via collect_commits() function.

    Note that this uses Github's API call for retrieval of recursive trees:
      https://developer.github.com/v3/git/trees/#get-a-tree-recursively
    This API call returns a flat list of all files and saves us many API calls that would be needed
    to recursively fetch files for each repo directory. But it may not work well for very big repos
    (> 5k files), becuase Github API has a limit of number of elements it will return in one call.
    """
    github_client = init_github_client(requester)
    repo = github_client.get_repo(full_name_or_id=repo_name)
    new_files = []
    for f in repo.get_git_tree(sha=repo.default_branch, recursive=True).tree:
        db_file, created = Document.objects.get_or_create(
            github_file_id=_compute_sha('{}{}'.format(repo_id, f.path)),
            github_repo_id=repo_id,
            requester=requester,
            user_id=requester.id
        )
        if created:
            new_files.append({
                'sha': f.sha,
                'filename': f.path,
                'action': 'modified',
                'type': f.type
            })
            db_file.primary_keywords = GITHUB_PRIMARY_KEYWORDS
            db_file.secondary_keywords = GITHUB_SECONDARY_KEYWORDS['file']
            # set the timestamp to 0 (epoch) to signal that we don't know the update timestamp
            db_file.last_updated_ts = 0
            db_file.last_updated = datetime.utcfromtimestamp(0).isoformat() + 'Z'
            db_file.github_title = '{}: {}'.format('Dir' if f.type == 'tree' else 'File', f.path.split('/')[-1])
            db_file.github_file_path = f.path
            db_file.github_repo_full_name = repo_name
            db_file.webview_link = '{}/blob/{}/{}'.format(repo_url, default_branch, f.path)
            algolia_engine.sync(db_file, add=created)
        db_file.last_synced = get_utc_timestamp()
        db_file.download_status = Document.PENDING
        db_file.save()
    # run enrich_files() for all new_files in chunks of 50 items
    i = 0
    for ff in [new_files[x:x + 50] for x in range(0, len(new_files), 50)]:
        i = i + 1
        subtask(enrich_files).apply_async(
            args=[requester, ff, repo.id, repo_name, repo_url, default_branch],
            countdown=enrichment_delay + (240 * i)
        )


@shared_task
def enrich_files(requester, files, repo_id, repo_name, repo_url, default_branch):
    """
    Fetch committers, update timestamp, etc. for files.
    """
    github_client = init_github_client(requester, per_page=50)
    # simple check if we are approaching api rate limits
    if github_client.rate_limiting[0] < 500:
        # reschedule after 10 minutes
        logger.debug("Skipping github enrich files for user '%s' due to rate limits", requester.username)
        subtask(enrich_files).apply_async(
            args=[requester, files, repo_id, repo_name, repo_url, default_branch],
            countdown=600
        )
        return

    repo = github_client.get_repo(full_name_or_id=repo_name)
    for f in files:
        db_file, created = Document.objects.get_or_create(
            github_file_id=_compute_sha('{}{}'.format(repo_id, f.get('filename'))),
            github_repo_id=repo_id,
            requester=requester,
            user_id=requester.id
        )
        if f.get('action') == 'removed':
            db_file.delete()
            continue

        logger.debug("Enriching github file '%s' for repo '%s' and user '%s'",
                     f.get('filename'), repo_name, requester.username)
        db_file.primary_keywords = GITHUB_PRIMARY_KEYWORDS
        db_file.secondary_keywords = GITHUB_SECONDARY_KEYWORDS['file']
        db_file.github_title = '{}: {}'.format(
            'Dir' if f.get('type') == 'tree' else 'File',
            f.get('filename').split('/')[-1]
        )
        db_file.github_file_path = f.get('filename')
        db_file.github_repo_full_name = repo_name
        db_file.webview_link = '{}/blob/{}/{}'.format(repo_url, default_branch, f.get('filename'))
        committers = []
        seen = set()
        ts_set = False
        for cmt in repo.get_commits(sha=default_branch, path=f.get('filename')):
            if not ts_set:
                db_file.last_updated_ts = cmt.commit.committer.date.timestamp()
                db_file.last_updated = cmt.commit.committer.date.isoformat() + 'Z'
                ts_set = True
            if cmt.commit.committer.name not in seen:
                c = {
                    'name': cmt.commit.committer.name
                }
                if cmt.committer:
                    c['url'] = cmt.committer.html_url
                    c['avatar'] = cmt.committer.avatar_url
                committers.append(c)
                seen.add(cmt.commit.committer.name)
            if len(committers) >= 10:
                break
        db_file.github_file_committers = committers
        algolia_engine.sync(db_file, add=created)

        db_file.last_synced = get_utc_timestamp()
        db_file.download_status = Document.READY
        db_file.save()
        # add sleep to avoid breaking API rate limits
        time.sleep(2)


@shared_task
def collect_commits(requester, repo_id, repo_name, repo_url, default_branch, commit_count):
    """
    Sync repository commits - up to the last commit that we've already synced or
    max 200 recent commits (whichever comes first).
    This is possible to do, because Github api returns commits
    sorted by commit timestamp and that old commits don't change
    (at least should not in a normally run repository).
    """
    max_commits = 200
    was_synced = Document.objects.filter(
        user_id=requester.id,
        github_repo_id=repo_id,
        github_commit_id__isnull=False).count() >= min(commit_count, max_commits)
    github_client = init_github_client(requester, per_page=20 if was_synced else 100)
    # simple check if we are approaching api rate limits
    if github_client.rate_limiting[0] < 500:
        logger.debug("Skipping github commits sync for user '%s' due to rate limits", requester.username)
        return

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
        db_commit.github_title = 'Commit: {}'.format(cmt.commit.message[:50])
        db_commit.github_commit_content = cmt.commit.message
        db_commit.github_repo_full_name = repo_name
        db_commit.github_commit_committer = {
            'name': cmt.commit.author.name,
        }
        if cmt.author:
            db_commit.github_commit_committer['url'] = cmt.author.html_url
            db_commit.github_commit_committer['avatar'] = cmt.author.avatar_url
        # get the changed/added/deleted files in this commit (up to 100 files)
        files = []
        for f in cmt.files:
            files.append({
                'sha': f.sha,
                'filename': f.filename,
                'url': f.blob_url,
                'additions': f.additions,
                'deletions': f.deletions,
                'action': f.status
            })
            if len(files) >= 100:
                break
        if was_synced and len(files) > 0:
            subtask(enrich_files).delay(requester, files, repo_id, repo_name, repo_url, default_branch)

        db_commit.github_commit_files = files
        algolia_engine.sync(db_commit, add=created)

        db_commit.last_synced = get_utc_timestamp()
        db_commit.download_status = Document.READY
        db_commit.save()
        # add sleep of half a second to avoid breaking API rate limits
        time.sleep(0.5)


def init_github_client(user, per_page=100):
    social = user.social_auth.filter(provider='github').first()
    if not social:
        return None
    oauth_token = social.extra_data['access_token']
    return Github(oauth_token, per_page=per_page)


def _to_html(markdown_text):
    if not markdown_text:
        return None
    # convert markdown to html (replace any <em> tags with bold tags, because <em> is reserved by Algolia
    md = markdown.markdown(markdown_text, extensions=[GithubFlavoredMarkdownExtension()])
    return md.replace('<em>', '<b>').replace('</em>', '</b>')


def _compute_sha(value):
    sha = hashlib.sha1()
    sha.update(bytes(value, 'utf-8'))
    return sha.hexdigest()
