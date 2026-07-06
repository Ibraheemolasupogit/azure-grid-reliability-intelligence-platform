param baseName string
param location string
param vnetAddressPrefix string
param subnetPrefixes object
param tags object

resource nsg 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: '${baseName}-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'DenyInboundInternet'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: 'Internet'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: '${baseName}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      for subnetName in [
        'integration'
        'private_endpoints'
        'machine_learning'
        'application'
        'management'
      ]: {
        name: subnetName
        properties: {
          addressPrefix: subnetPrefixes[subnetName]
          networkSecurityGroup: {
            id: nsg.id
          }
          privateEndpointNetworkPolicies: subnetName == 'private_endpoints' ? 'Disabled' : 'Enabled'
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output subnetIds object = {
  integration: resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'integration')
  privateEndpoints: resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'private_endpoints')
  machineLearning: resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'machine_learning')
  application: resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'application')
  management: resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'management')
}
