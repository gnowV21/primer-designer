"""
Unit tests for routes/batch_design.py — Phase 8 PART A.

7 test cases per spec A.7:
  - sync NDJSON path (≤10 miRNAs)
  - async path (>10 miRNAs)
  - partial results during async
  - one invalid entry does not block others
  - params applied uniformly
  - max-size warning (>50)
  - deduplication
"""

import json
import sys
import os
import time
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app as flask_app_module

# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def client():
    flask_app_module.app.config["TESTING"] = True
    with flask_app_module.app.test_client() as c:
        yield c


def _fake_pipeline_ok(seq, params, mirna_name=""):
    return {
        "top3": [{"sequence": "ACGT" * 4, "tm": 59.5, "total_score": 0.82}],
        "warnings": [],
    }


def _fake_resolve(mirna_id):
    if "bad" in mirna_id.lower():
        return None
    return "AUGCAUGCAUGCAUGCAUGC"   # 20 nt valid RNA


def _mirna_list(n, prefix="hsa-miR-"):
    return [f"{prefix}{21 + i}-5p" for i in range(n)]


# ── Test 1: Sync path (≤10) returns NDJSON ─────────────────────

@patch("routes.batch_design._resolve_sequence", side_effect=_fake_resolve)
@patch("routes.batch_design._pipeline_run", side_effect=_fake_pipeline_ok)
def test_sync_batch_3_mirnas_streams_ndjson(mock_run, mock_resolve, client):
    payload = {"mirnas": _mirna_list(3), "params": {}}
    resp = client.post("/api/batch-design", json=payload)

    assert resp.status_code == 200
    assert "x-ndjson" in resp.content_type

    lines = [l for l in resp.data.decode().splitlines() if l.strip()]
    assert len(lines) == 5  # meta + 3 result + done

    meta = json.loads(lines[0])
    assert meta["type"] == "meta"
    assert meta["total"] == 3

    done = json.loads(lines[-1])
    assert done["type"] == "done"
    assert done["succeeded"] == 3
    assert done["failed"] == 0


# ── Test 2: Async path (>10) returns 202 + job_id ──────────────

@patch("routes.batch_design._resolve_sequence", side_effect=_fake_resolve)
@patch("routes.batch_design._pipeline_run", side_effect=_fake_pipeline_ok)
def test_async_batch_15_mirnas_returns_job_id(mock_run, mock_resolve, client):
    payload = {"mirnas": _mirna_list(15), "params": {}}
    resp = client.post("/api/batch-design", json=payload)

    assert resp.status_code == 202
    body = resp.get_json()
    assert "job_id" in body
    assert body["mode"] == "async"
    assert body["total"] == 15
    assert body["status"] == "queued"


# ── Test 3: Partial results during async job ────────────────────

@patch("routes.batch_design._resolve_sequence", side_effect=_fake_resolve)
@patch("routes.batch_design._pipeline_run", side_effect=_fake_pipeline_ok)
def test_batch_status_partial_results(mock_run, mock_resolve, client):
    payload = {"mirnas": _mirna_list(11), "params": {}}
    resp = client.post("/api/batch-design", json=payload)
    job_id = resp.get_json()["job_id"]

    # Give thread a moment, then poll — may be queued, running, or done
    time.sleep(0.1)
    status_resp = client.get(f"/api/batch-status/{job_id}")
    assert status_resp.status_code == 200

    body = status_resp.get_json()
    assert body["status"] in ("queued", "running", "done")
    assert "completed" in body
    assert "results" in body


# ── Test 4: One invalid entry does not block others ─────────────

def _resolve_with_one_bad(mirna_id):
    if mirna_id == "hsa-miR-bad-5p":
        return None
    return "AUGCAUGCAUGCAUGCAUGC"


@patch("routes.batch_design._resolve_sequence", side_effect=_resolve_with_one_bad)
@patch("routes.batch_design._pipeline_run", side_effect=_fake_pipeline_ok)
def test_batch_one_invalid_does_not_block_others(mock_run, mock_resolve, client):
    mirnas = ["hsa-miR-21-5p", "hsa-miR-bad-5p", "hsa-miR-22-5p"]
    payload = {"mirnas": mirnas, "params": {}}
    resp = client.post("/api/batch-design", json=payload)

    assert resp.status_code == 200
    lines = [l for l in resp.data.decode().splitlines() if l.strip()]

    results = [json.loads(l) for l in lines if json.loads(l).get("type") == "result"]
    assert len(results) == 3

    statuses = {r["mirna"]: r["status"] for r in results}
    assert statuses["hsa-miR-21-5p"] == "ok"
    assert statuses["hsa-miR-bad-5p"] == "error"
    assert statuses["hsa-miR-22-5p"] == "ok"


# ── Test 5: Params applied uniformly ───────────────────────────

seen_params = []

def _capture_params(seq, params, mirna_name=""):
    seen_params.append(dict(params))
    return _fake_pipeline_ok(seq, params)


@patch("routes.batch_design._resolve_sequence", side_effect=_fake_resolve)
@patch("routes.batch_design._pipeline_run", side_effect=_capture_params)
def test_batch_params_applied_uniformly(mock_run, mock_resolve, client):
    seen_params.clear()
    custom = {"thermodynamic": {"saltConcentration": 100.0}}
    payload = {"mirnas": _mirna_list(3), **custom}
    resp = client.post("/api/batch-design", json=payload)
    _ = resp.data  # consume the NDJSON stream so the generator actually runs

    assert len(seen_params) == 3
    salts = [p.get("saltConcentration") for p in seen_params]
    assert all(s == 100.0 for s in salts), "All miRNAs should receive same params"


# ── Test 6: Max size warning when >50 ──────────────────────────

@patch("routes.batch_design._resolve_sequence", side_effect=_fake_resolve)
@patch("routes.batch_design._pipeline_run", side_effect=_fake_pipeline_ok)
def test_batch_max_size_warning(mock_run, mock_resolve, client):
    payload = {"mirnas": _mirna_list(55), "params": {}}
    resp = client.post("/api/batch-design", json=payload)

    # Async path (55 > BATCH_ASYNC_THRESHOLD=10)
    assert resp.status_code == 202
    body = resp.get_json()
    # total should be capped at BATCH_MAX_SIZE=50
    assert body["total"] == 50
    assert any("BATCH_MAX_SIZE" in w or "50" in w for w in body.get("warnings", []))


# ── Test 7: Deduplication ───────────────────────────────────────

@patch("routes.batch_design._resolve_sequence", side_effect=_fake_resolve)
@patch("routes.batch_design._pipeline_run", side_effect=_fake_pipeline_ok)
def test_batch_dedupe(mock_run, mock_resolve, client):
    # 3 entries but 2 duplicates → should only process 2 unique
    mirnas = ["hsa-miR-21-5p", "hsa-miR-21-5p", "hsa-miR-22-5p"]
    payload = {"mirnas": mirnas, "params": {}}
    resp = client.post("/api/batch-design", json=payload)

    assert resp.status_code == 200
    lines = [l for l in resp.data.decode().splitlines() if l.strip()]
    meta = json.loads(lines[0])
    assert meta["total"] == 2   # duplicate removed
    assert mock_run.call_count == 2
