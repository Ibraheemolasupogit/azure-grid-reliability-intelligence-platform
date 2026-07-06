param baseName string
param location string
param storageAccountId string
param applicationInsightsId string
param keyVaultName string
param mlComputeMinNodes int
param allowPublicNetworkAccess bool
param tags object

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    tenantId: tenant().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableSoftDelete: true
    enablePurgeProtection: true
    publicNetworkAccess: allowPublicNetworkAccess ? 'Enabled' : 'Disabled'
    enableRbacAuthorization: true
  }
}

resource workspace 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: '${baseName}-mlw'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    storageAccount: storageAccountId
    keyVault: keyVault.id
    applicationInsights: applicationInsightsId
    publicNetworkAccess: allowPublicNetworkAccess ? 'Enabled' : 'Disabled'
  }
}

resource compute 'Microsoft.MachineLearningServices/workspaces/computes@2024-04-01' = {
  parent: workspace
  name: 'batch-cpu'
  properties: {
    computeType: 'AmlCompute'
    properties: {
      vmSize: 'STANDARD_DS3_V2'
      scaleSettings: {
        minNodeCount: mlComputeMinNodes
        maxNodeCount: 2
      }
    }
  }
}

output workspaceId string = workspace.id
output keyVaultId string = keyVault.id
output computeName string = compute.name
