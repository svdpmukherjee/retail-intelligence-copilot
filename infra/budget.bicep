// Subscription-level budget with an alert. Not deployed in M1.
targetScope = 'subscription'

@description('Budget name.')
param budgetName string

@description('Monthly budget amount in USD.')
param amountUsd int

@description('Email that receives alerts.')
param contactEmail string

@description('Alert when actual spend reaches this percent of the budget.')
@minValue(1)
@maxValue(100)
param alertThresholdPercent int = 80

@description('Budget period start (first day of a month, yyyy-MM-dd).')
param startDate string

resource budget 'Microsoft.Consumption/budgets@2023-05-01' = {
  name: budgetName
  properties: {
    category: 'Cost'
    amount: amountUsd
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: startDate
    }
    notifications: {
      actualThreshold: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: alertThresholdPercent
        thresholdType: 'Actual'
        contactEmails: [
          contactEmail
        ]
      }
    }
  }
}
