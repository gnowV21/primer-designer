#!/usr/bin/env python3
"""
Download miRBase mature.fa and build the local SQLite database.

Usage:
  python scripts/build_db.py               # auto-download
  python scripts/build_db.py mature.fa.gz  # use a local file
"""
import gzip
import os
import sqlite3
import sys

import requests

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

DOWNLOAD_URLS = [
    "https://mirbase.org/download/mature.fa.gz",
    "https://mirbase.org/ftp/CURRENT/mature.fa.gz",
]

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
"""


def download() -> bytes:
    for url in DOWNLOAD_URLS:
        print(f"Trying {url} ...", flush=True)
        try:
            r = requests.get(url, timeout=60, stream=True)
            r.raise_for_status()
            data = r.content
            print(f"  Downloaded {len(data):,} bytes", flush=True)
            return data
        except Exception as e:
            print(f"  Failed: {e}", flush=True)
    raise RuntimeError(
        "All download sources failed.\n"
        "Download manually: https://mirbase.org/download/mature.fa.gz\n"
        "Then run: python scripts/build_db.py mature.fa.gz"
    )


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


def build(gz_data: bytes):
    text = gzip.decompress(gz_data).decode('utf-8')
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    rows = []
    for header, seq in parse_fasta(text):
        name, accession, species = parse_header(header)
        seq = seq.upper().replace('T', 'U')  # Force RNA notation
        rows.append((name, accession, seq, '', species, len(seq)))

    conn.executemany(
        'INSERT OR REPLACE INTO mirna (name, accession, sequence, family, species, length)'
        ' VALUES (?,?,?,?,?,?)',
        rows,
    )
    conn.commit()
    conn.close()
    print(f"Done — {len(rows):,} miRNAs written to {DB_PATH}", flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        path = sys.argv[1]
        print(f"Using local file: {path}")
        with open(path, 'rb') as f:
            gz = f.read()
    else:
        gz = download()
    build(gz)
