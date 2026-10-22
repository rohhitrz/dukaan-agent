"""BM25 search over the policy markdown files.

BM25 is keyword scoring, not embeddings: it ranks a chunk by how often the query's
words appear in it, damped by how common those words are across all chunks. Cheap,
no model call, and good enough for six short documents.

Each policy file is split into chunks on blank lines so a hit returns a few bullet
points rather than a whole document.
"""

import logging
import re

from rank_bm25 import BM25Okapi

from app.config import settings

log = logging.getLogger(__name__)

_chunks: list[dict] = []
_bm25: BM25Okapi | None = None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def load_policies() -> None:
    """Read the policy files and build the BM25 index. Called once at startup."""
    global _chunks, _bm25

    _chunks = []
    for path in sorted(settings.policies_dir.glob("*.md")):
        text = path.read_text()
        title = text.splitlines()[0].lstrip("# ").strip()
        # Split on blank lines; keep the heading with every chunk for context.
        for block in [b.strip() for b in text.split("\n\n") if b.strip()]:
            if block.startswith("#"):
                continue
            _chunks.append({"doc": path.stem, "title": title, "text": block})

    _bm25 = BM25Okapi([_tokenize(c["title"] + " " + c["text"]) for c in _chunks])
    log.info("indexed %d policy chunks from %d files", len(_chunks), len(set(c["doc"] for c in _chunks)))


def search(query: str, k: int = 3) -> list[dict]:
    """Top-k policy chunks for a query, each with its BM25 score."""
    if _bm25 is None:
        load_policies()

    scores = _bm25.get_scores(_tokenize(query))
    ranked = sorted(zip(scores, _chunks), key=lambda p: p[0], reverse=True)
    hits = [
        {"doc": c["doc"], "title": c["title"], "text": c["text"], "score": round(float(s), 3)}
        for s, c in ranked[:k]
        if s > 0
    ]
    log.debug("policy_search %r -> %s", query, [(h["doc"], h["score"]) for h in hits])
    return hits
