from __future__ import unicode_literals

from django.contrib.auth.models import User
from social_django.models import UserSocialAuth
from django.db import models
from django_mysql.models import JSONField
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from dataimporter.plan import FREE


class AlgoliaIndex(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=100, blank=False, null=False, unique=True)
    settings = JSONField(default=dict)


class Team(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=100, blank=False, null=False, unique=True)
    index = models.ForeignKey(AlgoliaIndex, null=True, on_delete=models.SET_NULL)
    plan = models.CharField(max_length=100, blank=False, null=False, default=FREE['name'])
    quota_users = models.IntegerField(null=False)
    quota_objects = models.IntegerField(null=False)


class Invite(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    email = models.CharField(max_length=200, null=False)
    consumed = models.BooleanField(blank=False, null=False, default=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    code = models.CharField(max_length=100, null=True)
    expired = models.BooleanField(blank=False, null=False, default=False)


class FailedAuth(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    invite_code = models.CharField(max_length=100, null=True)
    team_name = models.CharField(max_length=100, null=True)
    error = models.CharField(max_length=500, null=False)
    email = models.CharField(max_length=200, null=True)


class SyncedObject(models.Model):
    PENDING = 1
    PROCESSING = 2
    READY = 3
    DOWNLOAD_STATUS = (
        (PENDING, 'Pending'),
        (PROCESSING, 'Processing'),
        (READY, 'Ready'),
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # team is optional (set only in case the synced object should be searchable team-wide)
    team = models.ForeignKey(Team, null=True, on_delete=models.CASCADE)
    index_name = models.CharField(max_length=100, blank=False, null=False)
    last_synced = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(null=True)
    last_updated_ts = models.BigIntegerField(null=True)
    download_status = models.IntegerField(choices=DOWNLOAD_STATUS, default=PENDING)
    primary_keywords = models.CharField(max_length=500, blank=True, null=True)
    secondary_keywords = models.CharField(max_length=500, blank=True, null=True)

    gdrive_document_id = models.CharField(max_length=200, null=True)
    gdrive_title = models.CharField(max_length=500, blank=True, null=True)
    pipedrive_deal_id = models.CharField(max_length=50, blank=True, null=True)
    pipedrive_title = models.CharField(max_length=500, blank=True, null=True)
    helpscout_customer_id = models.CharField(max_length=50, blank=True, null=True)
    helpscout_title = models.CharField(max_length=500, blank=True, null=True)
    helpscout_document_id = models.CharField(max_length=50, blank=True, null=True)
    helpscout_document_title = models.CharField(max_length=500, blank=True, null=True)
    jira_issue_key = models.CharField(max_length=50, blank=True, null=True)
    jira_issue_title = models.CharField(max_length=500, blank=True, null=True)
    github_title = models.CharField(max_length=500, blank=True, null=True)
    github_repo_id = models.CharField(max_length=50, blank=True, null=True)
    github_commit_id = models.CharField(max_length=50, blank=True, null=True)
    github_file_id = models.CharField(max_length=50, blank=True, null=True)
    github_issue_id = models.CharField(max_length=50, blank=True, null=True)
    trello_title = models.CharField(max_length=500, blank=True, null=True)
    trello_board_id = models.CharField(max_length=50, blank=True, null=True)
    trello_card_id = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return str(self.id) if self.id else "Not saved to DB"


class Integration(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=100, blank=False, null=False)
    settings = JSONField(default=dict)
    social_auth = models.OneToOneField(
        UserSocialAuth,
        on_delete=models.CASCADE,
    )

    # Set this class to abstract to avoid duplicating fields in child models.
    # Django will create a new table for every child.
    class Meta:
        abstract = True


class TeamIntegration(Integration):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='team_integrations')


class UserIntegration(Integration):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_integrations')


def get_integration(auth):
    try:
        return auth.teamintegration
    except ObjectDoesNotExist:
        try:
            return auth.userintegration
        except ObjectDoesNotExist:
            return None


class UserAttributes(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    team_admin = models.BooleanField(blank=False, null=False, default=False)
    segment_identify = models.BooleanField(blank=False, null=False, default=True)


class DeletedUser(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    user_id = models.IntegerField()
    email = models.CharField(max_length=200, blank=True, null=True)


def get_or_create(model, **filter_args):
    """ The same as built-in 'get_or_create', but it will automatically delete duplicates. """
    try:
        return model.objects.get_or_create(**filter_args)
    except MultipleObjectsReturned:
        all_objects = model.objects.filter(**filter_args)
        for obj in all_objects[1:]:
            obj.delete()
        return (all_objects[0], False)
