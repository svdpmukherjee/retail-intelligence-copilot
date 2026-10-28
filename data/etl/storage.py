from pathlib import Path
from typing import Literal

from app.config import Settings, get_settings

Layer = Literal["bronze", "silver", "gold"]


def resolve_layer_path(layer: Layer, settings: Settings | None = None) -> str:
    """Return where a medallion layer lives; the single storage seam for the ETL."""
    settings = settings or get_settings()
    if settings.etl_storage == "blob":
        raise NotImplementedError(
            "ETL_STORAGE=blob requires explicit human go-ahead (cloud spend) and is not "
            "configured locally; use ETL_STORAGE=local."
        )
    return str(Path(settings.data_lake_path) / layer)
