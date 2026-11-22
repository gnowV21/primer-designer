"""
mirbase_pin.py — the pinned miRBase mature.fa behind algorithm 4.0.0.

The BLAST DB (build_blast_db.py), the local lookup DB db/mirbase.db (build_db.py)
and the overhang / family indexes must all come from the same file: mature.fa of
miRBase Release 22.1, sha256 3c521fc9… (48,885 mature). It is committed as
backend/data/mirbase_22.1/mature.fa.gz with its sha256 in SHA256 (of the
uncompressed file). miRBase CURRENT has moved on (23.1, 61,007 mature), so a build
from CURRENT would silently disagree with the indexes — every build goes through
`load_mature_fa`, which refuses a file whose sha256 differs.

No engine imports here: the build scripts run before the app exists.
"""

import gzip
import hashlib
import os
import urllib.request

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(_SCRIPTS_DIR)

PINNED_RELEASE = "22.1"
PINNED_DIR = os.path.join(BACKEND_DIR, "data", "mirbase_22.1")
PINNED_FASTA = os.path.join(PINNED_DIR, "mature.fa.gz")
PINNED_SHA256_FILE = os.path.join(PINNED_DIR, "SHA256")
PINNED_ENTRIES = 48885
# miRBase archive copy of the pinned file (used only with --download).
ARCHIVE_URL = "https://www.mirbase.org/download_version_files/22/mature.fa"

OVERHANG_INDEX = os.path.join(BACKEND_DIR, "data", "mirbase_overhang_index.json")


class PinMismatch(RuntimeError):
    """The mature.fa given to a build is not the pinned file."""


def pinned_sha256() -> str:
    """sha256 of the uncompressed pinned mature.fa, read from SHA256."""
    with open(PINNED_SHA256_FILE, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if parts and len(parts[0]) == 64:
                return parts[0].lower()
    raise PinMismatch(f"no sha256 in {PINNED_SHA256_FILE}")


def index_sha256() -> str | None:
    """mature_fa_sha256 recorded in the overhang index (_metadata), or None."""
    import json
    try:
        with open(OVERHANG_INDEX, encoding="utf-8") as f:
            return (json.load(f).get("_metadata") or {}).get("mature_fa_sha256")
    except (OSError, ValueError):
        return None


def read_fasta_bytes(path: str) -> bytes:
    """Uncompressed bytes of a mature.fa or mature.fa.gz (detected by magic bytes)."""
    with open(path, "rb") as f:
        raw = f.read()
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str = ARCHIVE_URL, timeout: int = 300) -> bytes:
    """Fetch a mature.fa (or .gz) — only when a build is run with --download."""
    print(f"Downloading {url} ...", flush=True)
    with urllib.request.urlopen(url, timeout=timeout) as r:
        data = r.read()
    print(f"  {len(data):,} bytes", flush=True)
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def load_mature_fa(path: str | None = None, *, download_url: str | None = None,
                   expected_sha256: str | None = None) -> tuple[bytes, str]:
    """(uncompressed mature.fa bytes, sha256) after checking the sha256.

    path            local mature.fa / mature.fa.gz (default: the pinned file)
    download_url    fetch this URL instead of reading a file (the --download flag)
    expected_sha256 default: the pinned sha256 (SHA256 file)

    Raises PinMismatch — before anything is built — when the sha256 differs."""
    expected = (expected_sha256 or pinned_sha256()).lower()
    if download_url:
        data, where = download(download_url), download_url
    else:
        where = path or PINNED_FASTA
        data = read_fasta_bytes(where)
    got = sha256_hex(data)
    if got != expected:
        raise PinMismatch(
            f"mature.fa sha256 mismatch for {where}:\n"
            f"  expected {expected} ("
            + ("--sha256" if expected_sha256 else f"miRBase {PINNED_RELEASE}, {PINNED_SHA256_FILE}")
            + ")\n"
            f"  got      {got}\n"
            "Refusing to build: the BLAST DB, db/mirbase.db and the overhang / family "
            "indexes must come from the same mature.fa. Use the pinned file "
            f"({PINNED_FASTA}).")
    return data, got


def count_entries(data: bytes) -> int:
    return sum(1 for line in data.splitlines() if line.startswith(b">"))
