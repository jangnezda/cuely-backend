from oauthlib.oauth1 import SIGNATURE_RSA
from requests_oauthlib import OAuth1Session

from social_core.backends.legacy import LegacyAuth
from social_core.backends.trello import TrelloOAuth
from social_core.exceptions import AuthMissingParameter, AuthException
from django.conf import settings
from dataimporter.models import UserAttributes, Team, Invite, FailedAuth, AlgoliaIndex
from dataimporter.algolia.index import default_index
from dataimporter.plan import FREE, PLANS
from frontend.views import index
import logging
logger = logging.getLogger(__name__)


class PipedriveApiKeysAuth(LegacyAuth):
    """ Authentication using Pipedrive Api key. """
    name = 'pipedrive-apikeys'
    ID_KEY = 'username'
    EXTRA_DATA = ['api_key', 'email', 'name']

    def auth_complete(self, *args, **kwargs):
        """Completes loging process, must return user instance"""
        logger.debug("auth_complete: %s %s", self.data, kwargs)
        api_key = self.data.get('api_key')
        if not api_key:
            raise AuthMissingParameter(self, 'api_key')
        django_user = kwargs.get('user')
        if not django_user:
            raise AuthException(self, 'Could not get authenticated user, please login first')
        user_data = {
            'username': django_user.username,
            'email': django_user.email,
            'name': django_user.first_name + ' ' + django_user.last_name,
            'api_key': api_key.strip()
        }
        kwargs.update({'response': user_data, 'backend': self})
        return self.strategy.authenticate(*args, **kwargs)


class HelpscoutApiKeysAuth(LegacyAuth):
    """ Authentication using Helpscout Api key. """
    name = 'helpscout-apikeys'
    ID_KEY = 'username'
    EXTRA_DATA = ['api_key', 'email', 'name']

    def auth_complete(self, *args, **kwargs):
        """Completes loging process, must return user instance"""
        logger.debug("auth_complete: %s %s", self.data, kwargs)
        api_key = self.data.get('api_key')
        if not api_key:
            raise AuthMissingParameter(self, 'api_key')
        django_user = kwargs.get('user')
        if not django_user:
            raise AuthException(self, 'Could not get authenticated user, please login first')
        user_data = {
            'username': django_user.username,
            'email': django_user.email,
            'name': django_user.first_name + ' ' + django_user.last_name,
            'api_key': api_key.strip()
        }
        kwargs.update({'response': user_data, 'backend': self})
        return self.strategy.authenticate(*args, **kwargs)


class HelpscoutDocsApiKeysAuth(HelpscoutApiKeysAuth):
    """ Authentication using Helpscout Docs Api key. """
    name = 'helpscout-docs-apikeys'


class JiraOAuth(LegacyAuth):
    """ Jira's OAuth has some custom things going on: need to supply private key and Jira server address. """
    name = 'jira-oauth'
    ID_KEY = 'username'
    EXTRA_DATA = [
        ('email', 'email'),
        ('name', 'name'),
        ('oauth_token', 'oauth_token'),
        ('oauth_expires_in', 'oauth_expires_in'),
        ('oauth_authorization_expires_in', 'oauth_authorization_expires_in'),
        ('oauth_token_secret', 'oauth_token_secret'),
        ('oauth_session_handle', 'oauth_session_handle')
    ]

    def read_key(self):
        path = settings.AUTH_FILES_DIR + '/jira.pem'
        with open(path) as f:
            return f.read()

    def auth_complete(self, *args, **kwargs):
        django_user = kwargs.get('user')
        if not django_user:
            raise AuthException(self, 'Could not get authenticated user, please login first')
        jira_server = self.data.get('jira_server')
        if jira_server:
            logger.debug("Starting Jira Oauth flow for user %s", django_user.username)
            request_token_url = '{}/plugins/servlet/oauth/request-token'.format(jira_server)
            consumer_key = self.data.get('consumer_key')
            ua = UserAttributes.objects.get(user=django_user)
            ua.jira_server = jira_server
            ua.jira_consumer_key = consumer_key
            oauth = OAuth1Session(
                consumer_key,
                signature_type='auth_header',
                signature_method=SIGNATURE_RSA,
                rsa_key=self.read_key()
            )
            request_token = oauth.fetch_request_token(request_token_url)
            logger.debug("Request token is: %s", request_token)
            authorize_url = '{}/plugins/servlet/oauth/authorize?oauth_token={}'.format(
                jira_server, request_token['oauth_token'])
            ua.jira_oauth_verifier = request_token['oauth_token_secret']
            ua.jira_oauth_token = request_token['oauth_token']
            ua.save()
            logger.debug("Authorize url is: %s", authorize_url)
            return self.strategy.redirect(authorize_url)
        else:
            # assume redirect from JIRA server
            logger.debug("Completing Jira OAuth flow for user %s", django_user.username)

            ua = UserAttributes.objects.get(user=django_user)
            oauth = OAuth1Session(
                client_key=ua.jira_consumer_key,
                signature_type='auth_header',
                signature_method=SIGNATURE_RSA,
                rsa_key=self.read_key(),
                verifier=ua.jira_oauth_verifier
            )
            access_token_url = '{}/plugins/servlet/oauth/access-token?oauth_token={}'.format(
                ua.jira_server, ua.jira_oauth_token)
            access_token = oauth.fetch_access_token(access_token_url)
            logger.debug("Access token=%s", access_token)
            user_data = {
                'username': django_user.username,
                'email': django_user.email,
                'name': django_user.first_name + ' ' + django_user.last_name,
                'oauth_token': access_token.get('oauth_token'),
                'oauth_expires_in': access_token.get('oauth_expires_in'),
                'oauth_authorization_expires_in': access_token.get('oauth_authorization_expires_in'),
                'oauth_token_secret': access_token.get('oauth_token_secret'),
                'oauth_session_handle': access_token.get('oauth_session_handle')
            }
            kwargs.update({'response': user_data, 'backend': self})
            return self.strategy.authenticate(*args, **kwargs)


class TrelloOAuthFixed(TrelloOAuth):
    SCOPE_SEPARATOR = ','


def validate_auth_flow(strategy, details, *args, **kwargs):
    """
    Use this function in social auth pipeline to validate team name, invite code, etc.
    Should be used *before* a user is created in the database.
    """
    signup, signin, team_name, invite_code = _get_session_params(strategy)

    error = None
    if signup:
        if team_name:
            if Team.objects.filter(name=team_name).exists():
                error = 'Company with name {} already exists. Please choose a different name.'.format(team_name)
        else:
            if invite_code:
                invite = Invite.objects.filter(code=invite_code, consumed=False, expired=False).first()
                if invite:
                    if invite.email != details.get('email').strip():
                        error = 'Invite code is not valid for {}.'.format(details.get('email'))
                else:
                    error = 'Invalid or expired invite code.'
            else:
                error = 'Missing invite code. Please use the code from invite email and try again.'

        if error:
            return _failed_auth(error, strategy, details.get('email'), team_name, invite_code)
    return {'auth_validated': True}


def _failed_auth(error, strategy, email, team_name, invite_code):
    failed_auth = FailedAuth()
    failed_auth.team_name = team_name
    failed_auth.invite_code = invite_code
    failed_auth.error = error
    failed_auth.email = email
    failed_auth.save()
    _pop_session_params(strategy)
    return index(strategy.request, error=error)


def handle_team_integration(strategy, user, is_new, social, *args, **kwargs):
    """
    Use this function in social auth pipeline to create a new team or invited user.
    """
    signup, signin, team_name, invite_code = _pop_session_params(strategy)
    if signup:
        if not is_new:
            error = "A user with email {} already exists. Please login using the link at the bottom.".format(user.email)
            return _failed_auth(error, strategy, user.email, team_name, invite_code)

        team = None
        team_admin = False
        if team_name:
            team_admin = True

            # every team is created with default index (and later switched to dedicated for paid plans)
            index_name, _, _ = default_index()
            ai = AlgoliaIndex.objects.get(name=index_name)
            team = Team()
            team.name = team_name
            team.index = ai
            team.plan = FREE
            team.quota_users = PLANS[FREE]['users']
            team.quota_objects = PLANS[FREE]['objects']
            team.save()
        else:
            invite = Invite.objects.get(code=invite_code, consumed=False, expired=False)
            team = invite.team
            invite.consumed = True
            invite.user_id = user.id
            invite.save()

        user_attr = UserAttributes()
        user_attr.user = user
        user_attr.team = team
        user_attr.team_admin = team_admin
        user_attr.save()

    next_uri = '{}?social_id={}&in_auth_flow=y&signup={}'.format(
        strategy.session_get('next'), social.id, 'y' if signup else 'n'
    )
    logger.debug("next=%s", next_uri)
    strategy.session_set('next', next_uri)
    return {'user': user}


def _get_session_params(strategy):
    return _session_params(strategy, pop=False)


def _session_params(strategy, pop=False):
    return [
        strategy.session_pop(x) if pop else strategy.session_get(x)
        for x in ['signup', 'signin', 'team_name', 'invite_code']
    ]


def _pop_session_params(strategy):
    return _session_params(strategy, pop=True)


def _param_true(param):
    if not param:
        return False
    return param.lower() in ['1', 't', 'true', 'y', 'yes']
