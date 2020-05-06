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
from importers.mutations import BULK_PART_UPLOAD_MUTATION # noqa

# Compiled regular expression to convert camel case to snake case
to_snake_case = re.compile(r'(?<!^)(?=[A-Z])')

# Unique identifiers for object types
type_identifiers = {
    'locations': lambda v: v.get('name'),
    'parts': lambda v: v.get('partNumber'),
    'units_of_measurements': lambda v: v.get('type'),
    'parts_lots': lambda v: v.get('lotNumber'),
    'parts_inventories': lambda v: _get_part_inventory_identifier(v),
    'parts_instances': lambda v: v.get('serialNumber'),
}

# Columns that are to be filled in by cached API responses
cache_ids = {
    'locationId': 'locations',
    'unitOfMeasureId': 'units_of_measurements',
    'originPartId': 'parts',
    'partId': 'parts',
    'partsInventoryId': 'parts_inventories',
    'partLotId': 'parts_lots',
    'partInventoryId': 'parts_inventories',
}


def _get_part_inventory_identifier(inventory: dict) -> str:
    """
    Get the unique identifier of an inventory object.

    Identifier is the concatenation of part number with location name.

    Args:
        inventory (dict): inventory object

    Returns:
        str: unique inventory object identifier
    """
    part = inventory.get('part', {}).get('partNumber', '')
    location = inventory.get('location', {}).get('name', None)
    if location is None:
        return part
    return f'{part}_{location}'


def update_cache(resp_data: dict, cache: dict) -> dict:
    """
    Returns import cache updated with responses from an API request response.

    Args:
        resp_data (dict): API response dict
        cache (dict): Import cache

    Returns:
        dict: Cache filled with new entries from response
    """
    for object_type in resp_data:
        cache_type = to_snake_case.sub('_', object_type).lower()
        if cache_type not in cache:
            cache[cache_type] = {}
        if resp_data[object_type] is None:
            continue
        obj_identifier = type_identifiers[cache_type]
        new_cache_entries = {obj_identifier(obj): obj for obj in resp_data[object_type]}
        cache[cache_type] = {**cache[cache_type], **new_cache_entries}
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


def _create_part_instance(part_number: str, serial_number: str,
                          instance_df: object) -> dict:
    """Create part instance dict to be uploaded"""
    part_instance = {
        'originPartId': part_number, 'serialNumber': serial_number
    }
    location = _get_attr_from_df(instance_df, 'location_name')
    part_instance['partsInventoryId'] = part_number
    if location is not None:
        part_instance['locationId'] = location
        part_instance['partsInventoryId'] = f'{part_number}_{location}'
    part_instance['partLotId'] = _get_attr_from_df(instance_df, 'lot_number')
    return part_instance


def _create_lot_inventory(part_number: str, lot_number: str, location: str,
                          lot_inventory_df: object) -> dict:
    """Create connection between part lot and part inventory objects."""
    part_inventory_id = part_number
    if location != '':
        part_inventory_id = f'{part_number}_{location}'
    inventory_lot = {
        'partInventoryId': part_inventory_id, 'partLotId': lot_number
    }
    inventory_lot['quantity'] = _get_attr_from_df(lot_inventory_df, 'quantity')
    return inventory_lot


def _create_part_lot(part_number: str, lot_number: str, lot_df: object,
                     to_upload: dict) -> dict:
    """Create part lot dict to be uploaded."""
    part_lot = {
        'originPartId': part_number, 'lotNumber': lot_number
    }
    lot_inventory_groups = lot_df.groupby(['location_name'])
    to_upload['part_inventories_lots'].extend(
        [_create_lot_inventory(part_number=part_number, lot_number=lot_number,
                               location=group_idx, lot_inventory_df=lot_inventory_df)
         for group_idx, lot_inventory_df in lot_inventory_groups])
    return part_lot


def _create_part_inventory(part_number: str, location: str,
                           part_inventory_df: object) -> dict:
    """Create part inventory dict to be uploaded."""
    part_inventory = {'partId': part_number, 'locationId': location}
    part_inventory['unitOfMeasureId'] = _get_attr_from_df(part_inventory_df, 'uom')
    part_inventory['cost'] = _get_attr_from_df(part_inventory_df, 'cost')
    part_inventory['quantity'] = _get_attr_from_df(part_inventory_df, 'quantity')
    # TODO Get inventory type
    return part_inventory


def _get_part_lot_groups(part_number: str, part_df: object, to_upload: dict) -> list:
    """Get all part lot objects for a specific part number."""
    # If a row has a lot number but not a serial number, it is a lot object.
    part_lot_groups = part_df[
        (part_df.serial_number.isna() == True) &
        (part_df.lot_number.isna() == False)].groupby(['lot_number']) # noqa
    return [_create_part_lot(part_number=part_number, lot_number=group_idx,
                             lot_df=part_lot_df, to_upload=to_upload)
            for group_idx, part_lot_df in part_lot_groups]


def _get_part_instance_groups(part_number: str, part_df: object) -> dict:
    """Get all part serial objects for a specific part number."""
    # If a row has a serial number its a serial object
    part_instance_groups = part_df[part_df.serial_number.isna() == False].groupby(['serial_number']) # noqa
    return [_create_part_instance(part_number=part_number, serial_number=group_idx,
                                  instance_df=part_instance_df)
            for group_idx, part_instance_df in part_instance_groups]


def _get_inventory_groups(part_number: str, part_df: object) -> dict:
    """Get all part inventory objects for a specific part number."""
    # Inventory objects are created for each location a part has.
    part_inventory_groups = part_df.groupby(['location_name'])
    return [_create_part_inventory(part_number=part_number, location=group_idx,
                                   part_inventory_df=part_inventory_df)
            for group_idx, part_inventory_df in part_inventory_groups]


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
        to_upload['parts_inventories'].extend(
            _get_inventory_groups(part_number=part_number, part_df=part_df))
        # Get all lots for a part
        to_upload['parts_lots'].extend(
            _get_part_lot_groups(part_number=part_number, part_df=part_df,
                                 to_upload=to_upload))
        # Get all serialized instances of a part
        to_upload['parts_instances'].extend(
            _get_part_instance_groups(part_number=part_number, part_df=part_df))
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
        'parts_instances': [],
        'parts_lots': [],
        'parts': [],
        'parts_inventories': [],
        'part_inventories_lots': []
    }


def create_bulk_upload_request(auth_token: str, **kwargs) -> dict:
    """Create an API bulk upload request and return response."""
    headers = {'Authorization': f'{auth_token}', 'Content-Type': 'application/json'}
    mutation_input = {}
    # Loop through kwargs and add them as request inputs
    for arg in kwargs:
        mutation_input[arg] = kwargs.get(arg)
    req_data = json.dumps({'query': BULK_PART_UPLOAD_MUTATION,
                           'variables': {'input': mutation_input}})
    res = requests.post(urljoin(API_URL, 'graphql'), headers=headers, data=req_data)
    bulk_upload_data = json.loads(res.text)
    if 'errors' in bulk_upload_data:
        raise AttributeError(bulk_upload_data['errors'][0]['message'])
    return bulk_upload_data['data']['bulkPartUpload']


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
        access_token, unitsOfMeasurements=to_upload['uoms'],
        parts=to_upload['parts'], locations=to_upload['locations'])
    # Fill cache with ids from newely created objects
    cache = update_cache(resp, {})
    to_upload = fill_from_cache(to_upload=to_upload, cache=cache,
                                to_fill=['parts_inventories', 'parts_lots'])
    # Upload part inventories and part lots
    resp = create_bulk_upload_request(
        access_token, partsInventories=to_upload['parts_inventories'],
        partsLots=to_upload['parts_lots'])
    cache = update_cache(resp, cache)
    to_upload = fill_from_cache(to_upload=to_upload, cache=cache,
                                to_fill=['parts_instances', 'part_inventories_lots'])
    # Upload part instances and part inventory to lot connections
    create_bulk_upload_request(
        access_token, partsInstances=to_upload['parts_instances'],
        partInventoriesLots=to_upload['part_inventories_lots'])
