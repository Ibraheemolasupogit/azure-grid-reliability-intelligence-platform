using '../main.bicep'

param organisationPrefix = 'agrip'
param workloadName = 'gridrel'
param environment = 'dev'
param location = 'uksouth'
param regionCode = 'uks'
param instance = '001'
param allowPublicNetworkAccess = true
param enableRoleAssignments = false
param vnetAddressPrefix = '10.40.0.0/20'
param subnetPrefixes = {
  integration: '10.40.0.0/24'
  private_endpoints: '10.40.1.0/24'
  machine_learning: '10.40.2.0/24'
  application: '10.40.3.0/24'
  management: '10.40.4.0/24'
}
param logRetentionDays = 30
param mlComputeMinNodes = 0
param tags = {
  application: 'azure-grid-reliability-intelligence-platform'
  environment: 'dev'
  owner: 'platform-team-placeholder'
  cost_center: 'placeholder'
  data_classification: 'synthetic'
  criticality: 'low'
  managed_by: 'bicep-blueprint'
  repository: 'azure-grid-reliability-intelligence-platform'
  deployment_stage: 'blueprint_only'
}
