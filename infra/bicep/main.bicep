targetScope = 'resourceGroup'

@description('Short organisation prefix used for deterministic names.')
param organisationPrefix string

@description('Workload name.')
param workloadName string = 'gridrel'

@allowed([
  'dev'
  'test'
  'prod'
])
@description('Deployment environment.')
param environment string

@description('Azure region for the blueprint.')
param location string = resourceGroup().location

@description('Short region code used in names.')
param regionCode string

@description('Instance suffix.')
param instance string = '001'

@description('Allow public network access for services that support the setting.')
param allowPublicNetworkAccess bool = false

@description('Enable role assignments. Disable for static validation.')
param enableRoleAssignments bool = false

@description('Virtual network address prefix placeholder.')
param vnetAddressPrefix string

@description('Subnet CIDR placeholders.')
param subnetPrefixes object

@description('Log Analytics retention in days.')
param logRetentionDays int = 30

@description('Minimum AML compute nodes.')
param mlComputeMinNodes int = 0

@description('Default tags applied to resources.')
param tags object

var baseName = toLower('${organisationPrefix}-${workloadName}-${environment}-${regionCode}-${instance}')
var storageName = take(replace(baseName, '-', ''), 20)
var keyVaultName = take(replace('${baseName}-kv', '-', ''), 24)

module identity 'modules/identity/managed-identities.bicep' = {
  name: 'identity'
  params: {
    baseName: baseName
    location: location
    tags: tags
  }
}

module networking 'modules/networking/network.bicep' = {
  name: 'networking'
  params: {
    baseName: baseName
    location: location
    vnetAddressPrefix: vnetAddressPrefix
    subnetPrefixes: subnetPrefixes
    tags: tags
  }
}

module monitoring 'modules/monitoring/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    baseName: baseName
    location: location
    logRetentionDays: logRetentionDays
    tags: tags
  }
}

module storage 'modules/storage/data-lake.bicep' = {
  name: 'storage'
  params: {
    storageAccountName: storageName
    location: location
    allowPublicNetworkAccess: allowPublicNetworkAccess
    tags: tags
  }
}

module eventing 'modules/eventing/event-hubs.bicep' = {
  name: 'eventing'
  params: {
    baseName: baseName
    location: location
    allowPublicNetworkAccess: allowPublicNetworkAccess
    tags: tags
  }
}

module analytics 'modules/analytics/data-explorer.bicep' = {
  name: 'analytics'
  params: {
    baseName: baseName
    location: location
    allowPublicNetworkAccess: allowPublicNetworkAccess
    tags: tags
  }
}

module machineLearning 'modules/machine-learning/workspace.bicep' = {
  name: 'machine-learning'
  params: {
    baseName: baseName
    location: location
    storageAccountId: storage.outputs.storageAccountId
    applicationInsightsId: monitoring.outputs.applicationInsightsId
    keyVaultName: keyVaultName
    mlComputeMinNodes: mlComputeMinNodes
    allowPublicNetworkAccess: allowPublicNetworkAccess
    tags: tags
  }
}

module ai 'modules/ai/ai-foundry-search.bicep' = {
  name: 'ai'
  params: {
    baseName: baseName
    location: location
    allowPublicNetworkAccess: allowPublicNetworkAccess
    tags: tags
  }
}

module governance 'modules/governance/purview.bicep' = {
  name: 'governance'
  params: {
    baseName: baseName
    location: location
    tags: tags
  }
}

module reporting 'modules/reporting/powerbi-fabric-placeholder.bicep' = {
  name: 'reporting'
  params: {
    baseName: baseName
    environment: environment
  }
}

output blueprintName string = baseName
output managedIdentityIds object = identity.outputs.identityResourceIds
output vnetId string = networking.outputs.vnetId
output storageAccountId string = storage.outputs.storageAccountId
output eventHubNamespaceId string = eventing.outputs.namespaceId
output dataExplorerClusterId string = analytics.outputs.clusterId
output machineLearningWorkspaceId string = machineLearning.outputs.workspaceId
output aiSearchServiceId string = ai.outputs.searchServiceId
output logAnalyticsWorkspaceId string = monitoring.outputs.logAnalyticsWorkspaceId
output purviewAccountId string = governance.outputs.purviewAccountId
output reportingDeploymentStatus string = reporting.outputs.deploymentStatus
output roleAssignmentsEnabled bool = enableRoleAssignments
