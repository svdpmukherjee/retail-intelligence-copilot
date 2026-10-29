from functools import lru_cache
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Provider seam: "azure" (Azure OpenAI + AI Search) or "free" (free-tier LLM + pgvector).
    provider_mode: Literal["azure", "free"] = "free"

    # Azure OpenAI
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: SecretStr | None = None
    azure_openai_chat_deployment: str | None = None
    azure_openai_embedding_deployment: str | None = None

    # Azure AI Search
    azure_search_endpoint: str | None = None
    azure_search_api_key: SecretStr | None = None
    azure_search_index: str | None = None

    # Azure Blob Storage
    azure_blob_connection_string: SecretStr | None = None
    azure_blob_container: str | None = None

    # Databricks (batch/build-time ETL only)
    databricks_host: str | None = None
    databricks_token: SecretStr | None = None

    # Free-tier LLM
    free_llm_base_url: str | None = None
    free_llm_api_key: SecretStr | None = None
    free_llm_model: str | None = None

    # pgvector / Postgres
    database_url: SecretStr | None = None

    # ETL (batch/build-time). Runtime/storage seams mirror provider_mode: local by default.
    etl_runtime: Literal["local", "databricks"] = "local"
    etl_storage: Literal["local", "blob"] = "local"
    data_lake_path: str = "data"
    etl_year_min: int = 2019
    etl_year_max: int = 2023
    etl_sample_size: int = 50
    amazon_dataset_id: str = "McAuley-Lab/Amazon-Reviews-2023"
    # Comma-separated in .env; NoDecode keeps pydantic from JSON-parsing the raw string.
    # Both Gold layers default to the same 15 categories; env can make them diverge.
    sql_categories: Annotated[list[str], NoDecode] = [
        "Electronics",
        "Home_and_Kitchen",
        "Books",
        "Beauty_and_Personal_Care",
        "Sports_and_Outdoors",
        "Toys_and_Games",
        "Automotive",
        "Pet_Supplies",
        "Cell_Phones_and_Accessories",
        "Clothing_Shoes_and_Jewelry",
        "Health_and_Household",
        "Office_Products",
        "Tools_and_Home_Improvement",
        "Grocery_and_Gourmet_Food",
        "Video_Games",
    ]
    rag_categories: Annotated[list[str], NoDecode] = [
        "Electronics",
        "Home_and_Kitchen",
        "Books",
        "Beauty_and_Personal_Care",
        "Sports_and_Outdoors",
        "Toys_and_Games",
        "Automotive",
        "Pet_Supplies",
        "Cell_Phones_and_Accessories",
        "Clothing_Shoes_and_Jewelry",
        "Health_and_Household",
        "Office_Products",
        "Tools_and_Home_Improvement",
        "Grocery_and_Gourmet_Food",
        "Video_Games",
    ]
    # Per-category row caps keep Gold bounded and the M3 embed spend capped.
    sql_rows_per_category: int = 100000
    rag_rows_per_category: int = 15000
    # Salt for hashing reviewer ids at Silver (M2.3); never commit a real value.
    pii_hash_salt: SecretStr | None = None

    # Browser origins allowed to call the API (the Vite dev server by default); CSV in .env.
    cors_allow_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("sql_categories", "rag_categories", "cors_allow_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    # Embeddings / indexing (M3). Free mode uses a local sentence-transformers model at $0.
    vector_store: Literal["pgvector", "azure_search"] = "pgvector"
    embedding_model_free: str = "sentence-transformers/all-MiniLM-L6-v2"
    # text-embedding-3-small supports Matryoshka reduction; 512 shrinks the index.
    azure_embedding_dim: int = 512
    embedding_batch_size: int = 64
    max_embedding_usd: float = 5.0
    # Tiny slice indexed into the AI Search free tier (demo only; bulk lives in pgvector).
    index_slice_size: int = 1000
    # Explicit human go-ahead; real Azure embedding calls spend money and refuse without it.
    azure_embedding_go_ahead: bool = False

    # LLM calls (M4). Azure chat spends money, so it refuses without the go-ahead flag.
    azure_llm_go_ahead: bool = False
    llm_max_tokens: int = 512
    # Rough blended price used only to estimate spend in the ledger.
    azure_llm_usd_per_1m_tokens: float = 1.0

    # Hybrid retrieval (M4.2). Reranker "none" is the $0 default; "azure" refuses without go-ahead.
    reranker: Literal["none", "local", "azure"] = "none"
    rerank_go_ahead: bool = False
    rerank_model_local: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    retrieval_top_k: int = 6
    hybrid_candidates: int = 30
    rerank_candidates: int = 20
    rrf_k: int = 60

    # Conversation memory (M5): max recent messages loaded into a turn's context.
    memory_history_turns: int = 6
    memory_enabled: bool = True
    memory_summary_max_tokens: int = 256
    memory_max_items: int = 20

    # Governance (M6): persist each answer's audit record to Postgres (best-effort).
    audit_enabled: bool = True

    # Evaluation (M7): the answer judge. "deterministic" is $0; "llm" goes through get_llm()
    # and so stays behind azure_llm_go_ahead in azure mode.
    eval_judge: Literal["deterministic", "llm"] = "deterministic"

    # Cost caps, consumed by the cost ledger
    max_cost_usd: float = 1.0
    max_tokens_per_query: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
