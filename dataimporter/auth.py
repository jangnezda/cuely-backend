import requests
from social.backends.oauth import BaseOAuth2


class IntercomOauth(BaseOAuth2):
    """ Intercom OAuth authentication backend"""

    name = 'intercom-oauth'
    AUTHORIZATION_URL = 'https://app.intercom.io/oauth'
    ACCESS_TOKEN_URL = 'https://api.intercom.io/auth/eagle/token'
    ACCESS_TOKEN_METHOD = 'POST'

    def get_user_details(self, response):
        """Return user details from Intercom account"""
        return {'email': response.get('email') or '',
                'name': response.get('name')}

    def user_data(self, access_token, *args, **kwargs):
        """Load user data from service"""
        response = requests.get(
            'https://api.intercom.io/me',
            auth=(access_token, ''),
            headers={'Accept': 'application/json'})
        response.raise_for_status()
        return response.json()
