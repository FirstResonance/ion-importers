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

## BOM

### SolidWorks excel BOM export

To import a BOM from SolidWorks, first make sure it is exported as an Excel (.xlsx) file. That can be done by following the instructions found [here](https://help.solidworks.com/2019/english/SolidWorks/sldworks/t_Saving_BOMs.htm). Be sure to follow the convention of keeping the filename as the Part Number for the BOM export's top level part.

The importer will create a corresponding MBOM item for every entry in the exported BOM, following the same hierarchy. If the part referenced by the BOM item does not exist within the ION ecosystem, then the part will be created in ION as well.

Any failures to import BOM items will be logged to the console with the message describing the reason for the failure, but will not stop the importer from continuing to the next item. The most common reason for failures is duplications of the same part number at the same level of indentation. It is best to verify there are no such duplicates ahead of time.

Supported Fields for BOM Items:
* Part Number
* Level
* Quantity

Supported Fields for created Parts:
* Part Number
* Description
* VendorNo


Run SolidWorks BOM importer:
```
python importers/bom/solidworks/import.p /path/to/solid_works/excel.xlsx
```
