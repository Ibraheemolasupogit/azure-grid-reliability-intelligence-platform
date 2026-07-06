param baseName string
param location string
param tags object

resource purview 'Microsoft.Purview/accounts@2021-12-01' = {
  name: '${baseName}-pview'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    publicNetworkAccess: 'Disabled'
  }
}

output purviewAccountId string = purview.id
