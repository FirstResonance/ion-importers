import os
import json
import requests
from urllib.parse import urljoin

AUTH0_DOMAIN = 'firstresonance.auth0.com'
API_URL = os.getenv('ION_IMPORT_API', 'http://localhost:5000/')


class Api(object):
    def __init__(self, client_id, client_secret) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.audience = os.getenv(
            'ION_API_AUDIENCE', 'https://trial-api.firstresonance.io/')
        self.get_access_token()

    def get_access_token(self) -> str:
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'audience': self.audience,
            'grant_type': 'client_credentials'
        }

        headers = {'content-type': 'application/json'}

        auth_url = urljoin(f'https://{AUTH0_DOMAIN}', 'oauth/token')
        res = requests.post(auth_url, json=payload, headers=headers)
        self.access_token = res.json()['access_token']
        return self.access_token

    def _get_headers(self) -> dict:
        """
        Get API request headers.

        Returns:
            dict: Return API request headers with authorization token.
        """
        return {'Authorization': f'{self.access_token}',
                'Content-Type': 'application/json'}

    def send_api_request(self, query_info: dict) -> dict:
        """
        Send authenticated request to ION GraphQL API.

        Args:
            query_info (dict): Mutation or resolver request info.

        Returns:
            dict: API response from request.
        """
        headers = self._get_headers()
        req_data = json.dumps(query_info)
        res = requests.post(urljoin(API_URL, 'graphql'), headers=headers, data=req_data)
        return json.loads(res.text)
