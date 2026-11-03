"""Bounded source-backed presentation helpers; no semantic-support guarantee."""

import re
from decimal import Decimal

from governance.pii import redact
from retrieval.normalization import normalize_source


def plain_source(text: str) -> str:
    try:
        return normalize_source(text).text
    except ValueError:
        return ""


def resolved_update(text: str) -> str | None:
    markers = list(re.finditer(r"\b(?:update[d]?|edit(?:ed)?|correction)\b\s*[:\-]?", text, re.I))
    if not markers:
        return None
    update = text[markers[-1].start() :]
    negated = re.search(
        r"\b(?:not|never|hasn't|isn't|wasn't|didn't|still)\b.{0,25}\b(?:fix\w*|resolv\w*|work\w*)",
        update,
        re.I,
    )
    if not negated and re.search(r"\b(?:fixed|resolved|works? now|no longer)\b", update, re.I):
        return update
    return None


def source_terms(text: str) -> set[str]:
    stop = set(
        (
            "what why how does are was were will with and but for from after before "
            "have has had not did only this that there their they about our its into some "
            "them when which who customer customers review reviews product products return "
            "policy lowest rated unhappy disappointing most say says can cant"
        ).split()
    )
    return {
        re.sub(r"(?:ing|ed|s)$", "", word).rstrip("e")
        for word in re.findall(r"\w{3,}", text.lower())
        if word not in stop
    }


def source_body(text: str) -> tuple[str, str]:
    lines = text.split("\n", 1)
    if (
        len(lines) == 2
        and lines[1].strip()
        and len(lines[0]) < 220
        and not re.search(r"[.!?]$", lines[0])
    ):
        return lines[0], lines[1].strip()
    return "", text


def excerpt(text: str, query: str = "", limit: int = 240) -> str:
    """Quote body text, not its title; retain later resolutions and nearby context."""
    title, body = source_body(text)
    update = resolved_update(text)
    chosen_source = update or body
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", chosen_source) if s.strip()]
    terms = source_terms(query)
    hints = source_terms(title)
    negative = bool(re.search(r"\b(?:why|complain\w*|unhappy|disappoint\w*)\b", query, re.I))

    def score(item):
        index, sentence = item
        words = source_terms(sentence)
        value = 3 * len(terms & words) + len(hints & words)
        if negative and re.search(
            r"\b(?:fail\w*|not|doesn't|couldn't|cant|hot|burn\w*|fall\w*|broke\w*|losing|stopped)\b",
            sentence,
            re.I,
        ):
            value += 2
        if update and re.search(r"\b(?:fixed|resolved|works? now|no longer)\b", sentence, re.I):
            value += 5
        if len(sentence) < 20:
            value -= 3
        if len(sentence) > limit:
            value -= 2
        return value, -index

    if sentences:
        index, chosen = max(enumerate(sentences), key=score)
        # A following short sentence can contain the actual failure or resolution.
        for next_sentence in sentences[index + 1 : index + 3]:
            if len(chosen) + len(next_sentence) + 1 > limit:
                break
            chosen += " " + next_sentence
    else:
        chosen = chosen_source.strip()
    if len(chosen) <= limit:
        return chosen
    return chosen[:limit].rsplit(" ", 1)[0] + "…"


def source_relevance(text: str, query: str) -> int:
    return len(source_terms(query) & source_terms(excerpt(text, query)))


def readable(name: str) -> str:
    return name.replace("_", " ").strip()


def number(value: object) -> str:
    if isinstance(value, (int, float, Decimal)):
        return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"
    return redact(str(value))


def sql_summary(result: dict) -> str:
    """Narrate only the actual result; unknown shapes get a neutral table introduction."""
    columns, rows = result["columns"], result["rows"]
    if not rows:
        return "No matching results were found within the available data."
    if result.get("metric") == "average_price":
        at = dict(zip(columns, rows[0], strict=True))
        value = at.get("average_product_price")
        if value is None:
            return "No recorded prices were available for the matching products. [1]"
        return (
            f"Average recorded product price: {number(value)}, across "
            f"{number(at['priced_products'])} "
            f"products with prices; {number(at['products_missing_price'])} products "
            f"have no recorded price. " + result.get("price_basis", "") + " [1]"
        )
    if result.get("metric") in {"list_products", "price_rank"}:
        title_note = (
            f" Product names contain the literal text ‘{plain_source(result['title_contains'])}’."
            if result.get("title_contains")
            else ""
        )
        return (
            f"Here are {len(rows)} matching products in the requested order."
            + title_note
            + " "
            + result.get("price_basis", "")
            + " [1]"
        )
    if result.get("minimum_review_count") and "product_title" in columns:
        at = {c: i for i, c in enumerate(columns)}
        descriptions = []
        for row in rows[:3]:
            title = plain_source(str(row[at["product_title"]] or "Unnamed product"))
            descriptions.append(
                f"{title}: {float(row[at['avg_rating']]):.2f}/5 "
                f"across {number(row[at['review_count']])} reviews"
            )
        return (
            (
                f"Selected products averaging below {result['average_below']:g}/5 (minimum "
                if result.get("average_below") is not None
                else "Selected lowest-rated products (minimum "
            )
            + str(result["minimum_review_count"])
            + " reviews each): "
            + "; ".join(descriptions)
            + ". [1]"
            + (
                " These are the lowest averages among products meeting your review-count "
                "requirement; "
                "their averages are still at least 4/5, so this selection does not "
                "establish that they are poorly rated overall. [1]"
                if all(float(row[at["avg_rating"]]) >= 4 for row in rows)
                else ""
            )
        )
    numeric = [
        i
        for i in range(len(columns))
        if all(
            isinstance(row[i], (int, float, Decimal)) and not isinstance(row[i], bool)
            for row in rows
        )
    ]
    if len(rows) == 1 and len(columns) == 1 and numeric:
        return f"{readable(columns[0]).capitalize()}: {number(rows[0][0])}. [1]"
    measure = [
        i
        for i in numeric
        if re.search(r"avg|average|mean|rating|count|reviews|^n$", columns[i], re.I)
        and not re.search(r"year|month|date", columns[i], re.I)
    ]
    if result.get("metric") == "review-weighted average rating" and "avg_rating" in columns:
        measure = [columns.index("avg_rating")]
    labels = [i for i, c in enumerate(columns) if c == "category"]
    if len(measure) == 1 and labels and not result.get("has_more"):
        mi, li = measure[0], labels[0]
        low, high = min(r[mi] for r in rows), max(r[mi] for r in rows)

        def names(value):
            tied = [readable(str(r[li])) for r in rows if r[mi] == value]
            return ", ".join(tied[:3]) + (
                f" and {len(tied)-3} other categories" if len(tied) > 3 else ""
            )

        metric = readable(columns[mi])
        if high == low:
            return f"All returned categories have the same {metric}: {number(high)}. [1]"
        return (
            f"Among the returned categories, the highest {metric} is {names(high)} "
            f"({number(high)}); the lowest is {names(low)} ({number(low)}). [1]"
        )
    if result.get("has_more"):
        return "Here is the first part of the calculated results; more matches are available. [1]"
    return "Here are the calculated results. [1]"


def draft_issues(
    draft: str, source_text: dict[int, str], *, has_sql: bool, has_reviews: bool = True
) -> list[str]:
    from governance.grounding import citation_numbers

    issues = []
    prose = re.sub(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", draft)
    if has_reviews and re.search(
        r"\b(?:most|majority|frequent\w*|common\w*|widespread|many|generally|usually|typically|often)\b",
        prose,
        re.I,
    ):
        issues.append("unmeasured prevalence claim")
    if has_sql and re.search(
        r"\d|\b(?:highest|lowest|above|below|more than|less than|largest|smallest)\b", prose, re.I
    ):
        issues.append("numeric/ranking prose must use the calculated summary")
    if re.match(r"\s*(?:[)]+|Here['’](?!s\b))", draft):
        issues.append("malformed generation")
    for line in draft.splitlines():
        if not has_reviews and re.search(r"\bfull refund\b|\brefunded in full\b", line, re.I):
            cited = " ".join(source_text.get(n, "") for n in citation_numbers(line))
            if not re.search(r"\bfull refund\b|\brefunded in full\b", cited, re.I):
                issues.append("full-refund claim unsupported by its cited policy passage")
        for n in citation_numbers(line):
            if resolved_update(source_text.get(n, "")):
                affirm_fix = re.search(
                    r"\b(?:fixed|resolved|no longer|replacement worked)\b", line, re.I
                )
                ongoing = re.search(
                    r"\b(?:persistent|persists?|still|ongoing|currently|continues?|keeps)\b",
                    line,
                    re.I,
                )
                denied_fix = re.search(
                    r"\b(?:not|never|wasn't|isn't|didn't)\b.{0,20}\b(?:fixed|resolved)\b",
                    line,
                    re.I,
                )
                if not affirm_fix or ongoing or denied_fix:
                    issues.append("review update omitted or contradicted")
    return list(dict.fromkeys(issues))
