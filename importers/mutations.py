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
                id _etag lotNumber serialNumber part { partNumber }
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


CREATE_MBOM_ITEM = '''
mutation($input: CreateMBomItemInput!){
  createMbomItem(input: $input){
      mbomItem { id }
  }
}
'''


GET_PARTS = '''
query GetParts($filters: PartsInputFilters) {
    parts(filters: $filters) {
        edges {node {id partNumber}}
    }
}
'''


GET_PROCEDURES = '''
query GetProcedures($filters: ProceduresInputFilters) {
    procedures(filters: $filters) {
        edges {node {
            id title
        }}
    }
}
'''


CREATE_RUN = '''
mutation CreateRun($input: CreateRunInput!) {
    createRun(input: $input) {
        run {
            id title procedureId partInventoryId
        }
    }
}
'''


CREATE_ABOM_FOR_PART_INVENTORY = '''
mutation CreateABomForPartInventory($id: ID!, $etag: String!) {
    createAbomForPartInventory(id: $id, etag: $etag) {
        abomItem {
            id partInventoryId children { id }
        }
    }
}
'''
