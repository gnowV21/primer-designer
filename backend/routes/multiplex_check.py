# ================================================================
# routes/multiplex_check.py — POST /api/multiplex-check
# Phase 6 PART B (SPEC_phase6 §B.3)
#
# Rate-limit: 10 req/min/IP (same as blast-check).
# ================================================================

from flask import Blueprint, jsonify, request
from algorithm.multiplex_check import check_multiplex_panel

multiplex_check_bp = Blueprint("multiplex_check", __name__)


@multiplex_check_bp.route("/multiplex-check", methods=["POST"])
def multiplex_check():
    """
    POST /api/multiplex-check

    Body:
        {
            "primer_sets": [
                {"mirna_id": "hsa-miR-21-5p", "forward": "GCATTATGAGT...", "probe": null},
                {"mirna_id": "hsa-let-7a-5p", "forward": "GTTCGGCGTCT...", "probe": null}
            ],
            "params": {}   // optional salt/Mg overrides
        }

    200 → { pairs, worst_risk, panel_ok, warnings, recommendations }
    400 → { error: "..." }
    """
    data = request.get_json(force=True)
    primer_sets = data.get("primer_sets", [])
    params      = data.get("params", {})

    # Validate: need at least 2 sets with forward sequences
    if len(primer_sets) < 2:
        return jsonify({"error": "At least 2 primer sets required for multiplex cross-dimer check."}), 400

    missing = [i for i, s in enumerate(primer_sets) if not s.get("forward", "").strip()]
    if missing:
        return jsonify({"error": f"primer_sets[{missing[0]}] is missing 'forward' sequence."}), 400

    result = check_multiplex_panel(primer_sets, params)
    return jsonify(result), 200
