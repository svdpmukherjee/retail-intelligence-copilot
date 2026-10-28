"""Single source of truth for PII patterns, shared by Silver (Spark), memory and the composer.

Patterns are plain strings so Spark `regexp_replace` (Java regex) and Python `re` both use them;
they stay within the syntax both engines share.
"""

import re

EMAIL_PATTERN = r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"

_SEP = r"[\s.\-]?"
# Most specific forms first: alternation is leftmost-first, so a looser form must not pre-empt.
_PHONE_FORMS = [
    # International: explicit '+<cc>' then 7-12 digits in any grouping, incl. '(0)' trunk digit.
    r"(?<![\w+])\+\d{1,3}" + _SEP + r"(?:\(0\))?\d(?:" + _SEP + r"\d){6,11}(?!\w)",
    # UK national: 020 7946 0958, 07911 123456, 01632 960 001 (leading 0 required).
    r"(?<!\w)0\d{2}" + _SEP + r"\d{4}" + _SEP + r"\d{4}(?!\w)",
    r"(?<!\w)0\d{3,4}" + _SEP + r"\d{3}" + _SEP + r"\d{3,4}(?!\w)",
    # US/NANP: optional country code, 3-3-4 (the M2 form, unchanged).
    r"(?<!\w)(?:\+?\d{1,3}"
    + _SEP
    + r")?(?:\(\d{3}\)|\d{3})"
    + _SEP
    + r"\d{3}"
    + _SEP
    + r"\d{4}(?!\w)",
    # Bare 7-digit local form (555-0142).
    r"(?<!\w)\d{3}[\s.\-]\d{4}(?!\w)",
]
PHONE_PATTERN = "|".join(_PHONE_FORMS)

_EMAIL = re.compile(EMAIL_PATTERN)
_PHONE = re.compile(PHONE_PATTERN)


def redact(text: str) -> str:
    """Replace emails and phone numbers with [EMAIL] / [PHONE] placeholders."""
    return _PHONE.sub("[PHONE]", _EMAIL.sub("[EMAIL]", text))
