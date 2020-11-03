# ion-importers
Import your data into ion from existing systems - PLM, spreadsheets, etc.

## Authentication
You will need a client ID and a client secret to authenticate to the API. You can get your client ID and secret by contacting First Resonance (software@firstresonance.io). You may want to override the API you are writing to with the following environment variables.

If you are targeting a non-production API, set `ION_IMPORT_API` to the API you are writing to and set your  `ION_API_AUDIENCE` to the API audience for the target API.

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
python importers/inventory/import.py /path/to/upload.csv --client_id <YOUR_CLIENT_ID>
```

### Excel

We currently support importing parts and inventory from an excel file providing it contains the correct columns and format

Supported Fields For Parts:
* Part Number (required)
* Description
* Tracking Level (valid options [Lot, Serial])
* Depth: Int value describing the MBOM structure
* Revision: String value which can only contain alphabetic text
* Quantity: MBOM quantity

Supported Fields For Inventory:
* Part Number (required)
* Description
* Serial Number
* Lot Number
* Quantity

Run excel importer for parts:
```
python importers/inventory/excel/import.py /path/to/excel_file --client_id=<client id> --type parts
```
Note that if no type is specified is defaults to parts

Run excel importer for inventory:
```
python importers/inventory/excel/import.py /path/to/excel_file --client_id=<client id> --type inventory
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
python importers/bom/solidworks/import.py /path/to/solidworks/excel.xlsx --client_id <YOUR_CLIENT_ID>
```

## Runs

### Bulk Run CSV

Runs can be bulk imported from a CSV format.

The importer will create serial tracked inventory instances for each serial number within the CSV. The part which the inventory entries reference must be previously created.

If no title is specified in the CSV, then a default title is generated using the format `<Part number> - <Serial number> - <Procedure title>`.

Execute Bulk Run CSV importer:
```
python importers/run/csv/import.py /path/to/run.csv --client_id <YOUR_CLIENT_ID>
```