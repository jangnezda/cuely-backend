import requests
from social.backends.oauth import BaseOAuth2
from social.backends.legacy import LegacyAuth
from social.exceptions import AuthMissingParameter, AuthException
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
