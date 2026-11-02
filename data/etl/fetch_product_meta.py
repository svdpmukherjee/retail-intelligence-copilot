"""Acquire the item-metadata slice the review feed lacks (price, title, avg-rating).

The Amazon Reviews 2023 review feed carries no product attributes; they live in the
separate `meta_<Category>.jsonl` feed (10-30 GB each). We cannot `curl | head` those the
way `LOCAL_SETUP.md § B.5` does for reviews, because a product's metadata can sit anywhere
in the file. So we stream each metadata file once and keep only the records whose
`parent_asin` appears in our already-downloaded reviews, projecting just the few fields we
need. Output: `<lake>/raw_meta/meta_<Category>.jsonl` (a few hundred MB total), consumed by
`product_meta.run_product_meta`.

Run once, after B.5, from the repo root:  python -m data.etl.fetch_product_meta
"""

import json
import subprocess
import sys
from pathlib import Path

from app.config import Settings, get_settings

META_PATH = "raw/meta_categories"


def _base_url(settings: Settings) -> str:
    return f"https://huggingface.co/datasets/{settings.amazon_dataset_id}/resolve/main/{META_PATH}"


def _parse_price(value: object) -> float | None:
    """Amazon prices arrive as float, '$12.99', '9.99 - 19.99', '', or 'None'."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text or text.lower() == "none":
        return None
    text = text.split("-")[0].split("to")[0].strip()
    try:
        return float(text)
    except ValueError:
        return None


def _first_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return " ".join(str(x) for x in value if x) or None
    return str(value).strip() or None


def _needed_parent_asins(raw_file: Path) -> set[str]:
    """Distinct parent_asin (falling back to asin) across one category's review file."""
    wanted: set[str] = set()
    with raw_file.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = record.get("parent_asin") or record.get("asin")
            if key:
                wanted.add(key)
    return wanted


def fetch_category(category: str, settings: Settings) -> tuple[int, int]:
    """Stream+filter one category's metadata; returns (products_kept, products_with_price)."""
    raw_file = Path(settings.data_lake_path) / "raw" / f"{category}.jsonl"
    if not raw_file.exists():
        print(f"SKIP {category}: no reviews at {raw_file}", flush=True)
        return (0, 0)
    wanted = _needed_parent_asins(raw_file)
    out_dir = Path(settings.data_lake_path) / "raw_meta"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"meta_{category}.jsonl"
    url = f"{_base_url(settings)}/meta_{category}.jsonl"

    kept = priced = 0
    proc = subprocess.Popen(["curl", "-sL", url], stdout=subprocess.PIPE, bufsize=1 << 20)
    with out_file.open("w", encoding="utf-8") as out:
        for raw in proc.stdout:  # type: ignore[union-attr]
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            parent = record.get("parent_asin")
            if parent is None or parent not in wanted:
                continue
            price = _parse_price(record.get("price"))
            out.write(
                json.dumps(
                    {
                        "parent_asin": parent,
                        "product_title": _first_str(record.get("title")),
                        "price": price,
                        "product_avg_rating": record.get("average_rating"),
                        "product_rating_count": record.get("rating_number"),
                        "store": _first_str(record.get("store")),
                        "main_category": _first_str(record.get("main_category")),
                    }
                )
                + "\n"
            )
            kept += 1
            priced += price is not None
    proc.wait()
    pct = (100.0 * priced / kept) if kept else 0.0
    print(f"{category}: {kept}/{len(wanted)} products, price on {priced} ({pct:.1f}%)", flush=True)
    return (kept, priced)


def main() -> None:
    settings = get_settings()
    kept = priced = 0
    for category in settings.sql_categories:
        k, p = fetch_category(category, settings)
        kept += k
        priced += p
    pct = (100.0 * priced / kept) if kept else 0.0
    print(f"TOTAL {kept} products, {priced} with price ({pct:.1f}%)", flush=True)
    if kept == 0:
        sys.exit("No products written; did you run B.5 (reviews) first?")


if __name__ == "__main__":
    main()
