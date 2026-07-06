param baseName string
param environment string

output semanticModelMapping string = '${baseName}-${environment}-powerbi-semantic-model-mapping'
output deploymentStatus string = 'BLUEPRINT_ONLY'
