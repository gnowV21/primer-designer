# ================================================================
# routes/blast_check.py — POST /api/blast-check  (Phase 3, optional)
#
# Features:
#   - Rate limit: 10 req/min/IP  [spec §9.3]
#   - SQLite cache: TTL 30 days  [spec §9.1]
#   - Circuit breaker: 3 fails → OPEN 60s  [spec §9.2]
#   - Database freshness warning: >90 days  [spec §9.4]
# ================================================================

import os
import subprocess

from flask import Blueprint, jsonify, request

from algorithm.specificity_check.blast_offtarget import (
    check_offtarget, _METADATA,
)
from algorithm.specificity_check.blast_cache import BlastCache
from db.circuit_breaker import CircuitBreaker
from scripts.build_blast_db import check_db_freshness
from algorithm.constants import (
    BLAST_CB_FAILURE_THRESHOLD, BLAST_CB_RECOVERY_TIMEOUT,
)

blast_check_bp = Blueprint("blast_check", __name__)

# Module-level singletons (reset on server restart, not persisted)
_cache           = BlastCache()
_circuit_breaker = CircuitBreaker()
# Override defaults from constants
_circuit_breaker.FAILURE_THRESHOLD = BLAST_CB_FAILURE_THRESHOLD
_circuit_breaker.RESET_TIMEOUT     = BLAST_CB_RECOVERY_TIMEOUT


@blast_check_bp.route("/blast-check", methods=["POST"])
def blast_check():
    """
    POST /api/blast-check

    Request body:
        {
          "forward_primer": "CACGCATGGAAGGACGGG",
          "reverse_primer": "CCAGTGCAGGGTCCGAGGTA",  // optional
          "mirna_id": "hsa-miR-21-5p"                 // optional, to skip self-hit
        }

    Response: see SPEC_phase3.md §8.9
    """
    # ── Rate limiting handled by flask-limiter decorator on app registration ──

    # ── 1. Parse request ────────────────────────────────────────
    data = request.get_json(force=True) or {}
    fwd  = (data.get("forward_primer") or "").upper().strip()
    rev  = (data.get("reverse_primer") or "").upper().strip()
    mirna_id = (data.get("mirna_id") or "").strip()

    if not fwd:
        return jsonify({"error": "forward_primer is required"}), 400
    if len(fwd) > 60:
        return jsonify({"error": "forward_primer too long (max 60 nt)"}), 400
    if not fwd.replace("ACGTN", ""):  # validate nucleotide chars
        pass  # valid
    invalid_chars = set(fwd) - set("ACGTN")
    if invalid_chars:
        return jsonify({"error": f"Invalid characters in forward_primer: {invalid_chars}"}), 400

    # ── 2. Database freshness check ──────────────────────────────
    db_info = check_db_freshness(_METADATA)

    # ── 3. Cache lookup ─────────────────────────────────────────
    db_version = db_info.get("build_date", "unknown")
    cached = _cache.get_result(fwd, rev, db_version)
    if cached is not None:
        cached["cache"] = {"hit": True, "cache_key": BlastCache._compute_key(fwd, rev, db_version)}
        cached["database_info"] = db_info
        return jsonify(cached)

    # ── 4. Circuit breaker check ─────────────────────────────────
    is_open, seconds_left = _circuit_breaker.check()
    if is_open:
        return jsonify({
            "error": "BLAST service temporarily unavailable (circuit open after repeated failures).",
            "retry_after_seconds": seconds_left,
        }), 503

    # ── 5. Run BLAST ─────────────────────────────────────────────
    try:
        result = check_offtarget(
            forward_primer=fwd,
            reverse_primer=rev or None,
            mirna_id=mirna_id or None,
            timeout=60,
        )
        _circuit_breaker.record_success()
    except subprocess.TimeoutExpired:
        _circuit_breaker.record_failure()
        return jsonify({"error": "BLAST search timed out (>60s). Try again later."}), 504
    except subprocess.CalledProcessError as e:
        _circuit_breaker.record_failure()
        return jsonify({"error": f"BLAST subprocess failed: {e.returncode}"}), 500
    except FileNotFoundError:
        _circuit_breaker.record_failure()
        return jsonify({
            "error": "blastn binary not found. NCBI BLAST+ must be installed on the server."
        }), 503
    except Exception as e:
        _circuit_breaker.record_failure()
        return jsonify({"error": f"Internal error: {e}"}), 500

    # ── 6. Cache result ──────────────────────────────────────────
    _cache.set_result(fwd, rev, result, db_version)

    result["cache"]         = {"hit": False, "cache_key": BlastCache._compute_key(fwd, rev, db_version)}
    result["database_info"] = db_info

    return jsonify(result)
