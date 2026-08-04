# ================================================================
# routes/design.py — POST /api/design
# ================================================================

from flask import Blueprint, jsonify, request
from algorithm.design_pipeline import run as _run_pipeline
from algorithm.sequence_utils import validate_rna_sequence

design_bp = Blueprint("design", __name__)


@design_bp.route("/design", methods=["POST"])
def design_primers():
    data = request.get_json(force=True)

    # ── 1. Validate input ─────────────────────────────────────────
    seq = data.get("sequence", {}).get("matureSequence", "").upper().strip()
    is_valid, err_msg = validate_rna_sequence(seq)
    if not is_valid:
        return jsonify({"error": err_msg}), 400

    # Flatten params from all form groups
    params = {
        **data.get("thermodynamic", {}),
        **data.get("primerConstraints", {}),
        **data.get("qpcr", {}),
        **data.get("detectionMethod", {}),
        **data.get("experimentalContext", {}),
    }
    mirna_name = data.get("sequence", {}).get("mirnaId", "") or ""

    # ── 2. Run pipeline ───────────────────────────────────────────
    result = _run_pipeline(seq, params, mirna_name)

    if "error" in result:
        return jsonify(result), 422
    return jsonify(result)
