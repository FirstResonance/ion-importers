
import os
import requests
from urllib.parse import urljoin

AUTH0_DOMAIN = 'firstresonance.auth0.com'
API_URL = os.getenv('ION_IMPORT_API', 'http://localhost:5000/')
CLIENT_ID = os.getenv('ION_IMPORTER_CLIENT_ID')
CLIENT_SECRET = os.getenv('ION_IMPORTER_CLIENT_SECRET')


def get_access_token():
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'audience': API_URL,
        'grant_type': 'client_credentials'
    }

    headers = {'content-type': 'application/json'}

    auth_url = urljoin(f'https://{AUTH0_DOMAIN}', 'oauth/token')
    res = requests.post(auth_url, json=payload, headers=headers)
    return res.json()['access_token']
