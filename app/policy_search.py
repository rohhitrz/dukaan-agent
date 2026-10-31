"""BM25 search over the policy markdown files.

BM25 is keyword scoring, not embeddings: it ranks a chunk by how often the query's
words appear in it, damped by how common those words are across all chunks. Cheap,
no model call, and good enough for six short documents.

Each policy file is split into chunks on blank lines so a hit returns a few bullet
points rather than a whole document.

Phase 1 gives the search its own `retriever` span. It nests under whichever
`tool search_policy` span is open, so the trace separates "the tool ran" from
"this is what BM25 actually returned and how weakly it scored" - the thing
Phase 0 found suspicious about this file.
"""

import logging
import re

from rank_bm25 import BM25Okapi

from app import chaos, tracing
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

    with tracing.client.start_as_current_observation(
        name="policy_search bm25",
        as_type="retriever",
        input={"query": query, "k": k},
    ) as span:
        scores = _bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(scores, _chunks), key=lambda p: p[0], reverse=True)
        hits = [
            {"doc": c["doc"], "title": c["title"], "text": c["text"], "score": round(float(s), 3)}
            for s, c in ranked[:k]
            if s > 0
        ]
        # Phase 2: chaos may drop every hit here. The span still reports
        # chunks_indexed, so "the index is empty" and "nothing matched a query that
        # should have matched" look different in the trace.
        hits = chaos.empty_policy(hits)
        # top_score and the doc names are the two fields worth scanning when an
        # answer turns out ungrounded: a weak top score means nothing matched, and
        # the wrong doc at rank 1 means BM25 matched on the wrong word.
        span.update(
            output=hits,
            metadata={
                "hits": len(hits),
                "chunks_indexed": len(_chunks),
                "top_score": hits[0]["score"] if hits else 0.0,
                "docs": [h["doc"] for h in hits],
            },
            level="WARNING" if not hits else None,
            status_message="no policy chunk matched" if not hits else None,
        )

    log.debug("policy_search %r -> %s", query, [(h["doc"], h["score"]) for h in hits])
    return hits
