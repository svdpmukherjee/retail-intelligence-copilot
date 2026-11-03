"""Dataset capabilities and typed product-grain operations; no corpus in prompts."""

from typing import Literal

from pydantic import BaseModel, Field


class ProductQuery(BaseModel):
    operation: Literal["list_products", "average_price", "price_rank", "product_count"]
    title_contains: str | None = Field(default=None, max_length=120)
    order: Literal["price_asc", "price_desc", "title"] = "title"
    limit: int = Field(default=10, ge=1, le=25)
    price_below: float | None = Field(default=None, gt=0, le=10000000)
    price_above: float | None = Field(default=None, ge=0, le=10000000)


def capabilities(categories: list[str]) -> dict:
    return {
        "categories": sorted(set(categories)),
        "structured": {
            "grain": "one customer review; products repeat across rows",
            "fields": {
                "asin": "product identifier",
                "category": "canonical category",
                "product_title": "product name; supports literal case-insensitive substring search",
                "price": "nullable product price metadata, repeated per review; not a live quote",
                "rating": "individual review rating, 1 to 5",
                "timestamp": "review date",
                "product_avg_rating": "vendor product rating metadata, not AVG(rating)",
                "product_rating_count": "vendor count metadata, not dataset review count",
            },
            "operations": [
                "list/search products by category or words in product_title; no exact SKU required",
                "average product price, product count, sort product prices ascending/descending",
                "customer rating AVG(rating) over ALL dataset review rows for selected products",
                "counts, category comparisons and date-filtered SQL analysis",
            ],
            "price_contract": "one price per ASIN/category, MAX(non-null price); "
            "exclude missing prices for price calculations",
        },
        "reviews": "sampled semantic search; SQL-selected products can use "
        "verified bounded source reviews",
        "documents": "shared indexed return/refund/warranty/policy/manual documents",
        "limitations": [
            "no sales, revenue, inventory, orders, or live prices",
            "no smartphone taxonomy; search product titles and disclose literal matching",
            "review examples do not measure population complaint frequency",
            "lowest-product explanations support category, average rating, minimum "
            "dataset review count, up to 25 products; other qualifiers need explicit clarification",
        ],
    }
