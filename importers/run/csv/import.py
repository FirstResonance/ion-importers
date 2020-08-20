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
    Get ids for all part numbers in the CSV.

    Args:
        api (Api): API instance to send authenticated requests
        df (pd.DataFrame): Dataframe of batch run creation CSV

    Returns:
        dict: Mapping from part number to part id
    """
    query_info = {
        'query': mutations.GET_PARTS,
        'variables': {
            'filters': {'partNumber': {'in': df['Part number'].unique().tolist()}}
        }
    }
    query_data = api.send_api_request(query_info)
    return {edge['node']['partNumber']: edge['node']['id']
            for edge in query_data['data']['parts']['edges']}


def _get_procedures(api: Api, df: pd.DataFrame) -> dict:
    """
    Get procedure titles for all procedures in the CSV.

    Args:
        api (Api): API instance to send authenticated requests
        df (pd.DataFrame): Dataframe of batch run creation CSV

    Returns:
        dict: Mapping from procedure id to procedure title
    """
    query_info = {
        'query': mutations.GET_PROCEDURES,
        'variables': {
            'filters': {'id': {'in': df['Procedure (ID)'].unique().tolist()}}
        }
    }
    query_data = api.send_api_request(query_info)
    return {edge['node']['id']: edge['node']['title']
            for edge in query_data['data']['procedures']['edges']}


def _bulk_create_part_inventories(api: Api, df: pd.DataFrame, parts_dict: dict) -> dict:
    """
    Bulk create inventory items for every unique serial and part number in CSV.

    Args:
        api (Api): API instance to send authenticated requests
        df (pd.DataFrame): Dataframe of batch run creation CSV
        parts_dict (dict): Mapping from part number to part id

    Returns:
        dict: Mapping of part/serial number tuple to newly created inventory id
    """
    create_mutations = []
    for part_info in df.groupby(['Part number', 'Serial number']).indices:
        mutation_input = {'serialNumber': part_info[1], 'quantity': 1,
                          'partId': parts_dict[part_info[0]]}
        create_mutations.append(
            {'query': mutations.CREATE_PART_INVENTORY,
             'variables': {'input': mutation_input}})
    inventories = api.send_api_request(create_mutations)
    inventory_dict = {}
    for inventory in inventories:
        item = inventory['data']['createPartInventory']['partInventory']
        inventory_dict[(item['part']['partNumber'], item['serialNumber'])] = item
    return inventory_dict


def _batch_create_runs(api: Api, df: pd.DataFrame, procedures: dict,
                       inventory_dict: dict, parts: dict) -> bool:
    """
    Batch create runs for every row in the import CSV.

    Args:
        api (Api): API instance to send authenticated requests
        df (pd.DataFrame): Dataframe of batch run creation CSV
        procedures (dict): Mapping from procedure id to procedure title
        inventory (dict): Mapping of part/serial number tuple to inventory id
        parts_dict (dict): Mapping from part number to part id

    Returns:
        bool: True if runs were successfully created.
    """
    create_mutations = []
    for _, row in df.iterrows():
        procedure_id = row['Procedure (ID)']
        inventory = inventory_dict.get((row["Part number"], row["Serial number"]), {})
        title = row['Run title (leave blank for default format*)']
        if not isinstance(title, str):
            procedure = procedures[procedure_id]
            title = f'{row["Part number"]} - {row["Serial number"]} - {procedure}'
        mutation_input = {'title': title, 'procedureId': procedure_id,
                          'partInventoryId': inventory.get('id', None),
                          'partId': parts[row['Part number']]}
        create_mutations.append(
            {'query': mutations.CREATE_RUN,
             'variables': {'input': mutation_input}})
        # CREATE ABOM TRACE FOR INVENTORY
        if inventory:
            create_mutations.append(
                {'query': mutations.CREATE_ABOM_FOR_PART_INVENTORY,
                'variables': {'id': inventory['id'], 'etag': inventory['_etag']}})
    runs = api.send_api_request(create_mutations)
    for run in runs:
        if 'errors' in run and len(run['errors']) > 0:
            logging.warning(run['errors'][0]['message'])
    return True


def import_runs(api: Api, input_file: str) -> bool:
    """
    Batch import runs and part inventory objects from CSV.

    Args:
        api (Api): API instance to send authenticated requests
        input_file (str): Location of CSV to be imported

    Returns:
        bool: True if import is successful
    """
    df = pd.read_csv(input_file, dtype={'Part number': str, 'Serial number': str})
    parts_dict = _get_parts(api, df)
    inventory_dict = _bulk_create_part_inventories(api, df, parts_dict)
    procedures_dict = _get_procedures(api, df)
    return _batch_create_runs(api, df, procedures_dict, inventory_dict, parts_dict)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Batch create runs and part inventory from CSV.')
    parser.add_argument('input_file', type=str,
                        help='Path to import CSV file.')
    parser.add_argument('--client_id', type=str, help='Your API client ID')
    args = parser.parse_args()
    client_secret = getpass('Client secret: ')
    if not args.client_id or not client_secret:
        raise argparse.ArgumentError('Must input client ID and '
                                     'client secret to run import')
    api = Api(client_id=args.client_id, client_secret=client_secret)
    import_runs(api, args.input_file)
