param baseName string
param location string
param tags object

var identities = [
  'ingestion'
  'analytics'
  'ml-training'
  'ml-inference'
  'assistant-retrieval'
  'monitoring'
]

resource userAssignedIdentities 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = [for identityName in identities: {
  name: '${baseName}-${identityName}-id'
  location: location
  tags: tags
}]

output identityResourceIds object = {
  ingestion: userAssignedIdentities[0].id
  analytics: userAssignedIdentities[1].id
  mlTraining: userAssignedIdentities[2].id
  mlInference: userAssignedIdentities[3].id
  assistantRetrieval: userAssignedIdentities[4].id
  monitoring: userAssignedIdentities[5].id
}
