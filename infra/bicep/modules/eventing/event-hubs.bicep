param baseName string
param location string
param allowPublicNetworkAccess bool
param tags object

var hubs = [
  'smart-meter-events'
  'substation-events'
  'weather-events'
  'asset-events'
  'maintenance-events'
  'outage-events'
]

resource namespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: '${baseName}-ehns'
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
    capacity: 1
  }
  tags: tags
  properties: {
    publicNetworkAccess: allowPublicNetworkAccess ? 'Enabled' : 'Disabled'
    minimumTlsVersion: '1.2'
    disableLocalAuth: true
  }
}

resource eventHubs 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = [for hubName in hubs: {
  parent: namespace
  name: hubName
  properties: {
    partitionCount: 2
    messageRetentionInDays: 1
  }
}]

resource consumerGroups 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = [for hubName in hubs: {
  parent: eventHubs[indexOf(hubs, hubName)]
  name: 'validation'
}]

output namespaceId string = namespace.id
output eventHubNames array = hubs
