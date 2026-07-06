param baseName string
param location string
param allowPublicNetworkAccess bool
param tags object

resource aiServices 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: '${baseName}-aif'
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    publicNetworkAccess: allowPublicNetworkAccess ? 'Enabled' : 'Disabled'
    disableLocalAuth: true
  }
}

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: '${baseName}-srch'
  location: location
  sku: {
    name: 'basic'
  }
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    publicNetworkAccess: allowPublicNetworkAccess ? 'enabled' : 'disabled'
    disableLocalAuth: true
    hostingMode: 'default'
  }
}

output aiFoundryAccountId string = aiServices.id
output searchServiceId string = search.id
