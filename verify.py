"""Verify connection and authentication with the target API."""

import argparse
from getpass import getpass
import logging
import pandas as pd
import sys
import os
sys.path.append(os.getcwd())
from importers import Api, API_URL

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] - [%(levelname)s] - %(message)s')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Verify connection and authentication with the ion API.')
    parser.add_argument('--client_id', type=str, help='Your API client ID')
    args = parser.parse_args()
    client_secret = getpass('Client secret: ')
    if not args.client_id or not client_secret:
        raise argparse.ArgumentError('Must input client ID and client secret.')
    try:
        api = Api(client_id=args.client_id, client_secret=client_secret)
        print('Successful connection!')
        print(f'API: {API_URL}')
        print(f'Audience: {api.audience}')
        print(f'Client ID: {api.client_id}')
    except KeyError:
        raise ConnectionError('Not able to connect to API.')
