"""Import transformed inventory CSV into ION using the ION API."""

import re
import sys
import os
import json
import argparse
import requests
import pandas as pd
from urllib.parse import urljoin
sys.path.append(os.getcwd())
from importers import get_access_token, API_URL # noqa
from importers import mutations # noqa

# Compiled regular expression to convert camel case to snake case
to_snake_case = re.compile(r'(?<!^)(?=[A-Z])')

# Unique identifiers for object types
type_identifiers = {
    'location': lambda v: v.get('name'),
    'part': lambda v: v.get('partNumber'),
    'unit_of_measurement': lambda v: v.get('type'),
}

# Columns that are to be filled in by cached API responses
cache_ids = {
    'locationId': 'location',
    'unitOfMeasureId': 'unit_of_measurement',
    'partId': 'part',
}


def update_cache(resp_data: dict, cache: dict) -> dict:
    """
    Returns import cache updated with responses from an API request response.

    Args:
        resp_data (dict): API response dict
        cache (dict): Import cache

    Returns:
        dict: Cache filled with new entries from response
    """
    for item in resp_data:
        for operation in item['data'].values():
            for return_type, return_item in operation.items():
                cache_type = to_snake_case.sub('_', return_type).lower()
                if cache_type not in cache:
                    cache[cache_type] = {}
                obj_identifier = type_identifiers[cache_type](return_item)
                cache[cache_type][obj_identifier] = return_item
    return cache


def fill_from_cache(to_upload: dict, cache: dict, to_fill: list) -> dict:
    """
    Fill upload dictionary with cached foreign key values returned from the API.

    Args:
        to_upload (dict): Dict of objects to be uploaded
        cache (dict): Dict of responses from API
        to_fill (list): List of object types to update with cached info

    Returns:
        dict: Dict of objects to be uploaded with fk values filled from cache
    """
    for object_type in to_fill:
        for item in to_upload[object_type]:
            for id_field in cache_ids:
                if id_field in item:
                    item[id_field] = cache[cache_ids[id_field]][item[id_field]]['id']
    return to_upload


def _get_attr_from_df(df: object, field_name: str) -> str:
    """Get an attribute from a dataframe."""
    vals = df[field_name][(df[field_name].isna() == False) & # noqa
                          (df[field_name] != '')].array
    if len(vals) > 0:
        return vals[0]
    return None


def _create_part_inventory(part_number: str, grouping: tuple,
                           part_inventory_df: object) -> dict:
    """Create part inventory dict to be uploaded."""
    part_inventory = {'partId': part_number}
    part_inventory['unitOfMeasureId'] = _get_attr_from_df(part_inventory_df, 'uom')
    part_inventory['cost'] = _get_attr_from_df(part_inventory_df, 'cost')
    part_inventory['quantity'] = _get_attr_from_df(part_inventory_df, 'quantity')
    part_inventory['locationId'] = grouping[0]
    part_inventory['lotNumber'] = grouping[1] if grouping[1] != '' else None
    part_inventory['serialNumber'] = grouping[2] if grouping[2] != '' else None
    return part_inventory


def _get_inventory_groups(part_number: str, part_df: object, to_upload: dict) -> dict:
    """Get all part inventory objects for a specific part number."""
    part_df['serial_number'].fillna(value='', inplace=True)
    part_df['lot_number'].fillna(value='', inplace=True)
    part_inventory = part_df[part_df.quantity.isna() == False] # noqa
    part_inventory_groups = part_inventory.groupby(['location_name', 'lot_number',
                                                    'serial_number'])
    for group_idx, part_inventory_df in part_inventory_groups:
        inventory = _create_part_inventory(
            part_number=part_number, grouping=group_idx,
            part_inventory_df=part_inventory_df)
        to_upload['parts_inventories'].append(inventory)
    return to_upload


def create_upload_items(df: object, to_upload: dict) -> dict:
    """
    Create parts, part lots, part inventories, and part instances objects to be uploaded.

    Args:
        df (object): Dataframe of CSV data.
        to_upload (dict): Dictionary of things to be uploaded.

    Returns:
        dict: Filled dictionary of things to be uploaded.
    """
    parts_df = df.groupby(['part_number'])
    for part_number, part_df in parts_df:
        part = {'partNumber': part_number}
        part['description'] = _get_attr_from_df(part_df, 'part_description')
        to_upload['parts'].append(part)
        # Get all inventory objects for a part
        to_upload = _get_inventory_groups(part_number=part_number, part_df=part_df,
                                          to_upload=to_upload)
    return to_upload


def get_upload_dict(df: object) -> dict:
    """
    Get dict of objects to be uploaded.

    Fill dict with unique values for units of measurement and locations.
    """
    return {
        'uoms': [{'type': uom} for uom in df.uom[df.uom.isna() == False].unique()], # noqa
        'locations': [{'name': loc} for loc in
                      df.location_name[df.location_name.isna() == False].unique()], # noqa
        'parts': [],
        'parts_inventories': [],
    }


def create_bulk_upload_request(auth_token: str, **kwargs) -> dict:
    """Create an API bulk upload request and return response."""
    headers = {'Authorization': f'{auth_token}', 'Content-Type': 'application/json'}
    mutation_inputs = []
    # Loop through kwargs and add them as request inputs
    for mutation_name in kwargs:
        mutation = getattr(mutations, mutation_name)
        for mutation_input in kwargs.get(mutation_name):
            mutation_inputs.append(
                {'query': mutation, 'variables': {'input': mutation_input}})
    req_data = json.dumps(mutation_inputs)
    res = requests.post(urljoin(API_URL, 'graphql'), headers=headers, data=req_data)
    bulk_upload_data = json.loads(res.text)
    return bulk_upload_data


def get_parts_df(input_file: str) -> object:
    """Get dataframe from file location."""
    df = pd.read_csv(input_file)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Import transformed CSV into the ION inventory system.')
    parser.add_argument('input_file', type=str,
                        help='Path to transformed CSV to be imported.')
    args = parser.parse_args()
    input_file = args.input_file
    df = get_parts_df(input_file)
    to_upload = get_upload_dict(df)
    to_upload = create_upload_items(df, to_upload)
    # Get API token
    access_token = get_access_token()
    # Upload parts, units of measurment and locations
    resp = create_bulk_upload_request(
        access_token, CREATE_UNITS_OF_MEASUREMENT=to_upload['uoms'],
        CREATE_PART=to_upload['parts'], CREATE_LOCATION=to_upload['locations'])
    # Fill cache with ids from newely created objects
    cache = update_cache(resp, {})
    to_upload = fill_from_cache(to_upload=to_upload, cache=cache,
                                to_fill=['parts_inventories'])
    # Upload part inventories and part lots
    resp = create_bulk_upload_request(
        access_token, CREATE_PART_INVENTORY=to_upload['parts_inventories'],)
