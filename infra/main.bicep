// Inert skeleton: declares parameters only. Nothing here is deployed in M1.
targetScope = 'subscription'

@description('Azure region for all resources (mirrors a future AZURE_LOCATION setting).')
param location string

@description('Environment name, e.g. dev or prod.')
param env string

@description('Naming prefix shared by all resources (mirrors a future AZURE_NAME_PREFIX setting).')
param namePrefix string

@description('Monthly budget cap in USD; the cloud twin of MAX_COST_USD.')
param budgetAmountUsd int

@description('Contact email for budget alerts.')
param budgetContactEmail string

var resourceGroupName = '${namePrefix}-${env}-rg'

// Later modules add (uncomment when real provisioning is approved):
// resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
//   name: resourceGroupName
//   location: location
// }
// module budget 'budget.bicep' = {
//   name: 'budget'
//   params: { budgetName: '${namePrefix}-${env}-budget', amountUsd: budgetAmountUsd, contactEmail: budgetContactEmail }
// }
// module openai 'modules/openai.bicep' = { ... }   // M3
// module search 'modules/search.bicep' = { ... }   // M3
// module storage 'modules/storage.bicep' = { ... } // M2

output plannedResourceGroup string = resourceGroupName
output plannedLocation string = location
