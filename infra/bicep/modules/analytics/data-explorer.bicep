param baseName string
param location string
param allowPublicNetworkAccess bool
param tags object

resource cluster 'Microsoft.Kusto/clusters@2023-08-15' = {
  name: '${baseName}-adx'
  location: location
  sku: {
    name: 'Dev(No SLA)_Standard_D11_v2'
    tier: 'Basic'
    capacity: 1
  }
  tags: tags
  properties: {
    publicNetworkAccess: allowPublicNetworkAccess ? 'Enabled' : 'Disabled'
    enableStreamingIngest: true
    enablePurge: false
  }
}

resource database 'Microsoft.Kusto/clusters/databases@2023-08-15' = {
  parent: cluster
  name: 'grid_reliability'
  location: location
  kind: 'ReadWrite'
  properties: {
    softDeletePeriod: 'P30D'
    hotCachePeriod: 'P7D'
  }
}

output clusterId string = cluster.id
output databaseName string = database.name
