import hashlib

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
