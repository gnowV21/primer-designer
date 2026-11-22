"""
bootstrap_blast_db.py — Idempotent bootstrap of the BLAST DB and db/mirbase.db.

Both are built from the PINNED mature.fa of miRBase 22.1 (scripts/mirbase_pin.py,
backend/data/mirbase_22.1/mature.fa.gz), never from miRBase CURRENT. Run it once
before the server — at image build time in Dockerfile.vercel, so a container
starts without downloading or building anything:

  python -m scripts.bootstrap_blast_db

Logic:
  1. The pinned sha256 must equal the overhang index's mature_fa_sha256; otherwise
     the repository itself is inconsistent → ERROR, nothing is built, exit 1.
  2. BLAST DB: kept when its volumes + metadata.json are present and metadata
     records the pinned sha256; else rebuilt (build_blast_db.py).
  3. db/mirbase.db: kept when its `source` table records the pinned sha256 and it
     holds the pinned number of rows; else rebuilt (build_db.py).
  4. After the build, metadata.json's mature_fa_sha256 must equal the overhang
     index's → otherwise ERROR "BLAST unavailable" and exit 1 (the server reports
     BLAST unavailable for such a DB too: blast_offtarget.blast_db_release_problem).

A failure never raises: it is logged and run() returns False (exit code 1).
/api/design stays usable without BLAST (blast_unavailable banner).
"""

import json
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="[bootstrap_blast_db] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_SCRIPTS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from scripts import mirbase_pin as pin  # noqa: E402

_DB_DIR = os.path.join(_BACKEND_DIR, "data", "blast_db")
_REQUIRED = ("mirbase_multi.nhr", "mirbase_multi.nin", "mirbase_multi.nsq")
_METADATA = os.path.join(_DB_DIR, "metadata.json")
_LOOKUP_DB = os.path.join(_BACKEND_DIR, "db", "mirbase.db")


def db_is_present() -> bool:
    """BLAST volumes + metadata.json exist (says nothing about the release)."""
    return (
        os.path.exists(_METADATA)
        and all(os.path.exists(os.path.join(_DB_DIR, f)) for f in _REQUIRED)
    )


def metadata_sha256() -> str | None:
    try:
        with open(_METADATA, encoding="utf-8") as f:
            return json.load(f).get("mature_fa_sha256")
    except (OSError, ValueError):
        return None


def blast_db_ok(expected: str) -> bool:
    return db_is_present() and metadata_sha256() == expected


def lookup_db_ok(expected: str) -> bool:
    from scripts.build_db import read_source
    src = read_source(_LOOKUP_DB)
    return src.get("mature_fa_sha256") == expected and src.get("rows") == pin.PINNED_ENTRIES


def _build_blast() -> None:
    from scripts.build_blast_db import main as _build
    _build(["--out-dir", _DB_DIR])


def _build_lookup() -> None:
    from scripts.build_db import main as _build
    code = _build(["--out", _LOOKUP_DB])
    if code:
        raise RuntimeError(f"build_db exited with code {code}")


def run() -> bool:
    """Bootstrap both databases. True when both are present and on the pinned release."""
    try:
        pinned = pin.pinned_sha256()
    except (OSError, pin.PinMismatch) as exc:
        log.error("Pinned mature.fa sha256 unreadable (%s) — BLAST unavailable.", exc)
        return False
    index_sha = pin.index_sha256()
    if index_sha != pinned:
        log.error(
            "Pinned mature.fa (sha256 %s) is not the file the overhang index was built "
            "from (%s) — refusing to build; BLAST unavailable.", pinned, index_sha)
        return False

    ok = True
    # ── BLAST DB ───────────────────────────────────────────────
    if blast_db_ok(pinned):
        log.info("BLAST DB present (miRBase %s, sha256 %s…), skipping build.",
                 pin.PINNED_RELEASE, pinned[:12])
    else:
        log.info("BLAST DB missing or not built from the pinned file — building ...")
        try:
            _build_blast()
        except SystemExit as exc:
            log.error("BLAST DB build exited (code %s) — makeblastdb missing or the "
                      "mature.fa sha256 is wrong. BLAST unavailable.", exc.code)
        except Exception as exc:  # noqa: BLE001
            log.error("BLAST DB build failed: %s — BLAST unavailable.", exc)
    if not db_is_present():
        log.error("BLAST DB files are missing — BLAST unavailable.")
        ok = False
    elif metadata_sha256() != index_sha:
        log.error(
            "BLAST DB metadata.json records mature.fa sha256 %s, the overhang index %s: "
            "different miRBase files — BLAST unavailable.", metadata_sha256(), index_sha)
        ok = False
    else:
        log.info("BLAST DB OK.")

    # ── db/mirbase.db (local lookup for /api/mirbase) ──────────
    if lookup_db_ok(pinned):
        log.info("db/mirbase.db present (%s rows, pinned sha256), skipping build.",
                 f"{pin.PINNED_ENTRIES:,}")
    else:
        log.info("db/mirbase.db missing or not built from the pinned file — building ...")
        try:
            _build_lookup()
        except Exception as exc:  # noqa: BLE001
            log.error("db/mirbase.db build failed: %s", exc)
        if lookup_db_ok(pinned):
            log.info("db/mirbase.db OK.")
        else:
            log.error("db/mirbase.db is not on the pinned release — /api/mirbase may "
                      "fall back to online lookups.")
            ok = False
    return ok


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
