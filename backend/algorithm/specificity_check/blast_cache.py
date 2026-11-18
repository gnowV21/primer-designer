# ================================================================
# blast_cache.py — SQLite cache for /api/blast-check results
#
# Extends SQLiteKVCache (utils/sqlite_kv_cache.py).
# TTL: 30 days (BLAST_CACHE_TTL_DAYS) — databases update infrequently.
# Key: SHA-256(fwd | rev | db_version | mirna_id [| context])[:32]
# mirna_id is part of the key because it changes the RESULT: the on-target
# miRNA (and its precursor/same-family variants) is excluded per mirna_id, so
# the same forward primer under two different mirna_id values must not collide.
# context carries everything else that changes the result — classifier version,
# target sequence and salt conditions of the duplex-Tm gate.
# ================================================================

import hashlib
import json
import os
import sqlite3
import time
from typing import Optional

from utils.sqlite_kv_cache import SQLiteKVCache
from algorithm.constants import BLAST_CACHE_TTL_DAYS

_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "blast_cache.sqlite"
)


class BlastCache(SQLiteKVCache):
    # Many processes write this file at once in batch runs (crossreactivity/design_all.py,
    # one pipeline per worker): WAL lets readers and one writer proceed together, and a
    # 60-s busy timeout makes a writer wait for the lock instead of failing at once.
    _BUSY_TIMEOUT_S = 60.0

    def __init__(self, db_path: str = _DB_PATH):
        super().__init__(
            db_path=db_path,
            table_name="blast_cache",
            default_ttl_days=BLAST_CACHE_TTL_DAYS,
        )

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=self._BUSY_TIMEOUT_S)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def get_result(self, fwd: str, rev: str, db_version: str, mirna_id: str = "",
                   context: str = "") -> Optional[dict]:
        """Return cached BLAST result dict or None."""
        key = self._compute_key(fwd, rev, db_version, mirna_id, context)
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
        mirna_id: str = "",
        context: str = "",
    ) -> None:
        """Cache a BLAST result dict with the default TTL."""
        key = self._compute_key(fwd, rev, db_version, mirna_id, context)
        self.set(
            key=key,
            value=json.dumps(result),
            metadata={"forward": fwd, "reverse": rev, "db_version": db_version,
                      "mirna_id": mirna_id, "context": context},
        )

    def get_results(self, fwds: list[str], rev: str, db_version: str, mirna_id: str = "",
                    context: str = "") -> dict[str, dict]:
        """{fwd: cached result} for the forward primers found and not expired (one
        connection; the tiered design looks up a whole candidate pool at once)."""
        keys = {self._compute_key(f, rev, db_version, mirna_id, context): f for f in fwds}
        if not keys:
            return {}
        now = self._utcnow_iso()
        out = {}
        with self._conn() as c:
            for i in range(0, len(keys), 500):
                chunk = list(keys)[i:i + 500]
                rows = c.execute(
                    f"SELECT key, value, expires_at FROM {self.table} WHERE key IN "
                    f"({','.join('?' * len(chunk))})", chunk).fetchall()
                for row in rows:
                    if not (row["expires_at"] and row["expires_at"] < now):
                        out[keys[row["key"]]] = json.loads(row["value"])
        return out

    def set_results(self, results: dict[str, dict], rev: str, db_version: str,
                    mirna_id: str = "", context: str = "") -> None:
        """Cache {fwd: result} in one transaction, default TTL."""
        if not results:
            return
        expires_at = None
        if self.default_ttl is not None:
            from datetime import datetime, timedelta, timezone
            expires_at = (datetime.now(timezone.utc) + timedelta(days=self.default_ttl)
                          ).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = [(self._compute_key(f, rev, db_version, mirna_id, context), json.dumps(r),
                 json.dumps({"forward": f, "reverse": rev, "db_version": db_version,
                             "mirna_id": mirna_id, "context": context}), expires_at)
                for f, r in results.items()]
        # Retried: a lock held past the busy timeout raises OperationalError.
        for attempt in range(3):
            try:
                with self._conn() as c:
                    c.executemany(
                        f"INSERT OR REPLACE INTO {self.table} "
                        f"(key, value, metadata, created_at, expires_at) "
                        f"VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'), ?)", rows)
                return
            except sqlite3.OperationalError:
                if attempt == 2:
                    raise
                time.sleep(1.0 + attempt)

    @staticmethod
    def _compute_key(fwd: str, rev: str, db_version: str, mirna_id: str = "",
                     context: str = "") -> str:
        # mirna_id is normalised (lower) because the on-target exclusion is
        # case-insensitive; it is included so two different targets sharing a
        # forward primer get distinct cache entries.
        raw = f"{fwd.upper()}|{rev.upper()}|{db_version}|{mirna_id.lower()}"
        if context:
            raw += f"|{context}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
