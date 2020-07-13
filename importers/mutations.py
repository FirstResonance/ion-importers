CREATE_UNITS_OF_MEASUREMENT = '''
    mutation CreateUnitOfMeasurement($input: CreateUnitOfMeasurementInput!) {
        createUnitOfMeasurement(input: $input) {
            unitOfMeasurement {
                id type
            }
        }
    }
'''


GET_UNITS_OF_MEASUREMENTS = '''
query UnitsOfMeasurements($filters: UnitsOfMeasurementInputFilters,
                         $sort: [UnitOfMeasurementSortEnum]) {
    unitsOfMeasurement(sort: $sort, filters: $filters) {
        edges{node {
            id type
        }}
    }
}
'''


CREATE_PART_INVENTORY = '''
    mutation CreatePartInventory($input: CreatePartInventoryInput!) {
        createPartInventory(input: $input) {
            partInventory {
                id lotNumber
            }
        }
    }
'''


CREATE_PART = '''
mutation CreatePart($input: CreatePartInput!) {
    createPart(input: $input) {
        part { id partNumber }
    }
}
'''


CREATE_LOCATION = '''
    mutation CreateLocation($input: CreateLocationInput!) {
        createLocation(input: $input) {
            location {
                id name
            }
        }
    }
'''


GET_LOCATIONS = '''
query GetLocations($filters: LocationsInputFilters, $sort: [LocationSortEnum]) {
    locations(sort: $sort, filters: $filters) {
        edges{ node { id name } }
    }
}
'''
