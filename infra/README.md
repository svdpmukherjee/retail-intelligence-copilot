# infra

**M1 provisions nothing. Expected cloud cost = $0.** These are inert stubs; no
`az deployment` has been run and no resource exists.

- `main.bicep` - subscription-scope entrypoint: parameters (`location`, `env`,
  `namePrefix`, budget inputs) and commented module references for later modules.
- `budget.bicep` - a monthly `Microsoft.Consumption` budget with an alert
  threshold (default 80% of actual spend). Amount and contact come from params.
  It is the cloud twin of the in-code `MAX_COST_USD` cap.
- `main.bicepparam` - placeholder values only; no secrets or real emails.
- `teardown.sh` - **destructive**: deletes a resource group after a typed
  confirmation. Use only after real provisioning, to stop spend.

Later use: once a module is approved to spend money, fill in `main.bicepparam`
locally, uncomment the relevant modules, and deploy with
`az deployment sub create -f main.bicep -p main.bicepparam` (after the cost gate
go-ahead, logged in `COST.md`). Validate syntax with `az bicep build -f main.bicep`.
