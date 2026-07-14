"""
indexer.py — chunk paper text, embed it, and persist to SQLite + ChromaDB
[SPEC_Phase1 §3.2 steps 3-5].

Pipeline per paper:
    abstract -> chunk_text(...) -> llm.embed(...) -> store.add_vectors(...)
                                                  -> store.insert_chunks(...)

The `vector_id` is what ties the two stores together: it is the Chroma id AND the
`chunks.vector_id` column, so a Chroma hit always resolves back to a citable paper.
"""

import llm
from db import store

# SPEC_Phase1 §3.2: chunks of ~200-400 words with ~50 words of overlap.
# We target the top of that band; PubMed abstracts are typically 200-300 words, so
# most papers yield exactly one chunk, and only long structured abstracts split.
CHUNK_SIZE    = 350   # words
CHUNK_OVERLAP = 50    # words carried from the tail of the previous chunk

# Below this, a trailing fragment carries no retrievable meaning ("CONCLUSIONS:")
# and would only add noise to the vector store.
MIN_CHUNK_WORDS = 20


def chunk_text(text: str, size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split `text` into overlapping word windows.

    Overlap exists so a sentence straddling a boundary still appears whole in at
    least one chunk — otherwise the fact it states could never be retrieved.
    """
    if overlap >= size:
        raise ValueError(f"overlap ({overlap}) must be smaller than size ({size})")

    words = text.split()
    if not words:
        return []
    if len(words) <= size:
        return [" ".join(words)]

    chunks = []
    step   = size - overlap
    for start in range(0, len(words), step):
        window = words[start:start + size]

        # Drop a short trailing remnant, but never drop the only chunk we have.
        if len(window) < MIN_CHUNK_WORDS and chunks:
            break

        chunks.append(" ".join(window))

        if start + size >= len(words):   # this window reached the end
            break

    return chunks


def index_paper(paper: dict) -> dict:
    """
    Persist one paper and its chunk vectors. Idempotent: a paper already in SQLite
    is skipped, so re-running the same keyword search does not duplicate vectors.

    Returns {pmid, paper_id, n_chunks, skipped}.
    """
    if store.paper_exists(paper["pmid"]):
        return {"pmid": paper["pmid"], "paper_id": None,
                "n_chunks": 0, "skipped": True}

    paper_id = store.insert_paper(paper)

    # Only text we are allowed to keep [SPEC_Phase1 §3.3]. full_text stays None in
    # Phase 1, but the concat is written this way so enabling open-access full text
    # later needs no change here.
    body   = paper.get("full_text") or paper.get("abstract") or ""
    source = f"{paper.get('title', '')}. {body}".strip()
    texts  = chunk_text(source)

    if not texts:
        return {"pmid": paper["pmid"], "paper_id": paper_id,
                "n_chunks": 0, "skipped": False}

    # kind="passage": these are documents, not questions. The query side adds an instruction
    # prefix that must NOT appear here [llm.embed].
    vectors    = llm.embed(texts, kind="passage")
    vector_ids = [f"{paper['pmid']}::{i}" for i in range(len(texts))]

    # Metadata duplicated into Chroma purely so a hit can be rendered even if the
    # SQLite join is skipped; SQLite stays the source of truth for citations.
    metadatas = [
        {
            "pmid":        paper["pmid"],
            "title":       paper.get("title", ""),
            "year":        paper.get("year") or 0,
            "chunk_index": i,
        }
        for i in range(len(texts))
    ]

    # Chroma first: if embedding or the vector write fails, we raise before writing
    # chunk rows, so SQLite never claims a chunk whose vector does not exist.
    store.add_vectors(vector_ids, vectors, texts, metadatas)
    store.insert_chunks(paper_id, [
        {"chunk_text": t, "chunk_index": i, "vector_id": vid}
        for i, (t, vid) in enumerate(zip(texts, vector_ids))
    ])

    return {"pmid": paper["pmid"], "paper_id": paper_id,
            "n_chunks": len(texts), "skipped": False}


def index_papers(papers: list[dict]) -> dict:
    """
    Index a batch. One bad paper must not abort the whole ingest run, so failures
    are collected and reported rather than raised.
    """
    added, skipped, failed, total_chunks = [], [], [], 0

    for paper in papers:
        try:
            res = index_paper(paper)
            if res["skipped"]:
                skipped.append(res["pmid"])
            else:
                added.append(res["pmid"])
                total_chunks += res["n_chunks"]
        except Exception as exc:
            failed.append({"pmid": paper.get("pmid", "?"), "error": str(exc)})

    return {
        "added":        added,
        "skipped":      skipped,
        "failed":       failed,
        "n_added":      len(added),
        "n_skipped":    len(skipped),
        "n_failed":     len(failed),
        "total_chunks": total_chunks,
    }
