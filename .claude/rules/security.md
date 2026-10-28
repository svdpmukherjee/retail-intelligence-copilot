# Security & responsible AI

- **Secrets:** only via `.env` (gitignored) or a secret store (Azure Key Vault /
  managed identity in cloud). Never commit, log, or print secrets. Every key is
  documented in `.env.example`.
- **Access control:** a role → allowed sources/categories policy is enforced **at
  retrieval, before the LLM** — not by prompt-asking the model to behave. A user
  must not retrieve evidence outside their scope.
- **PII:** redact personal data at ingestion. Do not commit raw PII; committed
  artifacts are the redacted/derived index only.
- **Grounding:** generated claims must map to retrieved evidence and be cited;
  block/flag uncited claims.
- **Auditability:** every answer logs query, role, retrieved sources, tool path,
  tokens, cost, latency — enough to reconstruct why an answer was given.
- **Least privilege:** cloud identities and DB users get only the access they
  need. Prefer managed identity over keys where possible.
- **Input handling:** treat uploaded/user documents as untrusted; validate and
  sandbox parsing.
