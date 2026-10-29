from pathlib import Path
from typing import Literal

from app.config import Settings, get_settings

Layer = Literal["bronze", "silver", "gold"]
# Gold is published under this prefix inside AZURE_BLOB_CONTAINER.
GOLD_BLOB_PREFIX = "gold"


def resolve_layer_path(layer: Layer, settings: Settings | None = None) -> str:
    """Local compute path for a medallion layer — the single storage seam for the ETL.

    The ETL always *computes* locally (local Spark writes the lake to disk; no
    hadoop-azure jars needed). `ETL_STORAGE=blob` does not change where Spark
    writes — it additionally publishes Gold to Blob (see `publish_gold_to_blob`).
    """
    settings = settings or get_settings()
    return str(Path(settings.data_lake_path) / layer)


def blob_enabled(settings: Settings | None = None) -> bool:
    """True when Gold should also be published to Azure Blob after a local run."""
    settings = settings or get_settings()
    return settings.etl_storage == "blob"


def publish_gold_to_blob(gold_root: str | Path, settings: Settings | None = None) -> dict:
    """Upload the local Gold tree (both Delta tables + _manifest.json) to Blob.

    Mirrors the on-disk layout under `<GOLD_BLOB_PREFIX>/...` inside
    `AZURE_BLOB_CONTAINER`. Fails loud if Blob is not configured.
    """
    settings = settings or get_settings()
    if settings.azure_blob_connection_string is None or not settings.azure_blob_container:
        raise ValueError(
            "ETL_STORAGE=blob requires AZURE_BLOB_CONNECTION_STRING and AZURE_BLOB_CONTAINER."
        )
    # Imported lazily so the ETL unit tests (local storage) don't need the Azure SDK.
    from azure.core.exceptions import ResourceExistsError
    from azure.storage.blob import BlobServiceClient

    gold_root = Path(gold_root)
    if not gold_root.is_dir():
        raise FileNotFoundError(f"Gold root not found at {gold_root}; run Gold first.")

    service = BlobServiceClient.from_connection_string(
        settings.azure_blob_connection_string.get_secret_value()
    )
    container = service.get_container_client(settings.azure_blob_container)
    try:
        container.create_container()
    except ResourceExistsError:
        pass

    uploaded, total_bytes = 0, 0
    for path in sorted(gold_root.rglob("*")):
        if not path.is_file():
            continue
        blob_name = f"{GOLD_BLOB_PREFIX}/{path.relative_to(gold_root).as_posix()}"
        data = path.read_bytes()
        container.upload_blob(name=blob_name, data=data, overwrite=True)
        uploaded += 1
        total_bytes += len(data)

    return {
        "container": settings.azure_blob_container,
        "prefix": f"{GOLD_BLOB_PREFIX}/",
        "files": uploaded,
        "bytes": total_bytes,
    }
