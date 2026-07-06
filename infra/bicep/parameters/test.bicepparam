using '../main.bicep'

param organisationPrefix = 'agrip'
param workloadName = 'gridrel'
param environment = 'test'
param location = 'uksouth'
param regionCode = 'uks'
param instance = '001'
param allowPublicNetworkAccess = false
param enableRoleAssignments = false
param vnetAddressPrefix = '10.50.0.0/20'
param subnetPrefixes = {
  integration: '10.50.0.0/24'
  private_endpoints: '10.50.1.0/24'
  machine_learning: '10.50.2.0/24'
  application: '10.50.3.0/24'
  management: '10.50.4.0/24'
}
param logRetentionDays = 60
param mlComputeMinNodes = 0
param tags = {
  application: 'azure-grid-reliability-intelligence-platform'
  environment: 'test'
  owner: 'platform-team-placeholder'
  cost_center: 'placeholder'
  data_classification: 'synthetic'
  criticality: 'medium'
  managed_by: 'bicep-blueprint'
  repository: 'azure-grid-reliability-intelligence-platform'
  deployment_stage: 'blueprint_only'
}
