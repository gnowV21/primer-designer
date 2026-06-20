import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), 'mirbase.db')

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mirna (
    name        TEXT PRIMARY KEY,
    accession   TEXT,
    sequence    TEXT NOT NULL,
    family      TEXT DEFAULT '',
    species     TEXT DEFAULT '',
    length      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_accession ON mirna (UPPER(accession));
CREATE INDEX IF NOT EXISTS idx_sequence  ON mirna (UPPER(sequence));
"""


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def exists() -> bool:
    return os.path.exists(DB_PATH)


def lookup(mirna_id: str) -> dict | None:
    if not exists():
        return None
    key = mirna_id.strip().upper()
    with _conn() as c:
        row = c.execute(
            """SELECT * FROM mirna
               WHERE UPPER(name)=? OR UPPER(accession)=? OR UPPER(sequence)=?
               ORDER BY CASE WHEN UPPER(species) LIKE 'HOMO SAPIENS%' THEN 0 ELSE 1 END
               LIMIT 1""",
            (key, key, key),
        ).fetchone()
    return dict(row) if row else None


def upsert(data: dict):
    """Cache a result fetched from an external source into local DB."""
    if not exists():
        return
    with _conn() as c:
        c.execute(
            """INSERT OR REPLACE INTO mirna (name, accession, sequence, family, species, length)
               VALUES (:id, :accession, :sequence, :family, :species, :length)""",
            data,
        )
        c.commit()


def init_schema():
    """Create DB file + schema if they do not already exist. Idempotent — safe to call at startup."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as c:
        c.executescript(_SCHEMA)
        c.commit()
