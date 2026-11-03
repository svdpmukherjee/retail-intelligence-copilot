"""One-pass source HTML decoding with a versioned normalized result; no rendering."""

import re
from html.parser import HTMLParser

from pydantic import BaseModel

from governance.pii import redact
from retrieval.provenance import content_hash

NORMALIZATION_VERSION = "html-plain-pii-v1"
BLOCKS = {
    "p",
    "div",
    "br",
    "li",
    "ul",
    "ol",
    "h1",
    "h2",
    "h3",
    "tr",
    "td",
    "th",
    "blockquote",
    "hr",
}
HIDDEN = {"script", "style", "template", "iframe", "object"}


class NormalizedText(BaseModel):
    text: str
    source_hash: str
    version: str = NORMALIZATION_VERSION


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in HIDDEN:
            self.hidden.append(tag)
        if not self.hidden and tag in BLOCKS:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        if tag not in HIDDEN and not self.hidden and tag in BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            return
        if tag in BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def normalize_source(value: str | NormalizedText) -> NormalizedText:
    """Idempotent on versioned results; decoded text is never parsed/decoded again.

    A plain string is always raw source. Retaining the version is essential for
    literal entities such as &amp;lt; and prevents repeated decoding on rebuilds.
    """
    if isinstance(value, NormalizedText):
        if value.version != NORMALIZATION_VERSION:
            raise ValueError("Unsupported normalization version")
        return value
    if not isinstance(value, str):
        raise ValueError("Source must be text")
    parser = _PlainText()
    parser.feed(value)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    text = "\n".join(re.sub(r"[^\S\n]+", " ", line).strip() for line in text.splitlines())
    text = redact(re.sub(r"\n{3,}", "\n\n", text).strip())
    if not text:
        raise ValueError("Source has no usable text")
    return NormalizedText(text=text, source_hash=content_hash(value))
