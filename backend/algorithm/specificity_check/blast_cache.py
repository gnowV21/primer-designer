# ================================================================
# blast_cache.py — SQLite cache for /api/blast-check results
#
# Extends SQLiteKVCache (utils/sqlite_kv_cache.py).
# TTL: 30 days (BLAST_CACHE_TTL_DAYS) — databases update infrequently.
# Key: SHA-256(fwd | rev | db_version)[:32]
# ================================================================

import hashlib
import json
import os
from typing import Optional

from utils.sqlite_kv_cache import SQLiteKVCache
from algorithm.constants import BLAST_CACHE_TTL_DAYS

_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "blast_cache.sqlite"
)


class BlastCache(SQLiteKVCache):
    def __init__(self, db_path: str = _DB_PATH):
        super().__init__(
            db_path=db_path,
            table_name="blast_cache",
            default_ttl_days=BLAST_CACHE_TTL_DAYS,
        )

    def get_result(self, fwd: str, rev: str, db_version: str) -> Optional[dict]:
        """Return cached BLAST result dict or None."""
        key = self._compute_key(fwd, rev, db_version)
        entry = self.get(key)
        if entry:
            return json.loads(entry["value"])
        return None

    def set_result(
        self,
        fwd: str,
        rev: str,
        result: dict,
        db_version: str,
    ) -> None:
        """Cache a BLAST result dict with the default TTL."""
        key = self._compute_key(fwd, rev, db_version)
        self.set(
            key=key,
            value=json.dumps(result),
            metadata={"forward": fwd, "reverse": rev, "db_version": db_version},
        )

    @staticmethod
    def _compute_key(fwd: str, rev: str, db_version: str) -> str:
        raw = f"{fwd.upper()}|{rev.upper()}|{db_version}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
