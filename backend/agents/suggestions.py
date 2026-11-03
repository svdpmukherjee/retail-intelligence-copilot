"""Executable next questions derived from the active request, never random topics."""

import re
from typing import Literal

from pydantic import BaseModel

from agents.query_plan import requested_categories
from governance.policy import scope_for_role


class NextAction(BaseModel):
    action: Literal["category_averages", "category_counts", "praise", "complaints", "returns"]
    category: str | None = None


def render_suggestions(
    role: str,
    query: str = "",
    actions: list | None = None,
    *,
    parts: list[dict] | None = None,
    result: dict | None = None,
) -> list[str]:
    """Use validated plan/result context; unsupported or out-of-role prompts never appear."""
    allowed = scope_for_role(role).get("category")
    categories = [c for c in requested_categories(query) if allowed is None or c in allowed]
    category = categories[0] if categories else (allowed[0] if allowed else None)
    label = (category or "all categories").replace("_", " ")
    proposals = []
    for part in parts or []:
        pq = part.get("product_query")
        selection = part.get("selection")
        part_categories = requested_categories(part.get("query", ""))
        part_label = ", ".join(c.replace("_", " ") for c in part_categories) or label
        if pq:
            term = pq.get("title_contains")
            subject = (
                f'{part_label} products with "{term}" in the product name'
                if term
                else f"{part_label} products"
            )
            for field, word in (("price_below", "below"), ("price_above", "above")):
                if pq.get(field) is not None:
                    subject += f" with recorded price {word} {pq[field]:g}"
            if pq["operation"] == "average_price":
                proposals.extend(
                    [
                        f"Show the 10 cheapest {subject} by recorded price",
                        f"Show the 10 most expensive {subject} by recorded price",
                    ]
                )
            else:
                direction = "most expensive" if pq.get("order") == "price_asc" else "cheapest"
                proposals.extend(
                    [
                        f"What is the average recorded price of {subject}?",
                        f"Show the 10 {direction} {subject} by recorded price",
                    ]
                )
            proposals.append(f"How many {subject} are in the data?")
        elif selection:
            minimum = selection["minimum_reviews"]
            threshold = selection.get("average_below")
            empty = (result or {}).get("audit", {}).get("sql_outcome") == "empty"
            if empty:
                relaxed = 2
                proposals.append(
                    f"Show five {part_label} products averaging below {threshold:g} with at "
                    f"least {relaxed} reviews"
                    if threshold
                    else (
                        f"Show five lowest average {part_label} products "
                        f"with at least {relaxed} reviews"
                    )
                )
            rank_question = (
                f"Show five lowest average {part_label} products with at least {minimum} reviews"
            )
            if empty:
                proposals.insert(0, rank_question)
            else:
                proposals.append(rank_question)
            proposals.append(
                f"Why are the lowest average {part_label} products disappointing "
                f"customers? Use five products with at least {minimum} reviews"
            )
            if threshold:
                proposals.append(
                    f"Show five {part_label} products averaging below "
                    f"{min(5, threshold + 1):g} with at least {minimum} reviews"
                )
        elif part.get("intent") == "docs_rag":
            proposals.extend(
                [
                    "How long do customers have to report a damaged item under our return policy?",
                    "What does our return policy say about opened electronics?",
                    "What does our return policy say about refunds for damaged items?",
                ]
            )
    if not proposals:
        if re.search(r"\b(?:policy|return|refund|warranty)\b", query, re.I) and not re.search(
            r"\b(?:reviews?|praise|dislike)\b", query, re.I
        ):
            proposals = [
                "What does our return policy say about opened electronics?",
                "What does our return policy say about refunds for damaged items?",
            ]
        else:
            sentiment = (
                "praise" if re.search(r"dislike|complain|negative", query, re.I) else "dislike"
            )
            proposals = [
                f"What do customers {sentiment} about {label} products?",
                f"What is the average customer rating for {label} products?",
                f"How many reviews are there for {label} products?",
            ]
    # Model-selected actions can supplement this topic, never insert unrelated policy
    # or forbidden-category questions into a price/product conversation.
    if not parts:
        for raw in actions or []:
            try:
                item = NextAction.model_validate(raw)
            except ValueError:
                continue
            if item.category and (
                requested_categories(item.category) != [item.category]
                or (allowed is not None and item.category not in allowed)
            ):
                continue
            if (
                item.category
                and category == item.category
                and item.action in {"praise", "complaints"}
            ):
                proposals.append(
                    f"What do customers {'praise' if item.action == 'praise' else 'dislike'} "
                    f"about {label} products?"
                )
    if len(parts or []) > 1 and any(p.get("intent") == "docs_rag" for p in parts):
        policy = next((q for q in proposals if "return policy" in q), None)
        if policy:
            proposals = proposals[:2] + [policy] + proposals[2:]
    result_questions = []
    for question in proposals:
        if any(allowed is not None and c not in allowed for c in requested_categories(question)):
            continue
        if question.lower().rstrip("?. ") == query.lower().rstrip("?. "):
            continue
        if question not in result_questions:
            result_questions.append(question)
        if len(result_questions) == 3:
            break
    return result_questions
