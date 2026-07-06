using '../main.bicep'

param organisationPrefix = 'agrip'
param workloadName = 'gridrel'
param environment = 'prod'
param location = 'uksouth'
param regionCode = 'uks'
param instance = '001'
param allowPublicNetworkAccess = false
param enableRoleAssignments = false
param vnetAddressPrefix = '10.60.0.0/20'
param subnetPrefixes = {
  integration: '10.60.0.0/24'
  private_endpoints: '10.60.1.0/24'
  machine_learning: '10.60.2.0/24'
  application: '10.60.3.0/24'
  management: '10.60.4.0/24'
}
param logRetentionDays = 180
param mlComputeMinNodes = 0
param tags = {
  application: 'azure-grid-reliability-intelligence-platform'
  environment: 'prod'
  owner: 'platform-team-placeholder'
  cost_center: 'placeholder'
  data_classification: 'synthetic'
  criticality: 'high'
  managed_by: 'bicep-blueprint'
  repository: 'azure-grid-reliability-intelligence-platform'
  deployment_stage: 'blueprint_only'
}
