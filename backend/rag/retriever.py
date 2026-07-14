"""
retriever.py — question -> the paper passages that can ground the answer
[SPEC_Phase1 §5.1 steps 2-3].

    embed(question) -> Chroma top-k -> resolve to SQLite -> citation-ready sources

The retriever never talks to the LLM. It only decides WHAT the LLM is allowed to
read, which is what makes the "grounded or silent" rule of SPEC_Phase1 §0 enforceable.
"""

import llm
from db import store

# SPEC_Phase1 §5.1: k ~ 4-6.
DEFAULT_K = 5

# Cosine distance (0 = identical, 1 = orthogonal); the collection uses hnsw:space=cosine and
# llm.embed() returns L2-normalised vectors.
#
# CALIBRATED, not guessed. With bge-small-en-v1.5, the probe query
# "What does a second melt peak in HRM indicate?" scores:
#
#     a genuinely relevant passage .... ~0.30
#     an off-topic sentence ("pizza") . ~0.57
#
# 0.45 sits in the gap. This threshold is the ONLY thing standing behind the §0 promise
# "grounded or silent": it is what lets retrieve() return nothing when the corpus holds
# nothing relevant, so the caller can refuse to answer instead of citing five papers that
# happen to be the least-bad matches. The previous embedding model made every distance land
# in a 0.10-0.21 band, so no threshold could work at all and this guard never once fired.
MAX_DISTANCE = 0.45

# No single paper may occupy more than this many of the k slots. Chunks from one abstract are
# near-duplicates of each other, so without a cap a single verbose paper can win every slot
# and the "five sources" behind an answer are really one — which is exactly the kind of
# false corroboration a reader cannot see and would never suspect.
MAX_CHUNKS_PER_PAPER = 2

# Over-fetch before diversifying: the per-paper cap discards hits, so the candidate pool has
# to be deeper than k or the cap would just shrink the result set.
_CANDIDATE_MULTIPLIER = 4


def retrieve(question: str, k: int = DEFAULT_K) -> list[dict]:
    """
    Return the passages relevant to `question`, nearest-first:

        [{n, chunk_text, distance, pmid, title, authors, journal, year, url}]

    `n` is the citation number the LLM must use ([1], [2], ...). Returns [] when the knowledge
    base is empty or nothing clears MAX_DISTANCE — the caller must then refuse to answer from
    papers rather than let the LLM improvise [§0].
    """
    if not question.strip():
        return []

    # kind="query": bge is an asymmetric retriever and the query side needs its instruction
    # prefix. Embedding a question as if it were a passage silently costs accuracy.
    query_vector = llm.embed([question], kind="query")[0]

    candidates = store.query_vectors(query_vector, k=k * _CANDIDATE_MULTIPLIER)
    candidates = [h for h in candidates if h["distance"] <= MAX_DISTANCE]
    if not candidates:
        return []

    # One SQLite round-trip for the whole candidate set, not one per hit.
    meta = store.get_chunks_by_vector_ids([h["vector_id"] for h in candidates])

    sources: list[dict] = []
    per_paper: dict[str, int] = {}

    for h in candidates:                     # already nearest-first
        m = meta.get(h["vector_id"])
        if m is None:
            # Vector present in Chroma but its chunk row is gone — the two stores have
            # drifted. Skip it: an uncitable passage is useless here by definition.
            continue

        pmid = m["pmid"]
        if per_paper.get(pmid, 0) >= MAX_CHUNKS_PER_PAPER:
            continue
        per_paper[pmid] = per_paper.get(pmid, 0) + 1

        sources.append({
            "n":          len(sources) + 1,   # assigned after filtering, so [n] stays dense
            "chunk_text": m["chunk_text"],
            "distance":   round(h["distance"], 4),
            "pmid":       pmid,
            "title":      m["title"],
            "authors":    m["authors"],
            "journal":    m["journal"],
            "year":       m["year"],
            "url":        m["url"],
        })

        if len(sources) >= k:
            break

    return sources


def stabilise_numbers(sources: list[dict], registry: list[dict] | None) -> list[dict]:
    """
    Keep a paper's citation number the SAME for the whole conversation.

    Numbers are otherwise assigned per query, so turn 1 might cite paper A as [1] while turn 2
    retrieves a different set and calls paper D [1]. The transcript still carries turn 1's
    "[1]", so the model — and the reader — end up with one number meaning two papers. The
    citation is then worse than useless: it is confidently wrong, and nothing on screen reveals it.

    `registry` is the accumulated [{n, pmid}] the client sends back each turn. A paper already
    in it keeps its number; anything new takes the next free one.

    Returns the updated registry (sources are renumbered in place).
    """
    known: dict[str, int] = {}
    for entry in registry or []:
        pmid = entry.get("pmid")
        n    = entry.get("n")
        if pmid and isinstance(n, int):
            known[pmid] = n

    next_n = max(known.values(), default=0) + 1

    for s in sources:
        if s["pmid"] in known:
            s["n"] = known[s["pmid"]]
        else:
            s["n"] = next_n
            known[s["pmid"]] = next_n
            next_n += 1

    # Nearest-first is the useful order for the model; the numbers no longer encode rank.
    return [{"n": n, "pmid": pmid} for pmid, n in sorted(known.items(), key=lambda kv: kv[1])]


def to_citations(sources: list[dict]) -> list[dict]:
    """Strip the passage text — what the frontend needs to render the sources panel."""
    return [
        {
            "n":       s["n"],
            "pmid":    s["pmid"],
            "title":   s["title"],
            "authors": _format_authors(s["authors"]),
            "journal": s["journal"],
            "year":    s["year"],
            "url":     s["url"],
        }
        for s in sources
    ]


def _format_authors(authors: list[str]) -> str:
    """'Chen C et al.' — the citation convention, not a full author dump."""
    if not authors:
        return ""
    if len(authors) <= 2:
        return ", ".join(authors)
    return f"{authors[0]} et al."
