"""
store.py — the two Phase 1 stores: SQLite (structured) + ChromaDB (vectors).

[SPEC_Phase1 §3.4, §7]

SQLite  — papers + chunks; the source of truth for citation metadata.
ChromaDB — one embedding per chunk; used only to find WHICH chunks are relevant.

Split rationale: Chroma is good at "which text is semantically close", bad as a
system of record. So Chroma stores vectors keyed by `vector_id`, and every
`vector_id` resolves back to a row in `chunks`, which joins to `papers` for the
[n] citation shown to the user.

ChromaDB is imported lazily so that the rest of the primer-designer backend
still boots when it is not installed.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

# data/papers.db + data/chroma/ [SPEC_Phase1 §7]. Kept under backend/data/ to
# match where this repo already stores its other data files.
_DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH     = os.path.abspath(os.path.join(_DATA_DIR, "papers.db"))
CHROMA_PATH = os.path.abspath(os.path.join(_DATA_DIR, "chroma"))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

_chroma_client     = None
_chroma_collection = None
_chroma_lock       = threading.Lock()


def collection_name() -> str:
    """
    One collection per embedding model.

    Vectors from two different models are not comparable, and their dimensions usually do not
    even match (bge-small is 384-d, S-PubMedBert was 768-d). Reusing one collection across a
    model change would either raise a dimension error or — far worse — silently mix
    incomparable vectors and quietly wreck retrieval.

    Keying the collection by model makes the switch safe: the new model starts with an empty
    collection, which reindex_if_stale() then refills from the chunk text already in SQLite.
    Switching back reuses the old collection untouched.
    """
    import llm
    slug = "".join(c if c.isalnum() else "_" for c in llm.EMBED_MODEL.lower())
    return f"chunks__{slug}"[:60]        # Chroma caps collection-name length


# ── SQLite ──────────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")   # make the chunks->papers CASCADE real
    return conn


def init_schema() -> None:
    """Create papers/chunks tables if absent. Safe to call on every startup."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        ddl = f.read()
    conn = _connect()
    try:
        conn.executescript(ddl)
        conn.commit()
    finally:
        conn.close()


def paper_exists(pmid: str) -> bool:
    conn = _connect()
    try:
        row = conn.execute("SELECT 1 FROM papers WHERE pmid = ?", (pmid,)).fetchone()
        return row is not None
    finally:
        conn.close()


def insert_paper(paper: dict) -> int:
    """
    Insert one paper and return its row id. If the pmid is already present,
    returns the existing id WITHOUT re-inserting (ingest is idempotent — the
    same keyword search run twice must not duplicate papers or chunks).
    """
    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT id FROM papers WHERE pmid = ?", (paper["pmid"],)
        ).fetchone()
        if existing:
            return int(existing["id"])

        cur = conn.execute(
            """
            INSERT INTO papers
                (pmid, title, authors, journal, year, abstract, url,
                 is_open_access, full_text, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper["pmid"],
                paper.get("title", ""),
                json.dumps(paper.get("authors", []), ensure_ascii=False),
                paper.get("journal", ""),
                paper.get("year"),
                paper.get("abstract", ""),
                paper.get("url", ""),
                1 if paper.get("is_open_access") else 0,
                paper.get("full_text"),          # None unless open-access [§3.3]
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def insert_chunks(paper_id: int, chunks: list[dict]) -> None:
    """chunks: [{chunk_text, chunk_index, vector_id}, ...]"""
    if not chunks:
        return
    conn = _connect()
    try:
        conn.executemany(
            """
            INSERT OR IGNORE INTO chunks (paper_id, chunk_text, chunk_index, vector_id)
            VALUES (?, ?, ?, ?)
            """,
            [(paper_id, c["chunk_text"], c["chunk_index"], c["vector_id"]) for c in chunks],
        )
        conn.commit()
    finally:
        conn.close()


def get_chunks_by_vector_ids(vector_ids: list[str]) -> dict[str, dict]:
    """
    Resolve Chroma hits back to chunk text + the parent paper's citation metadata.
    Returns {vector_id: {chunk_text, pmid, title, authors, journal, year, url}}.
    """
    if not vector_ids:
        return {}
    conn = _connect()
    try:
        placeholders = ",".join("?" * len(vector_ids))
        rows = conn.execute(
            f"""
            SELECT c.vector_id, c.chunk_text,
                   p.pmid, p.title, p.authors, p.journal, p.year, p.url
            FROM chunks c
            JOIN papers p ON p.id = c.paper_id
            WHERE c.vector_id IN ({placeholders})
            """,
            vector_ids,
        ).fetchall()

        out = {}
        for r in rows:
            out[r["vector_id"]] = {
                "chunk_text": r["chunk_text"],
                "pmid":       r["pmid"],
                "title":      r["title"],
                "authors":    json.loads(r["authors"] or "[]"),
                "journal":    r["journal"],
                "year":       r["year"],
                "url":        r["url"],
            }
        return out
    finally:
        conn.close()


def list_papers(page: int = 1, per_page: int = 20) -> dict:
    """Paginated listing for GET /api/papers [SPEC_Phase1 §6]."""
    page     = max(1, int(page))
    per_page = max(1, min(100, int(per_page)))   # cap: never dump the whole table
    offset   = (page - 1) * per_page

    conn = _connect()
    try:
        total = conn.execute("SELECT COUNT(*) AS n FROM papers").fetchone()["n"]
        rows  = conn.execute(
            """
            SELECT p.id, p.pmid, p.title, p.authors, p.journal, p.year,
                   p.abstract, p.url, p.is_open_access, p.ingested_at,
                   (SELECT COUNT(*) FROM chunks c WHERE c.paper_id = p.id) AS n_chunks
            FROM papers p
            ORDER BY p.ingested_at DESC, p.id DESC
            LIMIT ? OFFSET ?
            """,
            (per_page, offset),
        ).fetchall()

        return {
            "papers": [
                {
                    "id":             r["id"],
                    "pmid":           r["pmid"],
                    "title":          r["title"],
                    "authors":        json.loads(r["authors"] or "[]"),
                    "journal":        r["journal"],
                    "year":           r["year"],
                    "abstract":       r["abstract"],
                    "url":            r["url"],
                    "is_open_access": bool(r["is_open_access"]),
                    "ingested_at":    r["ingested_at"],
                    "n_chunks":       r["n_chunks"],
                }
                for r in rows
            ],
            "total":    total,
            "page":     page,
            "per_page": per_page,
            "pages":    (total + per_page - 1) // per_page,
        }
    finally:
        conn.close()


def count_papers() -> int:
    conn = _connect()
    try:
        return int(conn.execute("SELECT COUNT(*) AS n FROM papers").fetchone()["n"])
    finally:
        conn.close()


def count_chunks() -> int:
    conn = _connect()
    try:
        return int(conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"])
    finally:
        conn.close()


# ── ChromaDB ────────────────────────────────────────────────────────────────

def get_collection():
    """
    Return the persistent Chroma collection, creating it on first use.

    embedding_function=None on purpose: we pass vectors in explicitly, produced
    by llm.embed(). Letting Chroma embed on its own would bypass the single
    abstraction layer required by SPEC_Phase1 §5.4 and silently use a different
    model than the query side.
    """
    global _chroma_client, _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection

    with _chroma_lock:
        if _chroma_collection is not None:
            return _chroma_collection
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError(
                "chromadb is not installed. Install it with:  pip install chromadb"
            ) from exc

        os.makedirs(CHROMA_PATH, exist_ok=True)
        _chroma_client     = chromadb.PersistentClient(path=CHROMA_PATH)
        _chroma_collection = _chroma_client.get_or_create_collection(
            name=collection_name(),
            embedding_function=None,
            metadata={"hnsw:space": "cosine"},   # vectors from llm.embed() are L2-normalised
        )
        return _chroma_collection


def all_chunks_for_reindex() -> list[dict]:
    """Every chunk with its text and vector_id — the raw material for re-embedding."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT c.vector_id, c.chunk_text, c.chunk_index, p.pmid, p.title, p.year
            FROM chunks c JOIN papers p ON p.id = c.paper_id
            ORDER BY c.id
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def reindex_if_stale(batch: int = 64) -> dict:
    """
    Re-embed every stored chunk when the vector store is out of step with SQLite.

    This is what makes changing the embedding model a safe, one-line operation: the chunk TEXT
    lives in SQLite, so a new model can be vectorised from local data — no second trip to
    PubMed, no re-ingest, no data loss.

    Triggers when the model's collection holds fewer vectors than SQLite holds chunks, which
    covers both cases that matter: a fresh model with an empty collection, and an ingest that
    half-failed.

    Returns {reindexed, chunks, collection}.
    """
    import llm

    chunks = all_chunks_for_reindex()
    coll   = get_collection()

    if not chunks or coll.count() >= len(chunks):
        return {"reindexed": 0, "chunks": len(chunks), "collection": collection_name()}

    for i in range(0, len(chunks), batch):
        window  = chunks[i:i + batch]
        texts   = [c["chunk_text"] for c in window]
        vectors = llm.embed(texts, kind="passage")
        coll.upsert(
            ids=[c["vector_id"] for c in window],
            embeddings=vectors,
            documents=texts,
            metadatas=[
                {
                    "pmid":        c["pmid"],
                    "title":       c["title"] or "",
                    "year":        c["year"] or 0,
                    "chunk_index": c["chunk_index"],
                }
                for c in window
            ],
        )

    return {"reindexed": len(chunks), "chunks": len(chunks),
            "collection": collection_name()}


def add_vectors(ids: list[str], vectors: list[list[float]],
                documents: list[str], metadatas: list[dict]) -> None:
    """Upsert chunk vectors into Chroma. `ids` are the `vector_id`s in SQLite."""
    if not ids:
        return
    get_collection().upsert(
        ids=ids, embeddings=vectors, documents=documents, metadatas=metadatas
    )


def query_vectors(query_vector: list[float], k: int = 5) -> list[dict]:
    """
    Nearest-neighbour search. Returns [{vector_id, document, metadata, distance}]
    ordered nearest-first. Empty list when the collection has no vectors yet.
    """
    coll = get_collection()
    if coll.count() == 0:
        return []

    res = coll.query(
        query_embeddings=[query_vector],
        n_results=min(k, coll.count()),
        include=["documents", "metadatas", "distances"],
    )
    return [
        {
            "vector_id": res["ids"][0][i],
            "document":  res["documents"][0][i],
            "metadata":  res["metadatas"][0][i],
            "distance":  res["distances"][0][i],
        }
        for i in range(len(res["ids"][0]))
    ]


def chroma_health() -> dict:
    """Never raises — /api/health must answer even when Chroma is missing."""
    try:
        vectors = get_collection().count()
        chunks  = count_chunks()
        # A vector count below the chunk count means part of the corpus is unsearchable —
        # usually because the embedding model changed. Say so, rather than quietly answering
        # from whatever fraction happens to be indexed.
        return {
            "alive":      True,
            "vectors":    vectors,
            "collection": collection_name(),
            "stale":      vectors < chunks,
            "error":      None,
        }
    except Exception as exc:
        return {"alive": False, "vectors": 0, "collection": None,
                "stale": False, "error": str(exc)}


def sqlite_health() -> dict:
    try:
        return {"alive": True, "papers": count_papers(),
                "chunks": count_chunks(), "error": None}
    except Exception as exc:
        return {"alive": False, "papers": 0, "chunks": 0, "error": str(exc)}
