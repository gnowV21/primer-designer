"""
bootstrap_blast_db.py — Idempotent BLAST DB bootstrap hook. (Phase 7 PART A)

Run before app.py at container/server start:
  python -m scripts.bootstrap_blast_db && python app.py

Logic:
  1. All 3 DB files (.nhr / .nin / .nsq) + metadata.json present → SKIP.
  2. Any missing → call build_blast_db.main() to build from miRBase mature.fa.
  3. Build fails (network down / makeblastdb not installed) → log ERROR, do NOT
     crash.  /api/design remains fully functional; /api/blast-status returns
     available=false so the frontend disables the BLAST button gracefully.
"""

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
_DB_DIR = os.path.join(_BACKEND_DIR, "data", "blast_db")
_REQUIRED = ("mirbase_multi.nhr", "mirbase_multi.nin", "mirbase_multi.nsq")
_METADATA = os.path.join(_DB_DIR, "metadata.json")


def db_is_present() -> bool:
    return (
        os.path.exists(_METADATA)
        and all(os.path.exists(os.path.join(_DB_DIR, f)) for f in _REQUIRED)
    )


def run() -> bool:
    """Bootstrap BLAST DB. Returns True if DB is available after this call."""
    if db_is_present():
        log.info("BLAST DB present, skipping build.")
        return True

    log.info("BLAST DB not found — attempting to build...")

    if _BACKEND_DIR not in sys.path:
        sys.path.insert(0, _BACKEND_DIR)

    try:
        from scripts.build_blast_db import main as _build

        _build()
        if db_is_present():
            log.info("BLAST DB built successfully.")
            return True
        log.error(
            "BLAST DB build ran but expected files are missing — BLAST unavailable."
        )
        return False
    except SystemExit as exc:
        log.error(
            "BLAST DB build exited (code %s) — makeblastdb may not be installed. "
            "App starts without BLAST support.",
            exc.code,
        )
        return False
    except Exception as exc:
        log.error(
            "BLAST DB build failed: %s — app will start without BLAST support.", exc
        )
        return False


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
