"""Import SolidWorks BOM into ION."""

import json
import argparse
from getpass import getpass
import logging
import requests
import pandas as pd
from urllib.parse import urljoin
from typing import Tuple
import sys
import os
sys.path.append(os.getcwd())
from importers import API_URL, Api # noqa
from importers import mutations # noqa

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] - [%(levelname)s] - %(message)s')
# SolidWorks assigns numerical levels starting at 1 to each part in the BOM with the
# top level part being the name of the file. We encode this part with a level of 0.
TOP_LEVEL = '0'


def _get_headers(access_token: str) -> dict:
    """
    Get headers for GraphQL API request.

    Args:
        access_token (str): Auth token to access API

    Returns:
        dict: Headers to be sent in GraphQL request.
    """
    return {'Authorization': f'{access_token}', 'Content-Type': 'application/json'}


def get_existing_parts(access_token: str, part_numbers: dict) -> Tuple[dict, dict]:
    """
    Get existing parts referenced in BOM import by querying for matching part numbers.

    Args:
        access_token (str): Auth token to access API
        part_numbers (dict): Part number to SolidWorks Part Level mapping

    Returns:
        Tuple[dict, dict]: The first dict is a mapping from SoldWorks part level to part
                           id. The second a mapping from part number to part id.
    """
    headers = _get_headers(access_token)
    query_info = {
        'query': mutations.GET_PARTS,
        'variables': {
            'filters': {'partNumber': {'in': list(part_numbers.keys())}}
        }
    }
    req_data = json.dumps(query_info)
    res = requests.post(urljoin(API_URL, 'graphql'), headers=headers, data=req_data)
    query_data = json.loads(res.text)
    part_dict = {}
    part_numbers_dict = {}
    for edge in query_data['data']['parts']['edges']:
        part_dict[part_numbers[edge['node']['partNumber']]] = edge['node']['id']
        part_numbers_dict[edge['node']['partNumber']] = edge['node']['id']
    return part_dict, part_numbers_dict


def _create_part(access_token: str, part_info: dict) -> int:
    """
    Create a new part, if BOM import references part not currently in ION.

    Args:
        access_token (str): Auth token to access API
        part_info (dict): Fields representing new part.

    Returns:
        int: ID of newly created part.
    """
    headers = _get_headers(access_token)
    query_info = {'query': mutations.CREATE_PART, 'variables': {'input': part_info}}
    req_data = json.dumps(query_info)
    res = requests.post(urljoin(API_URL, 'graphql'), headers=headers, data=req_data)
    part_data = json.loads(res.text)['data']['createPart']['part']
    return part_data['id']


def _get_parts_info(access_token: str, df: pd.DataFrame,
                    top_level_part_number: str) -> Tuple[dict, dict]:
    """
    Get information regarding all the parts to used in the BOM import.

    Args:
        access_token (str): Auth token to access API
        df (pd.DataFrame): Dataframe created by reading SolidWorks BOM export
        top_level_part_number (str): The part number of the top level part

    Returns:
        Tuple[dict, dict]: The first dict is a mapping from SoldWorks part level to part
                           id. The second a mapping from part number to part id.
    """
    index_part_number_groups = df.groupby(['Part Number', 'Level'])
    # Get mapping from part number to SolidWorks part level
    part_numbers = {idx[0][0]: idx[0][1] for idx in index_part_number_groups}
    part_numbers[top_level_part_number] = TOP_LEVEL
    # Find existing parts already in ION
    part_dict, part_numbers = get_existing_parts(access_token, part_numbers)
    # Create top level part if it does not already exist
    if top_level_part_number not in part_numbers:
        top_level_part_id = _create_part(access_token,
                                         {'partNumber': top_level_part_number})
        part_dict[TOP_LEVEL] = top_level_part_id
        part_numbers[top_level_part_number] = top_level_part_id
    return part_dict, part_numbers


def _create_mbom_item(access_token: str, row: Tuple,
                      part_dict: dict, part_numbers: dict) -> None:
    """
    Create MBOM item from row in SolidWorks BOM export.

    Args:
        access_token (str): Auth token to access API
        row (Tuple): Row from SolidWorks BOM export.
        part_dict (dict): Mapping from SolidWorks part level to part id
        part_numbers (dict): Mapping from part number to part id
    """
    headers = _get_headers(access_token)
    mbom_info = {'partId': part_numbers[row['Part Number']], 'quantity': row['Qty']}
    # BOM heirachy is defined with dot notation in SolidWorks export
    level_arr = row._name.split('.')
    # If no dot is present in BOM level, that parent ID is top level part
    parent_level = TOP_LEVEL
    # Else get parent from part level to part id dict
    if len(level_arr) > 1:
        parent_level = '.'.join(row._name.split('.')[:-1])
    mbom_info['parentId'] = part_dict[parent_level]
    query_info = {'query': mutations.CREATE_MBOM_ITEM, 'variables': {'input': mbom_info}}
    req_data = json.dumps(query_info)
    res = requests.post(urljoin(API_URL, 'graphql'), headers=headers, data=req_data)
    mbom_item = json.loads(res.text)
    # If mbom item fails to be created raise value error. Usually because of unique
    # constraint between part_id and parent_id
    if 'errors' in mbom_item:
        err = mbom_item['errors'][0]['message']
        if 'not unique' in err:
            err = (f'Failed to import BOM item {row._name} because item with part number'
                   f' {row["Part Number"]} and parent {parent_level} already exists.')
        logging.warning(err)


def _get_part_info(row: Tuple) -> dict:
    """
    Get information related to part from row in BOM export.

    Args:
        row (Tuple): Row from SolidWorks BOM export.

    Returns:
        dict: Info describing part
    """
    part_info = {'partNumber': row['Part Number']}
    if isinstance(row.Description, str):
        part_info['description'] = row.Description
    if isinstance(row.VendorNo, str):
        part_info['supplierPartNumber'] = row.VendorNo
    if isinstance(row.Revision, str) and row.Revision.isalpha():
        part_info['revision'] = row.Revision
    return part_info


def _create_mbom_items(access_token: str, df: pd.DataFrame,
                       part_dict: dict, part_numbers: dict) -> None:
    """
    Create MBOM items for every row in the SolidWorks BOM export.

    Args:
        access_token (str): Auth token to access API
        df (pd.DataFrame): Dataframe created by reading SolidWorks BOM export
        part_dict (dict): Mapping from SolidWorks part level to part id
        part_numbers (dict): Mapping from part number to part id
    """
    for idx, row in df.iterrows():
        # If part does not exist, then create part
        if row['Part Number'] not in part_numbers:
            part_info = _get_part_info(row)
            part_id = _create_part(access_token, part_info)
            part_dict[idx] = part_id
            part_numbers[row['Part Number']] = part_id
        else:
            part_dict[idx] = part_numbers[row['Part Number']]
        _create_mbom_item(access_token, row, part_dict, part_numbers)


def import_bom(api: Api, input_file: str) -> None:
    """
    Parse SolidWorks BOM export into pandas DataFrame.

    Upload each row from the excel file into ION as an MBOM item. If the part being
    referenced by the MBOM item does not exist, create that as well.

    Args:
        input_file (str): Path to SolidWorks BOM to be imported

    Returns:
        bool: Returns true if the BOM was successfully imported
    """
    # Read SolidWorks Level as string to correctly parse hierarchy.
    df = pd.read_excel(input_file, dtype={'Level': str, 'Part Number': str})
    # Use level as index
    df.set_index('Level', inplace=True)
    # Get top level part from file name
    top_level_part_number = args.input_file.split('/')[-1].split('.')[0]

    # TODO: Replace access token fetching with just using the Api object 
    # and abstract access tokens and requests from business logic
    # Get API token
    access_token = api.get_access_token()
    part_dict, part_numbers = _get_parts_info(access_token, df, top_level_part_number)
    _create_mbom_items(access_token, df, part_dict, part_numbers)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Import SolidWorks BOM exported as an excel file into ION.')
    parser.add_argument('input_file', type=str,
                        help='Path to SolidWorks BOM excel file.')
    parser.add_argument('--client_id', type=str, help='Your API client ID')
    args = parser.parse_args()
    client_secret = getpass('Client secret: ')
    if not args.client_id or not client_secret:
        raise argparse.ArgumentError('Must input client ID and client secret to run import')
    api = Api(client_id=args.client_id, client_secret=client_secret)
    import_bom(api, args.input_file)
