import argparse
import re
from pathlib import Path

from pypdf import PdfReader

from retrieval.chunking import chunk_doc
from retrieval.index_reviews import REPO_ROOT, embed_and_upsert

DOCS_ROOT = REPO_ROOT / "data" / "docs"
# Manual PDFs mark sections as "1. Setup"; recover them as markdown headings.
PDF_HEADING = re.compile(r"^\d+\.\s+\S.*[^.]$")


def pdf_to_markdown(path: Path) -> str:
    """Extract PDF text as `# title` + `## section` markdown (first line is the title)."""
    reader = PdfReader(str(path))
    lines = [ln.strip() for page in reader.pages for ln in (page.extract_text() or "").splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        raise ValueError(f"No extractable text in {path}")
    out = [f"# {lines[0]}"]
    out += [f"## {ln}" if PDF_HEADING.match(ln) else ln for ln in lines[1:]]
    return "\n".join(out)


def read_docs(root: Path = DOCS_ROOT) -> list[tuple[str, str]]:
    """(doc_id, markdown) for every .md/.pdf under root; doc_id is the relative path sans suffix."""
    if not root.exists():
        raise FileNotFoundError(f"Docs directory not found at {root}")
    docs = []
    for path in sorted(root.rglob("*")):
        if path.suffix == ".md":
            text = path.read_text(encoding="utf-8")
        elif path.suffix == ".pdf":
            text = pdf_to_markdown(path)
        else:
            continue
        docs.append((path.relative_to(root).with_suffix("").as_posix(), text))
    return docs


def index_docs(root: Path = DOCS_ROOT) -> dict:
    """Parse, chunk, embed, and upsert policy/manual docs; re-runs hit the same ids."""
    chunks = [c for doc_id, text in read_docs(root) for c in chunk_doc(doc_id, text)]
    return embed_and_upsert(chunks)


def main() -> None:
    argparse.ArgumentParser(description="Embed data/docs into the vector store.").parse_args()
    result = index_docs()
    print(f"indexed={result['indexed']} tokens~{result['tokens']} usd=${result['usd']:.4f}")


if __name__ == "__main__":
    main()
