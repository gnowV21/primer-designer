# ================================================================
# tests/test_sqlite_kv_cache.py — SQLiteKVCache + BlastCache tests
# ================================================================

import os
import sys
import tempfile
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.sqlite_kv_cache import SQLiteKVCache


def _tmp_cache(ttl=None):
    tmp = tempfile.mktemp(suffix=".sqlite")
    return SQLiteKVCache(db_path=tmp, table_name="test_cache", default_ttl_days=ttl)


# ── Basic get/set ─────────────────────────────────────────────────

def test_get_missing_key_returns_none():
    c = _tmp_cache()
    assert c.get("missing") is None


def test_set_and_get_round_trips():
    c = _tmp_cache()
    c.set("k1", '{"x": 1}')
    result = c.get("k1")
    assert result is not None
    assert result["value"] == '{"x": 1}'


def test_set_with_metadata():
    c = _tmp_cache()
    c.set("k1", "val", metadata={"source": "test"})
    result = c.get("k1")
    assert result["metadata"]["source"] == "test"


def test_set_overwrites_existing():
    c = _tmp_cache()
    c.set("k1", "v1")
    c.set("k1", "v2")
    assert c.get("k1")["value"] == "v2"


def test_delete_removes_key():
    c = _tmp_cache()
    c.set("k1", "v1")
    deleted = c.delete("k1")
    assert deleted is True
    assert c.get("k1") is None


def test_delete_nonexistent_returns_false():
    c = _tmp_cache()
    assert c.delete("nope") is False


# ── TTL / expiry ──────────────────────────────────────────────────

def test_expired_entry_returns_none():
    c = _tmp_cache(ttl=None)
    # Set with ttl_days=0 (expires immediately — past timestamp)
    from datetime import datetime, timezone, timedelta
    from utils.sqlite_kv_cache import SQLiteKVCache
    import sqlite3
    c.set("expiring", "val")
    # Manually set expires_at to past
    with sqlite3.connect(c.db_path) as conn:
        conn.execute(
            "UPDATE test_cache SET expires_at='2000-01-01T00:00:00Z' WHERE key='expiring'"
        )
    assert c.get("expiring") is None


def test_no_ttl_entry_does_not_expire():
    c = _tmp_cache(ttl=None)
    c.set("permanent", "stays")
    assert c.get("permanent") is not None


def test_cleanup_expired_removes_stale():
    c = _tmp_cache(ttl=None)
    c.set("stale", "old")
    import sqlite3
    with sqlite3.connect(c.db_path) as conn:
        conn.execute(
            "UPDATE test_cache SET expires_at='2000-01-01T00:00:00Z' WHERE key='stale'"
        )
    removed = c.cleanup_expired()
    assert removed >= 1
    assert c.get("stale") is None


# ── BlastCache ────────────────────────────────────────────────────

def test_blast_cache_set_and_get():
    from algorithm.specificity_check.blast_cache import BlastCache
    tmp = tempfile.mktemp(suffix=".sqlite")
    bc = BlastCache(db_path=tmp)

    payload = {"summary": {"overall_risk": "SAFE"}, "forward_primer_hits": []}
    bc.set_result("ATCGATCG", "CCAGTGCA", payload, "2026-01-01")
    result = bc.get_result("ATCGATCG", "CCAGTGCA", "2026-01-01")
    assert result is not None
    assert result["summary"]["overall_risk"] == "SAFE"


def test_blast_cache_miss_different_db_version():
    from algorithm.specificity_check.blast_cache import BlastCache
    tmp = tempfile.mktemp(suffix=".sqlite")
    bc = BlastCache(db_path=tmp)

    bc.set_result("ATCGATCG", "", {"summary": {}}, "2026-01-01")
    result = bc.get_result("ATCGATCG", "", "2026-02-01")  # different version
    assert result is None


def test_blast_cache_key_is_deterministic():
    from algorithm.specificity_check.blast_cache import BlastCache
    k1 = BlastCache._compute_key("ATCG", "GCAT", "v1")
    k2 = BlastCache._compute_key("ATCG", "GCAT", "v1")
    assert k1 == k2


def test_blast_cache_key_differs_on_different_input():
    from algorithm.specificity_check.blast_cache import BlastCache
    k1 = BlastCache._compute_key("ATCG", "", "v1")
    k2 = BlastCache._compute_key("TTTT", "", "v1")
    assert k1 != k2
