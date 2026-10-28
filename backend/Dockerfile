# Build from the backend directory: docker build -t ric-backend backend
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /srv
COPY pyproject.toml ./
COPY app app
COPY agents agents
COPY retrieval retrieval
COPY memory memory
COPY governance governance
COPY eval eval

# CPU-only torch first: the default wheel pulls multi-GB CUDA libraries the free-tier embedder never uses.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir .

# Config (DATABASE_URL, PROVIDER_MODE, keys, CORS_ALLOW_ORIGINS) arrives via runtime env, never baked in.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
