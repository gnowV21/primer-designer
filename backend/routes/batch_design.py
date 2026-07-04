"""
routes/batch_design.py — POST /api/batch-design  GET /api/batch-status/<job_id>

Hybrid sync/async batch design (Phase 8 PART A):
  ≤ BATCH_ASYNC_THRESHOLD  → synchronous NDJSON streaming
  > BATCH_ASYNC_THRESHOLD  → async job + polling

Reuses algorithm.design_pipeline.run() — no duplicate design logic.
"""

import json
import re
import threading
import time
import uuid
from dataclasses import dataclass, field

from flask import Blueprint, Response, jsonify, request

from algorithm.design_pipeline import run as _pipeline_run
from algorithm.sequence_utils import validate_rna_sequence
from db import local_db
from db.circuit_breaker import CircuitBreaker
from algorithm.constants import (
    BATCH_ASYNC_THRESHOLD,
    BATCH_MAX_SIZE,
    BATCH_JOB_TTL_SEC,
)

batch_design_bp = Blueprint("batch_design", __name__)

# ── miRNA name validation regex ────────────────────────────────────────────────
_RE_MIRNA = re.compile(r'^[a-z]{3}-(miR|let|lin|bantam)-', re.IGNORECASE)

# ── In-memory job store (single-instance; scale → Redis) ──────────────────────
@dataclass
class BatchJob:
    job_id: str
    total: int
    status: str = "queued"        # queued | running | done | error
    completed: int = 0
    succeeded: int = 0
    failed: int = 0
    results: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

_JOB_STORE: dict[str, BatchJob] = {}
_JOB_STORE_LOCK = threading.Lock()


def _sweep_expired() -> None:
    """Remove jobs older than BATCH_JOB_TTL_SEC (lazy cleanup)."""
    now = time.time()
    with _JOB_STORE_LOCK:
        expired = [jid for jid, job in _JOB_STORE.items()
                   if now - job.created_at > BATCH_JOB_TTL_SEC]
        for jid in expired:
            del _JOB_STORE[jid]


# ── miRNA sequence resolution ──────────────────────────────────────────────────

_mirbase_breaker = CircuitBreaker()

def _resolve_sequence(mirna_id: str) -> str | None:
    """
    Resolve a miRNA ID to its mature sequence (RNA uppercase).
    Checks local SQLite first, then miRBase REST API via existing db/routes.
    Returns None if not found.
    """
    # 1. Local SQLite cache (fast, offline)
    local = local_db.lookup(mirna_id)
    if local and local.get("sequence"):
        return local["sequence"].upper()

    # 2. miRBase REST API (with circuit breaker)
    breaker_open, _ = _mirbase_breaker.check()
    if breaker_open:
        return None

    try:
        import requests as _requests
        r = _requests.get(
            "https://mirbase.org/api/mirna/",
            params={"name": mirna_id},
            timeout=8,
        )
        if r.status_code == 200:
            body    = r.json()
            results = body.get("results", []) if isinstance(body, dict) else body
            if results:
                seq = results[0].get("mature_sequence", results[0].get("sequence", "")).upper()
                if seq:
                    _mirbase_breaker.record_success()
                    local_db.upsert({
                        "id": mirna_id, "accession": results[0].get("mature_acc", ""),
                        "sequence": seq, "family": results[0].get("family", ""),
                        "species": "", "length": len(seq),
                    })
                    return seq
        _mirbase_breaker.record_failure()
        return None
    except Exception:
        _mirbase_breaker.record_failure()
        return None


# ── Core per-miRNA runner ──────────────────────────────────────────────────────

def _run_one(mirna_id: str, params: dict) -> dict:
    """Design primers for a single miRNA; catch errors per-entry."""
    try:
        seq = _resolve_sequence(mirna_id)
        if seq is None:
            return {"mirna": mirna_id, "status": "error",
                    "error": f"miRNA '{mirna_id}' not found in miRBase or local cache."}

        # validate_rna_sequence expects RNA (AUGC); seq from miRBase is RNA
        is_valid, err_msg = validate_rna_sequence(seq)
        if not is_valid:
            return {"mirna": mirna_id, "status": "error", "error": err_msg}

        data = _pipeline_run(seq, params, mirna_name=mirna_id)
        if "error" in data:
            return {"mirna": mirna_id, "status": "error", "error": data["error"]}
        return {"mirna": mirna_id, "status": "ok", "data": data}
    except Exception as exc:
        return {"mirna": mirna_id, "status": "error", "error": str(exc)}


# ── Sync streaming (NDJSON) ───────────────────────────────────────────────────

def _stream_batch(mirnas: list, params: dict):
    """Generator — yields NDJSON lines for synchronous batch."""
    yield json.dumps({"type": "meta", "total": len(mirnas), "mode": "sync"}) + "\n"
    succeeded = failed = 0
    for i, m in enumerate(mirnas):
        r = _run_one(m, params)
        if r["status"] == "ok":
            succeeded += 1
        else:
            failed += 1
        yield json.dumps({"type": "result", "index": i, **r}) + "\n"
    yield json.dumps({"type": "done", "succeeded": succeeded, "failed": failed}) + "\n"


# ── Async background runner ───────────────────────────────────────────────────

def _run_batch_async(job_id: str, mirnas: list, params: dict) -> None:
    """Background thread — populates job store."""
    job = _JOB_STORE.get(job_id)
    if job is None:
        return
    job.status = "running"
    for m in mirnas:
        r = _run_one(m, params)
        job.completed += 1
        if r["status"] == "ok":
            job.succeeded += 1
            job.results.append(r)
        else:
            job.failed += 1
            job.errors.append({"mirna": m, "error": r.get("error", "unknown")})
    job.status = "done"


# ── Request parsing / validation helpers ──────────────────────────────────────

def _parse_mirna_list(raw: list) -> tuple[list, list]:
    """
    Normalise, deduplicate, and partition miRNA IDs.
    Returns (valid_ids, invalid_ids).
    """
    seen = set()
    valid = []
    invalid = []
    for entry in raw:
        if not isinstance(entry, str):
            continue
        entry = entry.strip()
        if not entry:
            continue
        if entry in seen:
            continue
        seen.add(entry)
        # Basic regex check — still allow through (backend resolves definitively)
        if _RE_MIRNA.match(entry) or len(entry) >= 8:
            valid.append(entry)
        else:
            invalid.append(entry)
    return valid, invalid


def _flatten_params(data: dict) -> dict:
    """Flatten nested param groups (same as routes/design.py)."""
    return {
        **data.get("thermodynamic", {}),
        **data.get("primerConstraints", {}),
        **data.get("qpcr", {}),
        **data.get("detectionMethod", {}),
        **data.get("experimentalContext", {}),
        **data.get("params", {}),   # flat params block (batch schema)
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@batch_design_bp.route("/batch-design", methods=["POST"])
def batch_design():
    """
    POST /api/batch-design

    Request:
      { "mirnas": ["hsa-miR-21-5p", ...], "params": {...} }

    Response (≤10 miRNAs): NDJSON stream, Content-Type: application/x-ndjson
    Response (>10 miRNAs): 202 JSON { job_id, total, mode, status }
    """
    _sweep_expired()

    data      = request.get_json(force=True) or {}
    raw_list  = data.get("mirnas", [])
    params    = _flatten_params(data)

    if not isinstance(raw_list, list) or not raw_list:
        return jsonify({"error": "mirnas must be a non-empty list"}), 400

    valid, invalid = _parse_mirna_list(raw_list)

    warnings = []
    if invalid:
        warnings.append(f"Skipped {len(invalid)} unrecognised entries: {invalid[:5]}")
    if len(valid) > BATCH_MAX_SIZE:
        warnings.append(
            f"Batch size {len(valid)} exceeds BATCH_MAX_SIZE={BATCH_MAX_SIZE}. "
            f"Only the first {BATCH_MAX_SIZE} miRNAs will be processed."
        )
        valid = valid[:BATCH_MAX_SIZE]

    if not valid:
        return jsonify({"error": "No valid miRNA IDs provided."}), 400

    # ── Synchronous path (≤ BATCH_ASYNC_THRESHOLD) ───────────────
    if len(valid) <= BATCH_ASYNC_THRESHOLD:
        return Response(
            _stream_batch(valid, params),
            content_type="application/x-ndjson",
            headers={"X-Batch-Warnings": json.dumps(warnings)},
        )

    # ── Async path (> BATCH_ASYNC_THRESHOLD) ─────────────────────
    job_id = f"batch_{uuid.uuid4().hex[:8]}"
    job = BatchJob(job_id=job_id, total=len(valid))
    with _JOB_STORE_LOCK:
        _JOB_STORE[job_id] = job

    thread = threading.Thread(
        target=_run_batch_async,
        args=(job_id, valid, params),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "job_id":   job_id,
        "total":    len(valid),
        "mode":     "async",
        "status":   "queued",
        "warnings": warnings,
    }), 202


@batch_design_bp.route("/batch-status/<job_id>", methods=["GET"])
def batch_status(job_id: str):
    """
    GET /api/batch-status/<job_id>

    Returns current progress and partial results for an async batch job.
    """
    _sweep_expired()

    job = _JOB_STORE.get(job_id)
    if job is None:
        return jsonify({"error": f"Job '{job_id}' not found or expired."}), 404

    return jsonify({
        "job_id":    job.job_id,
        "status":    job.status,
        "total":     job.total,
        "completed": job.completed,
        "succeeded": job.succeeded,
        "failed":    job.failed,
        "results":   job.results,
        "errors":    job.errors,
    })
