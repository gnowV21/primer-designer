# ================================================================
# routes/benchmark.py — GET /api/benchmark  (Phase 7 PART F)
#
# Serves precomputed benchmark_results.json (static file read).
# Does NOT run the benchmark at request time — that would be too
# slow and depends on external tools (miRprimer/Ruby).
#
# Run offline: cd benchmark && python run_benchmark.py
# Then commit the updated benchmark_results.json.
#
# Security: reads only from a whitelisted static path; no user
# input used in file path → no path traversal risk.
# ================================================================

import json
import os

from flask import Blueprint, jsonify

benchmark_bp = Blueprint("benchmark", __name__)

_RESULTS_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "benchmark", "benchmark_results.json",
    )
)


@benchmark_bp.route("/benchmark", methods=["GET"])
def get_benchmark():
    """
    GET /api/benchmark

    Response (file present, even if PENDING):
        { _metadata: {...}, metrics: {...} | null, per_assay: [...] }

    Response (file missing):
        { available: false, message: "..." }
    """
    if not os.path.isfile(_RESULTS_PATH):
        return jsonify({
            "available": False,
            "message": (
                "Benchmark results not found. "
                "Run benchmark/run_benchmark.py offline and commit benchmark_results.json."
            ),
        })

    try:
        with open(_RESULTS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as exc:
        return jsonify({
            "available": False,
            "message": f"Could not read benchmark results: {exc}",
        })
