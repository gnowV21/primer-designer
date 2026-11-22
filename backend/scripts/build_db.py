#!/usr/bin/env python3
"""
Build the local miRBase lookup database db/mirbase.db (served by /api/mirbase).

Input is the PINNED mature.fa of miRBase 22.1 (backend/data/mirbase_22.1/
mature.fa.gz, sha256 in SHA256 — scripts/mirbase_pin.py), the file the BLAST DB
and the overhang / family indexes come from. The sha256 is checked before anything
is written; a different file exits with code 2. The database is built in a new
file and moved into place, so no row of an older database (for example an entry
cached from an online lookup before 3.8.2) survives a rebuild.

Usage:
  python scripts/build_db.py                       # pinned file
  python scripts/build_db.py mature.fa.gz          # another copy, same sha256
  python scripts/build_db.py --download            # miRBase archive copy of 22.1
  python scripts/build_db.py --out /tmp/mirbase.db
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from scripts import mirbase_pin as pin  # noqa: E402

# Resolve path relative to this script: backend/db/mirbase.db
DB_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'db', 'mirbase.db'))

SPECIES_MAP = {
    "hsa": "Homo sapiens",
    "mmu": "Mus musculus",
    "rno": "Rattus norvegicus",
    "cel": "Caenorhabditis elegans",
    "dme": "Drosophila melanogaster",
    "gga": "Gallus gallus",
    "bta": "Bos taurus",
}

# The same tables and indexes as db/local_db.py, so the app never has to add an
# index at startup (the deployed image keeps the database read-only), plus a
# `source` table that records which mature.fa the rows came from.
SCHEMA = """
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
CREATE TABLE IF NOT EXISTS source (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def parse_fasta(text: str):
    """Yield (header, sequence) pairs from a FASTA string."""
    header, parts = None, []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('>'):
            if header and parts:
                yield header, ''.join(parts)
            header, parts = line[1:], []
        elif line:
            parts.append(line)
    if header and parts:
        yield header, ''.join(parts)


def parse_header(header: str):
    """
    'hsa-miR-21-5p MIMAT0000076 Homo sapiens miR-21-5p'
    → (name, accession, species)
    """
    parts = header.split()
    name = parts[0] if parts else ''
    accession = parts[1] if len(parts) > 1 else ''
    if len(parts) >= 4:
        species = f"{parts[2]} {parts[3]}"
    else:
        prefix = name[:3].lower() if '-' in name else ''
        species = SPECIES_MAP.get(prefix, '')
    return name, accession, species


def build(fasta: bytes, out_path: str = DB_PATH, sha256: str = "", release: str = "") -> int:
    """Write the database to `out_path` (new file, then replace). Returns the row count."""
    text = fasta.decode('utf-8')
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    tmp = out_path + ".building"
    if os.path.exists(tmp):
        os.remove(tmp)

    rows = []
    for header, seq in parse_fasta(text):
        name, accession, species = parse_header(header)
        seq = seq.upper().replace('T', 'U')  # Force RNA notation
        rows.append((name, accession, seq, '', species, len(seq)))

    conn = sqlite3.connect(tmp)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            'INSERT OR REPLACE INTO mirna (name, accession, sequence, family, species, length)'
            ' VALUES (?,?,?,?,?,?)',
            rows,
        )
        n = conn.execute('SELECT COUNT(*) FROM mirna').fetchone()[0]
        conn.executemany('INSERT OR REPLACE INTO source (key, value) VALUES (?, ?)', [
            ("mirbase_release", release),
            ("mature_fa_sha256", sha256),
            ("entries", str(n)),
            ("build_date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        ])
        conn.commit()
    finally:
        conn.close()
    os.replace(tmp, out_path)
    print(f"Done — {n:,} miRNAs written to {out_path}", flush=True)
    return n


def read_source(db_path: str = DB_PATH) -> dict:
    """The `source` table of a database built by this script ({} if absent)."""
    if not os.path.exists(db_path):
        return {}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            meta = dict(conn.execute('SELECT key, value FROM source').fetchall())
            meta["rows"] = conn.execute('SELECT COUNT(*) FROM mirna').fetchone()[0]
            return meta
        finally:
            conn.close()
    except sqlite3.Error:
        return {}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build db/mirbase.db from the pinned mature.fa")
    parser.add_argument("path", nargs="?", default=None,
                        help=f"local mature.fa or mature.fa.gz (default: {pin.PINNED_FASTA})")
    parser.add_argument("--fasta", default=None, help="same as the positional path")
    parser.add_argument("--download", action="store_true",
                        help="fetch mature.fa from --url instead of reading a local file")
    parser.add_argument("--url", default=pin.ARCHIVE_URL)
    parser.add_argument("--sha256", default=None,
                        help="expected sha256 of the uncompressed file (default: the pinned one)")
    parser.add_argument("--out", default=DB_PATH)
    args = parser.parse_args(argv)

    path = args.fasta or args.path
    try:
        data, sha = pin.load_mature_fa(path, download_url=args.url if args.download else None,
                                       expected_sha256=args.sha256)
    except pin.PinMismatch as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"ERROR: cannot read mature.fa: {e}", file=sys.stderr)
        return 2
    release = pin.PINNED_RELEASE if sha == pin.pinned_sha256() else "unknown"
    n = build(data, args.out, sha256=sha, release=release)
    expected = pin.count_entries(data)
    if n != expected:
        print(f"ERROR: {n:,} rows written, mature.fa has {expected:,} entries "
              "(duplicate names?).", file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
