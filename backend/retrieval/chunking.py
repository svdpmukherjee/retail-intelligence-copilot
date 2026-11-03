import hashlib
from typing import Any, Literal

from retrieval.provenance import ParentSource
from retrieval.schema import Chunk, make_chunk_id


def chunk_review(row: dict) -> Chunk:
    """One review = one chunk (reviews are short); id is stable across re-runs.

    The embedding is left empty here; the indexer fills it in batches.
    """
    title = (row.get("title") or "").strip()
    body = (row.get("text") or "").strip()
    text = f"{title}\n{body}" if title else body
    text_hash = hashlib.sha1(text.encode()).hexdigest()
    return Chunk(
        id=make_chunk_id("review", row.get("asin"), text_hash),
        source_type="review",
        text=text,
        category=row.get("category"),
        asin=row.get("asin"),
        year=row.get("year"),
    )


def split_sections(markdown: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (title, [(section, body)]) from `# title` / `## section` markdown."""
    title, sections = "", []
    heading, lines = "Overview", []

    def flush() -> None:
        body = "\n".join(lines).strip()
        if body:
            sections.append((heading, body))

    for line in markdown.splitlines():
        if line.startswith("## "):
            flush()
            heading, lines = line[3:].strip(), []
        elif line.startswith("# ") and not title:
            title = line[2:].strip()
        else:
            lines.append(line)
    flush()
    return title, sections


def _bounded(body: str, max_chars: int) -> list[str]:
    """Pack paragraphs into pieces <= max_chars; an oversized paragraph is split on words."""
    pieces, current = [], ""
    for para in (p.strip() for p in body.split("\n\n") if p.strip()):
        while len(para) > max_chars:
            cut = para.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            pieces.append(para[:cut])
            para = para[cut:].strip()
        if current and len(current) + len(para) + 2 > max_chars:
            pieces.append(current)
            current = ""
        current = f"{current}\n\n{para}" if current else para
    if current:
        pieces.append(current)
    return pieces


def chunk_doc(doc_id: str, markdown: str, max_chars: int = 1200) -> list[Chunk]:
    """Section-aware chunks: never spans sections; each carries doc/section metadata.

    Text is prefixed with title and section so a chunk embeds with its own context.
    """
    title, sections = split_sections(markdown)
    title = title or doc_id
    chunks = []
    for section, body in sections:
        for piece in _bounded(body, max_chars):
            index = len(chunks)
            chunks.append(
                Chunk(
                    id=make_chunk_id("doc", doc_id, index),
                    source_type="doc",
                    text=f"{title} - {section}\n{piece}",
                    doc_id=doc_id,
                    doc_title=title,
                    section=section,
                    chunk_index=index,
                )
            )
    return chunks


# Version 2 is explicit: legacy serving chunks are not silently rewritten.
CHUNKER_VERSION = "token-offset-v1"


def source_parent(
    row: dict, source_snapshot: str, *, source_type: Literal["review", "doc"] = "review"
) -> ParentSource:
    from governance.pii import redact
    from retrieval.normalization import normalize_source
    from retrieval.provenance import content_hash, review_parent_id

    if source_type == "review":
        parent_id, identity_kind = review_parent_id(row)
        raw = "\n".join(str(row.get(k) or "") for k in ("title", "text")).strip()
    else:
        if not row.get("doc_id"):
            raise ValueError("Document identity missing")
        parent_id, identity_kind = make_chunk_id("doc", row["doc_id"]), "doc_path_v1"
        raw = row["text"]
    normalized = normalize_source(raw)
    fields = {
        k: row.get(k)
        for k in (
            "category",
            "asin",
            "rating",
            "timestamp",
            "product_title",
            "price",
            "product_avg_rating",
            "year",
            "doc_id",
            "doc_title",
            "section",
            "source",
        )
    }
    for key in ("product_title", "doc_title", "section"):
        if fields[key]:
            fields[key] = redact(normalize_source(fields[key]).text)
    return ParentSource(
        parent_id=parent_id,
        identity_kind=identity_kind,
        source_type=source_type,
        text=normalized.text,
        source_snapshot=source_snapshot,
        source_hash=normalized.source_hash,
        content_hash=content_hash(normalized.text),
        normalization_version=normalized.version,
        sample_membership=row.get("sample_membership", []),
        **fields,
    )


def chunk_parent(
    parent: ParentSource, tokenizer: Any, *, max_tokens: int, overlap: int = 24
) -> list[Chunk]:
    """Bound by the actual embedding tokenizer; offsets refer to normalized parent text."""
    if not 0 <= overlap < max_tokens:
        raise ValueError("Overlap must be smaller than the token budget")
    budget = max_tokens - tokenizer.num_special_tokens_to_add(pair=False)
    if budget <= overlap:
        raise ValueError("Token budget must include special tokens and overlap")
    encoded = tokenizer(
        parent.text,
        add_special_tokens=False,
        return_offsets_mapping=True,
        truncation=False,
        verbose=False,
    )
    offsets = encoded["offset_mapping"]
    chunks = []
    cursor = 0
    while cursor < len(offsets):
        stop = min(cursor + budget, len(offsets))
        start_char = offsets[cursor][0]
        end_char = offsets[stop - 1][1]
        # Some tokenizers map multiple tokens to one unicode character. Shrink the
        # window until re-encoding the exact slice satisfies the real bound.
        while len(tokenizer.encode(parent.text[start_char:end_char])) > max_tokens:
            stop -= 1
            if stop <= cursor:
                raise ValueError("Tokenizer cannot bound this source span")
            end_char = offsets[stop - 1][1]
        index = len(chunks)
        chunks.append(
            Chunk(
                id=make_chunk_id(parent.parent_id, parent.content_hash, CHUNKER_VERSION, index),
                source_type=parent.source_type,
                text=parent.text[start_char:end_char],
                category=parent.category,
                asin=parent.asin,
                year=parent.year,
                doc_id=parent.doc_id,
                doc_title=parent.doc_title,
                section=parent.section,
                source=parent.source,
                chunk_index=index,
                parent_id=parent.parent_id,
                rating=parent.rating,
                timestamp=parent.timestamp,
                product_title=parent.product_title,
                source_snapshot=parent.source_snapshot,
                content_hash=parent.content_hash,
                normalization_version=parent.normalization_version,
                chunker_version=CHUNKER_VERSION,
                start_char=start_char,
                end_char=end_char,
            )
        )
        if stop == len(offsets):
            break
        cursor = max(cursor + 1, stop - overlap)
    if not chunks:
        raise ValueError("Source has no tokens")
    return chunks
