param storageAccountName string
param location string
param allowPublicNetworkAccess bool
param tags object

var zoneNames = [
  'raw'
  'quarantine'
  'interim'
  'processed'
  'analytics'
  'model-artifacts'
  'monitoring'
  'assistant-index'
  'reporting'
]

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  tags: tags
  properties: {
    isHnsEnabled: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    publicNetworkAccess: allowPublicNetworkAccess ? 'Enabled' : 'Disabled'
  }
}

resource blob 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 14
    }
  }
}

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [for zoneName in zoneNames: {
  parent: blob
  name: zoneName
  properties: {
    publicAccess: 'None'
  }
}]

output storageAccountId string = storage.id
output filesystemNames array = zoneNames
