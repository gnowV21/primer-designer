-- schema.sql — structured store for the Phase 1 AI chatbot [SPEC_Phase1 §3.4].
--
-- Holds paper metadata + abstract (and full text ONLY for open-access papers,
-- per the copyright rule in SPEC_Phase1 §3.3). The vectors themselves live in
-- ChromaDB; `chunks.vector_id` is the join key back to them.

CREATE TABLE IF NOT EXISTS papers (
    id             INTEGER PRIMARY KEY,
    pmid           TEXT UNIQUE,
    title          TEXT,
    authors        TEXT,          -- JSON list of strings
    journal        TEXT,
    year           INTEGER,
    abstract       TEXT,
    url            TEXT,
    is_open_access INTEGER DEFAULT 0,
    full_text      TEXT,          -- open-access only [SPEC_Phase1 §3.3]
    ingested_at    TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY,
    paper_id    INTEGER REFERENCES papers(id) ON DELETE CASCADE,
    chunk_text  TEXT,
    chunk_index INTEGER,
    vector_id   TEXT UNIQUE       -- matches the id stored in ChromaDB
);

-- Retrieval path: Chroma returns vector_ids -> we look chunks up by vector_id,
-- then join to papers for the citation metadata. Both directions need an index.
CREATE INDEX IF NOT EXISTS idx_chunks_vector_id ON chunks(vector_id);
CREATE INDEX IF NOT EXISTS idx_chunks_paper_id  ON chunks(paper_id);
CREATE INDEX IF NOT EXISTS idx_papers_pmid      ON papers(pmid);
