# Code style

- **Python 3.12**, formatted with `ruff` + `black`; type hints on public
  functions. Prefer `async def` for I/O (API routes, model/DB calls).
- Small, single-purpose modules. Match the style of code already in the file.
- No dead code, no commented-out blocks, no TODOs left as the only "handling".
- Config via environment (`.env` + `pydantic-settings`); never hard-code URLs,
  keys, model slugs, or paths.
- Errors fail **loud but clean**: API routes catch upstream failures and return
  a typed `HTTPException` with a JSON `detail`, never an unhandled 500.
- Frontend (React/Vite): keep components small; wrap API calls in `try/catch`
  and surface errors in the UI, never a silent blank state.
- Comments explain *why*, not *what*. Keep them at the density of the surrounding
  code.
