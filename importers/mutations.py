

BULK_PART_UPLOAD_MUTATION = '''
    mutation BulkPartUpload($input: BulkPartUploadInput!) {
        bulkPartUpload(input: $input) {
            parts { id partNumber }
            partsInstances { id serialNumber originPartId }
            partsLots { id lotNumber originPartId quantity }
            partsInventories { id part { partNumber } location { name } }
            locations { id name }
            unitsOfMeasurements { id type }
        }
    }
'''
