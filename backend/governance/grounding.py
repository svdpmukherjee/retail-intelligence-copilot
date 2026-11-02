import re

# Public so the composer derives the cited set with the exact pattern the gate enforces.
CITE = re.compile(r"\[(\d+)\]")

# A grounded answer leads with a plain-language takeaway (often uncited) and cites its evidence
# lines. We require that at least this fraction of lines carry a citation: enough to stop a model
# from ignoring the sources and free-writing, without forcing a citation onto the summary sentence.
MIN_CITED_FRACTION = 0.5


def enforce_grounding(answer: str, valid: set[int]) -> list[str]:
    """Grounding gate. Blocking issues: a citation to a source that was not provided (dangling),
    an answer with no citations at all, and an answer whose lines are mostly uncited (the model
    ignored the sources). A summary lead sentence may be uncited if the evidence lines are cited."""
    issues = [
        f"dangling citation [{n}]" for n in sorted({int(m) for m in CITE.findall(answer)} - valid)
    ]
    lines = [s.strip() for s in re.split(r"(?<=[.!?\]])\s*\n+|\n+", answer) if s.strip()]
    cited = [line for line in lines if CITE.search(line)]
    if not cited:
        issues.append("answer has no citations")
    elif lines and len(cited) / len(lines) < MIN_CITED_FRACTION:
        issues.append(f"mostly uncited ({len(cited)} of {len(lines)} lines cited)")
    return issues
