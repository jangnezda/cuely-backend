import requests
from oauthlib.oauth1 import SIGNATURE_RSA
from requests_oauthlib import OAuth1Session

from social.backends.oauth import BaseOAuth2
from social.backends.legacy import LegacyAuth
from social.exceptions import AuthMissingParameter, AuthException
from django.conf import settings
from dataimporter.models import UserAttributes
import logging
logger = logging.getLogger(__name__)


class IntercomOauth(BaseOAuth2):
    """ Intercom OAuth authentication backend"""

    name = 'intercom-oauth'
    AUTHORIZATION_URL = 'https://app.intercom.io/oauth'
    ACCESS_TOKEN_URL = 'https://api.intercom.io/auth/eagle/token'
    ACCESS_TOKEN_METHOD = 'POST'
    EXTRA_DATA = [
        ('email', 'email'),
        ('name', 'name'),
        ('app_id', 'app_id'),
        ('app_name', 'app_name')
    ]

    def get_user_details(self, response):
        """Return user details from Intercom account"""
        return {
            'email': response.get('email') or '',
            'name': response.get('name'),
            'app_id': response.get('app', {}).get('id_code'),
            'app_name': response.get('app', {}).get('name'),
        }

    def user_data(self, access_token, *args, **kwargs):
        """Load user data from service"""
        response = requests.get(
            'https://api.intercom.io/me',
            auth=(access_token, ''),
            headers={'Accept': 'application/json'})
        response.raise_for_status()
        return response.json()


class IntercomApiKeysAuth(LegacyAuth):
    """
    Authenticate using API keys. Note that this is deprecated and scheduled for removal in January 2017.
    https://developers.intercom.com/blog/announcement-upcoming-deprecation-of-api-keys
    """
    name = 'intercom-apikeys'
    ID_KEY = 'username'
    EXTRA_DATA = ['app_id', 'api_key', 'email', 'name']

    def auth_complete(self, *args, **kwargs):
        """Completes loging process, must return user instance"""
        logger.debug("auth_complete: %s %s", self.data, kwargs)
        app_id = self.data.get('app_id')
        api_key = self.data.get('api_key')
        if not app_id:
            raise AuthMissingParameter(self, 'app_id')
        if not api_key:
            raise AuthMissingParameter(self, 'api_key')
        django_user = kwargs.get('user')
        if not django_user:
            raise AuthException(self, 'Could not get authenticated user, please login first')
        user_data = {
            'username': django_user.username,
            'email': django_user.email,
            'name': django_user.first_name + ' ' + django_user.last_name,
            'app_id': app_id.strip(),
            'api_key': api_key.strip()
        }
        kwargs.update({'response': user_data, 'backend': self})
        return self.strategy.authenticate(*args, **kwargs)


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
