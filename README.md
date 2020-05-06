# ion-importers
Import your data into ion from existing systems - PLM, spreadsheets, etc.

## Authentication
The API is protected with JWT token authentication, powered by Auth0. Users must be authenticated to retrieve any resource. The importer currently only supports machine to machine authentication using a client id and client secret. To run the import scripts set the following env variables.
```shell script
export ION_IMPORTER_CLIENT_ID='<your-ion-client-id>'
export ION_IMPORTER_CLIENT_SECRET='<your-ion-client-secret>'
```

## Setup

System dependencies:
- Python
- pip
- virtualenv

Create a virtualenv and activate it:

```
virtualenv -p python3 importer_venv
source ./importer_venv/bin/activate
```

Then, install the dependencies:

```
pip install -r requirements.txt
```

# Importers

## Inventory

To import any transformed inventory CSV into ION run the following command.
```
python importers/inventory/import.py /path/to/upload.csv
```

### Fishbowl Transformer

We currently support importing inventory from fishbowl. Both part metadata as well as inventory tracked lot and serial parts.

Supported Fields:
* PartNumber
* PartDescription
* Location
* Qty
* UOM
* Cost
* Tracking-Lot Number
* Serial Number
* PartType

Run fishbowl converter:
```
python importers/inventory/fishbowl/transform.py /path/to/fishbowl/csvs --output_file=optional_output_filename
```
