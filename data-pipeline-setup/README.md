# Data pipeline setup

How to populate the data a fresh clone doesn't ship (the real corpus, the medallion lake, and the
vector store are all gitignored). Pick the mode you want to run in — the two are mutually exclusive
and both are driven by `backend/.env` flags.

| Mode | Guide | Cost | When |
|---|---|---|---|
| **Local** (default) | [`local/LOCAL_SETUP.md`](./local/LOCAL_SETUP.md) | **$0** | Reproduce everything on your own machine — download the dataset slice → build the medallion lake → embed into pgvector → run the app. Start here. |
| **Cloud** (optional) | [`cloud/CLOUD_SETUP.md`](./cloud/CLOUD_SETUP.md) | metered, **cost-gated** | A one-off "prove it live on Azure + Databricks, capture evidence, tear down" run. `cloud/P3_etl_spec.md` is the ETL spec it builds on. |

Switching modes = flipping provider/storage flags in `backend/.env` (e.g. `PROVIDER_MODE`,
`ETL_STORAGE`, the `*_GO_AHEAD` cost gates). Each guide states exactly which flags its mode needs.
