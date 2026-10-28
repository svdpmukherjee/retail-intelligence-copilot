// Inert skeleton: declares parameters only. Nothing here is deployed in M8.
// Future home of the hosted backend + frontend; real provisioning needs explicit human go-ahead (cost gate).
targetScope = 'resourceGroup'

@description('Azure region for all resources (mirrors a future AZURE_LOCATION setting).')
param location string

@description('Environment name, e.g. dev or prod.')
param env string

@description('Naming prefix shared by all resources (mirrors a future AZURE_NAME_PREFIX setting).')
param namePrefix string

@description('Container image for the backend (built from backend/Dockerfile).')
param backendImage string

@description('Comma-separated allowed browser origins; mirrors CORS_ALLOW_ORIGINS.')
param corsAllowOrigins string

var backendAppName = '${namePrefix}-${env}-api'
var frontendAppName = '${namePrefix}-${env}-web'

// Later (uncomment when real provisioning is approved):
// resource plan 'Microsoft.Web/serverfarms@2023-12-01' = { ... }
// resource api 'Microsoft.Web/sites@2023-12-01' = {
//   name: backendAppName
//   location: location
//   // container: backendImage; app settings CORS_ALLOW_ORIGINS=corsAllowOrigins; secrets via Key Vault references
// }
// resource web 'Microsoft.Web/staticSites@2023-12-01' = { name: frontendAppName, location: location, ... }

output plannedBackendApp string = backendAppName
output plannedFrontendApp string = frontendAppName
