"""Small semantic contracts for supported metrics, independent of model wording."""

import re
from typing import Literal

from app.config import get_settings
from retrieval.vector_store import Filters

Operation = Literal["category_average", "category_review_count", "lowest_products"]
LOWEST = re.compile(r"\b(?:lowest|worst)[ -]rated\b", re.I)
EXPLAIN = re.compile(r"\b(?:why|explain|reasons?|disappoint\w*|unhappy|complain\w*)\b", re.I)
TEMPLATE_WORDS = set(
    (
        "what s is are was were do does did which why our the a an of for by per each across "
        "and customer customers rating ratings average avg mean category categories "
        "product products with from "
        "lowest worst rated top bottom unhappy disappointing disappoint disappointed explain "
        "reason reasons complaints complain about that so have get show give me us please list "
        "all except excluding other than"
    ).split()
)


def normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower().replace("&", " and ")))


def requested_categories(query: str) -> list[str]:
    """Canonical names/unique category stems from configured corpus vocabulary.

    Not a general entity extractor: ambiguous aliases are deliberately ignored.
    Permission checks still run separately, including explicit empty intersections.
    """
    s = get_settings()
    categories = sorted(set(s.sql_categories + s.rag_categories))
    aliases: dict[str, set[str]] = {}
    for category in categories:
        full = normalized(category)
        first = full.split()[0]
        names = {full, first}
        if first.endswith("s"):
            names.add(first[:-1])
        for alias in names:
            aliases.setdefault(alias, set()).add(category)

    def find(text: str) -> set[str]:
        text = " " + normalized(text) + " "
        return {
            next(iter(names))
            for alias, names in aliases.items()
            if len(names) == 1 and " " + alias + " " in text
        }

    # An explicit replacement in a follow-up wins over the inherited old category.
    replacement = re.split(
        r"\b(?:what about|how about|same but(?: for)?|and for)\b", query, flags=re.I
    )[-1]
    found = find(replacement) or find(query)
    # Explicit unknown slug remains a constraint, never a search of all categories.
    found.update(
        value for value in re.findall(r"\b\w+Category\b", query) if value not in categories
    )
    if not found:
        explicit = re.search(
            r"\b(?:in|for)\s+(?:the\s+)?([a-z_-]+)\s+(?:category|department)\b", query, re.I
        )
        if explicit and explicit[1].lower() not in {"each", "every", "all", "product", "our"}:
            found.add(explicit[1])
    return sorted(found)


def constrained_scope(query: str, scope: Filters | None) -> Filters:
    filters = dict(scope or {})
    parts = re.split(r"\b(?:except|excluding|other than)\b", query, maxsplit=1, flags=re.I)
    requested = requested_categories(parts[0])
    excluded = requested_categories(parts[1]) if len(parts) > 1 else []
    if excluded and not requested:
        s = get_settings()
        requested = sorted(set(s.sql_categories + s.rag_categories))
    if requested:
        allowed = filters.get("category")
        if allowed is not None:
            allowed = [allowed] if isinstance(allowed, str) else allowed
            requested = [c for c in requested if c in allowed]
        requested = [c for c in requested if c not in excluded]
        filters["category"] = requested
    return filters


def rating_operation(query: str) -> Operation | None:
    if re.fullmatch(
        r"\s*(?:how many reviews (?:are there )?(?:by|per|in each) categor(?:y|ies)|"
        r"(?:what(?:'s| is) (?:the )?)?review counts? (?:by|per) categor(?:y|ies))[?.!]*\s*",
        query,
        re.I,
    ):
        return "category_review_count"
    s = get_settings()
    category_words = set(
        normalized(
            " ".join(s.sql_categories + s.rag_categories + requested_categories(query))
        ).split()
    )
    category_words |= {w[:-1] for w in category_words if w.endswith("s")}
    tokens = {w for w in normalized(query).split() if not w.isdigit()}
    if tokens - TEMPLATE_WORDS - category_words:
        return None  # Unknown entity/qualifier: do not silently discard it in a template.
    if re.search(r"\bproduct_avg_rating\b|\baverage product ratings?\b", query, re.I):
        return None
    # These templates do not silently discard requested time windows/subpopulations.
    if re.search(
        r"\b(?:verified|unverified|price|priced|under|over|above|below|since|before|"
        r"after|between|during|month|monthly|year|yearly|date|trend|last|this|past|"
        r"recent|yesterday|today|negative|positive|helpful|store|brand|"
        r"product[- ]level)\b|\b\d{4}\b",
        query,
        re.I,
    ):
        return None
    if LOWEST.search(query):
        without_limit = re.sub(
            r"\b(?:top|bottom|lowest(?:[ -]rated)?)\s+\d+\b", "", query, flags=re.I
        )
        if re.search(
            r"\d|\b(?:per|by|each)\s+categor|\b(?:compare|compared|versus|vs)\b",
            without_limit,
            re.I,
        ):
            return None
        return "lowest_products"
    if (
        re.search(r"\b(?:average|avg|mean)\b", query, re.I)
        and re.search(r"\bratings?\b", query, re.I)
        and re.search(r"\b(?:by|per|each|across)\s+(?:product\s+)?categor(?:y|ies)\b", query, re.I)
        and not re.search(r"\b(?:month|year|date|trend|product[- ]level)\b", query, re.I)
        and not re.search(r"\d", query)
    ):
        return "category_average"
    return None


def product_explanation(query: str) -> bool:
    return bool(LOWEST.search(query) and EXPLAIN.search(query))


def product_limit(query: str) -> int:
    match = re.search(r"\b(?:top|bottom|lowest(?:[ -]rated)?)\s+(\d+)\b", query, re.I)
    return min(25, max(1, int(match[1]))) if match else 1


_QUESTION_START = (
    r"(?:why|what|which|how|when|where|who|can|could|does|do|is|are|show|tell|give|explain)\b"
)
_QUESTION_BOUNDARY = re.compile(
    rf"(?:[?]\s*(?:and\s+|also\s+)?|;\s*(?:and\s+)?|\n+\s*(?:and\s+)?|"
    rf"\s+(?:and|also)\s+)(?={_QUESTION_START})",
    re.I,
)


def independent_questions(query: str) -> list[str]:
    """Bound explicit questions, preserving lists and dependent clauses verbatim.

    No LLM planning or inferred missing subjects: unsupported phrasing stays one
    question. The caller asks the user to shorten requests over four parts.
    """
    parts = [part.strip() for part in _QUESTION_BOUNDARY.split(query) if part.strip()]
    dependent = re.compile(
        r"^(?:(?:show|give|use|take|limit(?: to)?)\s+(?:me\s+)?(?:the\s+)?"
        r"(?:\d+|one|two|three|four|five|ten)(?:\s+(?:products?|results?|items?))?[?.! ]*$|"
        r"(?:why|how|when|where|what)[?.!]*$|why (?:is|was) (?:that|this)|what about|how about|"
        r"(?:why|how|what|when|where)\s+(?:do|does|did|are|is|can|could|will)\s+"
        r"(?:they|it|those|these|that|this)\b)",
        re.I,
    )
    if any(dependent.search(part) for part in parts[1:]):
        return [query]
    if len(parts) < 2 or not all(re.match(_QUESTION_START, p, re.I) for p in parts):
        return [query]
    return [p if p.endswith(("?", ".", "!")) else p + "?" for p in parts]
