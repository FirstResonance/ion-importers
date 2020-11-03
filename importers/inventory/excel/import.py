import argparse
from getpass import getpass
import logging
import pandas as pd
import sys
import os
sys.path.append(os.getcwd())
from importers import Api, mutations # noqa

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] - [%(levelname)s] - %(message)s')


def _get_parts(api: Api, df: pd.DataFrame) -> dict:
    """
    Get ids for all part numbers in the excel sheet.

    Args:
        api (Api): API instance to send authenticated requests
        df (pd.DataFrame): Dataframe of excel file passed in arguments

    Returns:
        dict: Mapping from part number to part id
    """
    query_info = {
        'query': mutations.GET_PARTS,
        'variables': {
            'filters': {
                'partNumber': {'in': df['Part Number'].unique().tolist()},
                'isLatestRevision': {'eq': True}}
        }
    }
    query_data = api.send_api_request(query_info)
    return {edge['node']['partNumber']: edge['node']['id']
            for edge in query_data['data']['parts']['edges']}


def _get_locations(api: Api, df: pd.DataFrame) -> dict:
    """
    Get ids for all location names in the excel sheet.

    Args:
        api (Api): API instance to send authenticated requests
        df (pd.DataFrame): Dataframe of excel file passed in arguments

    Returns:
        dict: Mapping from location name to location id
    """
    query_info = {
        'query': mutations.GET_LOCATIONS,
        'variables': {
            'filters': {
                'name': {'in': df['Location'].unique().tolist()}}
        }
    }
    query_data = api.send_api_request(query_info)
    return {edge['node']['name']: edge['node']['id']
            for edge in query_data['data']['locations']['edges']}


def _bulk_create_part_inventories(api: Api, df: pd.DataFrame, parts: dict,
                                  locations: dict) -> bool:
    """
    Bulk create inventory items for every row in excel.

    Validates that the part number the inventory object is referencing exists.

    Args:
        api (Api): API instance to send authenticated requests
        df (pd.DataFrame): Dataframe of excel file passed in arguments
        parts (dict): Mapping from part number to part id

    Returns:
        bool: True if inventory import was successful.
    """
    create_mutations = []
    for _, row in df.iterrows():
        if row['Part Number'] not in parts:
            logging.warning('Cannot create inventory because part '
                            f'{row["Part Number"]} does not exist.')
            continue
        quantity = row['Quantity'] if row['Serial Number'] is None else 1
        location = None
        if row['Location'] in locations:
            location = locations[row['Location']]
        mutation_input = {
            'serialNumber': row['Serial Number'], 'quantity': quantity,
            'partId': parts[row['Part Number']], 'lotNumber': row['Lot Number'],
            'locationId': location}
        create_mutations.append(
            {'query': mutations.CREATE_PART_INVENTORY,
             'variables': {'input': mutation_input}})
    inventories = api.send_api_request(create_mutations)
    for idx, inventory in enumerate(inventories):
        if 'errors' in inventory and len(inventory['errors']) > 0:
            logging.warning(inventory['errors'][0]['message'])
    return True


def _create_mbom(api: Api, mbom_struct: dict, parts: dict) -> bool:
    """
    Batch create MBOM items for every part in the import excel.

    Args:
        api (Api): API instance to send authenticated requests
        mbom_struct (dict): Mapping of part number to parent part and quantity
        parts (dict): Mapping from part number to part id

    Returns:
        bool: True if part import was successful.
    """
    create_mutations = []
    for part_number, mbom_item in mbom_struct.items():
        if mbom_item['parent'] in parts and part_number in parts:
            mutation_input = {
                'partId': parts[part_number], 'parentId': parts[mbom_item['parent']],
                'quantity': mbom_item['quantity']}
            create_mutations.append(
                {'query': mutations.CREATE_MBOM_ITEM,
                'variables': {'input': mutation_input}})
    mboms = api.send_api_request(create_mutations)
    for idx, mbom_item in enumerate(mboms):
        if 'errors' in mbom_item and len(mbom_item['errors']) > 0:
            logging.warning(mbom_item['errors'][0]['message'])
    return True


def _bulk_create_parts(api: Api, df: pd.DataFrame, parts: dict) -> bool:
    """
    Batch create parts for every row in the import excel.

    Args:
        api (Api): API instance to send authenticated requests
        df (pd.DataFrame): Dataframe of excel file passed in arguments
        parts (dict): Mapping from part number to part id

    Returns:
        bool: True if part import was successful.
    """
    mbom_struct = {}
    create_mutations = []
    depth = 0
    parent_part_queue = []
    parts_dict = {}
    for idx, row in df.iterrows():
        if row['Part Number'] in parts:
            logging.warning(
                f'Cannot create part {row["Part Number"]} because it already exists.')
        if row['Depth'] > depth:
            parent_part_queue.append(row["Part Number"])
        elif row['Depth'] < depth:
            parent_part_queue = parent_part_queue[:row['Depth'] - depth - 1]
            parent_part_queue.append(row["Part Number"])
        else:
            parent_part_queue[-1] = row["Part Number"]
        if len(parent_part_queue) > 1:
            mbom_struct[row['Part Number']] = {'parent': parent_part_queue[-2],
                                               'quantity': row['Quantity']}
        depth = row['Depth']
        mutation_input = {
            'partNumber': row['Part Number'], 'description': row['Description'],
            'trackingType': row['Tracking Level'].upper()}
        if row.get('Revision', None) is not None:
            mutation_input['revision'] = row.get('Revision', None)
        create_mutations.append(
            {'query': mutations.CREATE_PART, 'variables': {'input': mutation_input}})
    parts = api.send_api_request(create_mutations)
    for idx, part in enumerate(parts):
        if 'errors' in part and len(part['errors']) > 0:
            logging.warning(part['errors'][0]['message'])
        else:
            p = part['data']['createPart']['part']
            parts_dict[p['partNumber']] = p['id']
    return _create_mbom(api, mbom_struct, parts_dict)


def import_parts(api: Api, input_file: str) -> bool:
    """
    Batch import part objects from excel.

    Args:
        api (Api): API instance to send authenticated requests
        input_file (str): Location of excel file to be imported

    Returns:
        bool: True if import is successful
    """
    df = pd.read_excel(input_file, dtype={'Part Number': str})
    df = df.where(df.notnull(), None)
    parts_dict = _get_parts(api, df)
    return _bulk_create_parts(api, df, parts_dict)


def import_inventory(api: Api, input_file: str) -> bool:
    """
    Batch import inventory from excel.

    Args:
        api (Api): API instance to send authenticated requests
        input_file (str): Location of excel file to be imported

    Returns:
        bool: True if import is successful
    """
    df = pd.read_excel(input_file, dtype={'Part Number': str, 'Serial Number': str})
    df = df.where(df.notnull(), None)
    parts_dict = _get_parts(api, df)
    locations_dict = _get_locations(api, df)
    return _bulk_create_part_inventories(api, df, parts_dict, locations_dict)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Batch create parts and part inventory from Excel file.')
    parser.add_argument('input_file', type=str,
                        help='Path to import Excel file.')
    parser.add_argument('--client_id', type=str, help='Your API client ID')
    parser.add_argument(
        '--type', type=str, default='parts', choices=['parts', 'inventory'],
        help='Type of file to import either parts or inventory.')
    args = parser.parse_args()
    client_secret = getpass('Client secret: ')
    if not args.client_id or not client_secret:
        raise argparse.ArgumentError('Must input client ID and '
                                     'client secret to run import')
    api = Api(client_id=args.client_id, client_secret=client_secret)
    if args.type == 'inventory':
        import_inventory(api, args.input_file)
    else:
        import_parts(api, args.input_file)
