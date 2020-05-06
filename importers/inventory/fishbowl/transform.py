"""Transform a folder of fishbowl formatted CSV into an ION formatted CSV."""

import os
import csv
from codecs import decode
import argparse
from datetime import datetime
from copy import deepcopy
import pandas as pd

# Mappings from fishbowl column names to ION column names
column_mapping = {
    'PartNumber': 'part_number',
    'PartDescription': 'part_description',
    'Location': 'location_name',
    'Qty': 'quantity',
    'UOM': 'uom',
    'Cost': 'cost',
    'Date': 'created_date',
    'Tracking-Lot Number': 'lot_number',
    'PartType': 'tracking_type'
}
# Additional columns to include
additional_columns = ['serial_number']


def parse_input_csv(file_path: str, file_name: str) -> object:
    """Parse an input CSV into an ION formatted dataframe."""
    rows = []
    row = None
    # Read in as bytes to fix any decoding errors in utf-8
    with open(os.path.join(file_path, file_name), 'rb') as file_bytes:
        for idx, row_bytes in enumerate(file_bytes):
            # Use csv parser to split row into array
            csv_row = next(csv.reader([decode(row_bytes, errors='replace')]))
            if idx == 0:
                row_idxs, headers = _get_header_info(csv_row)
                continue
            # If the row length is one then its a serial number
            if len(csv_row) == 1:
                row, skip = _handle_serial_number_rows(csv_row, rows, row)
                if skip is True:
                    continue
            else:
                row = [col for col_idx, col in enumerate(csv_row) if col_idx in row_idxs]
                row.extend([None] * len(additional_columns))
            rows.append(row)
    return pd.DataFrame(rows, columns=headers)


def _handle_serial_number_rows(csv_row: list, rows: list, row: list) -> (list, bool):
    """Handle serial number rows."""
    if csv_row[0] == 'Serial Number':
        rows[-1][3] = 0
        return deepcopy(rows[-1]), True
    row = deepcopy(row)
    row[-1] = csv_row[0]
    return row, False


def _get_header_info(csv_row: list) -> (set, list):
    """Get ION header names and row indices of columns to save."""
    row_idxs = []
    headers = []
    for col_idx, col in enumerate(csv_row):
        if col in column_mapping:
            headers.append(column_mapping[col])
            row_idxs.append(col_idx)
    headers.extend(additional_columns)
    return set(row_idxs), headers


def _get_input_csv_files(input_folder_path: str) -> list:
    """Get all files in given folder that end with .csv"""
    if not os.path.exists(input_folder_path):
        raise FileNotFoundError('Cannot find files in input folder path '
                                f': {input_folder_path}')
    return [file_name for file_name in os.listdir(input_folder_path)
            if file_name.endswith('.csv')]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Transform fishbowl output into an ION importable CSV.')
    parser.add_argument('input_folder_path', type=str,
                        help='Path to folder that contains fishbowl CSVs')
    parser.add_argument('--output_file', type=str,
                        help='The name of the transformed CSV.')
    args = parser.parse_args()
    input_folder_path = args.input_folder_path
    output_file = args.output_file
    if output_file is None:
        date_time_str = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
        output_file = f'ion_inventory_import_{date_time_str}.csv'
    files = _get_input_csv_files(input_folder_path)
    frames = [parse_input_csv(input_folder_path, file_name)
              for file_name in files]
    df = pd.concat(frames, sort=False)
    df.to_csv(output_file, index=False)
