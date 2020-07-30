import os
import requests
from urllib.parse import urljoin

AUTH0_DOMAIN = 'firstresonance.auth0.com'
API_URL = os.getenv('ION_IMPORT_API', 'https://api.firstresonance.io/')

class Api(object):
    def __init__(self, client_id, client_secret) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.audience = os.getenv('ION_API_AUDIENCE', 'https://trial-api.firstresonance.io/')

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
        return res.json()['access_token']
