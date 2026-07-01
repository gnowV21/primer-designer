# ================================================================
# utils/sqlite_kv_cache.py — Generic SQLite key-value cache with TTL
#
# Base class reused by:
#   - BlastCache (Phase 3) — blast_cache.py
#   - (Phase 4+) any future cache needing SQLite + TTL
#
# Backward-compatible with Week 1: local_db.py (miRBase lookup) is a
# separate module-level API and does NOT subclass this — it has its own
# domain-specific schema. This class is for generic KV caching only.
# ================================================================

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional


class SQLiteKVCache:
    """
    Generic SQLite key-value cache with optional TTL.

    Schema:
        key         TEXT PRIMARY KEY
        value       TEXT NOT NULL       — JSON-serialised value
        metadata    TEXT                — JSON blob for extra context
        created_at  TIMESTAMP
        expires_at  TIMESTAMP           — NULL = no expiry
    """

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS {table} (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        metadata   TEXT,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        expires_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_{table}_expires ON {table}(expires_at);
    """

    def __init__(
        self,
        db_path: str,
        table_name: str = "cache",
        default_ttl_days: Optional[int] = None,
    ):
        self.db_path = db_path
        self.table = table_name
        self.default_ttl = default_ttl_days
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_schema()

    # ── Public API ────────────────────────────────────────────────

    def get(self, key: str) -> Optional[dict]:
        """
        Return {"value": str, "metadata": dict|None, "created_at": str}
        or None if not found or expired.
        """
        now = self._utcnow_iso()
        with self._conn() as c:
            row = c.execute(
                f"SELECT value, metadata, created_at, expires_at "
                f"FROM {self.table} WHERE key=?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        # Check expiry
        if row["expires_at"] and row["expires_at"] < now:
            self.delete(key)
            return None
        return {
            "value":      row["value"],
            "metadata":   json.loads(row["metadata"]) if row["metadata"] else None,
            "created_at": row["created_at"],
        }

    def set(
        self,
        key: str,
        value: str,
        metadata: Optional[dict] = None,
        ttl_days: Optional[int] = None,
    ) -> None:
        """Store key → value. ttl_days overrides default_ttl if provided."""
        effective_ttl = ttl_days if ttl_days is not None else self.default_ttl
        expires_at = None
        if effective_ttl is not None:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(days=effective_ttl)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        meta_json = json.dumps(metadata) if metadata else None
        with self._conn() as c:
            c.execute(
                f"INSERT OR REPLACE INTO {self.table} "
                f"(key, value, metadata, created_at, expires_at) "
                f"VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'), ?)",
                (key, value, meta_json, expires_at),
            )

    def delete(self, key: str) -> bool:
        with self._conn() as c:
            cur = c.execute(f"DELETE FROM {self.table} WHERE key=?", (key,))
        return cur.rowcount > 0

    def cleanup_expired(self) -> int:
        """Delete all expired entries. Returns count deleted."""
        now = self._utcnow_iso()
        with self._conn() as c:
            cur = c.execute(
                f"DELETE FROM {self.table} WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            )
        return cur.rowcount

    # ── Internal helpers ──────────────────────────────────────────

    def _init_schema(self):
        schema = self._SCHEMA.format(table=self.table)
        with self._conn() as c:
            c.executescript(schema)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
