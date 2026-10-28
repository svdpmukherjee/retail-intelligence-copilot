import re

# Public so the composer derives the cited set with the exact pattern the gate enforces.
CITE = re.compile(r"\[(\d+)\]")


def enforce_grounding(answer: str, valid: set[int]) -> list[str]:
    """Grounding gate: dangling [n], uncited claim lines, and citation-free answers are issues."""
    issues = [
        f"dangling citation [{n}]" for n in sorted({int(m) for m in CITE.findall(answer)} - valid)
    ]
    for sentence in filter(None, (s.strip() for s in re.split(r"(?<=[.!?\]])\s*\n+|\n+", answer))):
        if not CITE.search(sentence):
            issues.append(f"uncited claim: {sentence[:60]}")
    if not CITE.search(answer):
        issues.append("answer has no citations")
    return issues
