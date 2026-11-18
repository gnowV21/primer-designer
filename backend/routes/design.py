# ================================================================
# routes/design.py — POST /api/design
# ================================================================

from flask import Blueprint, jsonify, request
from algorithm.design_pipeline import run as _run_pipeline
from algorithm.tiered_pipeline import resolve_system
from algorithm.sequence_utils import validate_rna_sequence
from algorithm.constants import OVERHANG_LENGTH_MIN, OVERHANG_LENGTH_MAX

design_bp = Blueprint("design", __name__)


@design_bp.route("/design", methods=["POST"])
def design_primers():
    data = request.get_json(force=True, silent=True)
    # A JSON body that is not an object (null, a list, a string), or a "sequence"
    # that is not an object, is a client error, not a 500.
    if not isinstance(data, dict) or not isinstance(data.get("sequence", {}), dict):
        return jsonify({"error": "Request body must be a JSON object with a "
                                 "'sequence' object ({'matureSequence': ...})."}), 400
    for group in ("thermodynamic", "primerConstraints", "qpcr", "detectionMethod",
                  "experimentalContext"):
        if not isinstance(data.get(group, {}), dict):
            return jsonify({"error": f"'{group}' must be a JSON object."}), 400

    # ── 1. Validate input ─────────────────────────────────────────
    seq = str(data.get("sequence", {}).get("matureSequence") or "").upper().strip()
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
    # RT overhang length: supported 5–7 nt. Reject instead of silently clamping,
    # so the returned primers always match what the user asked for.
    if "bindingRegion3prime" in params:
        # Whole numbers only: int() would truncate 6.9 to 6 (primers for an overhang the
        # user did not ask for); 6.0 and "6" are accepted, booleans and Infinity are not.
        raw = params["bindingRegion3prime"]
        try:
            f = float(raw)
            ov = int(f) if (not isinstance(raw, bool) and f.is_integer()) else None
        except (TypeError, ValueError, OverflowError):
            ov = None
        if ov is None or not (OVERHANG_LENGTH_MIN <= ov <= OVERHANG_LENGTH_MAX):
            return jsonify({"error": (
                f"bindingRegion3prime must be an integer {OVERHANG_LENGTH_MIN}–{OVERHANG_LENGTH_MAX} nt "
                f"(got {params['bindingRegion3prime']!r})."
            )}), 400
        params["bindingRegion3prime"] = ov

    # Ranking system (4.0.0): "tiered" (default) or "v4". Top-level field, or inside
    # any parameter group.
    if data.get("scoringSystem") is not None:
        params["scoringSystem"] = data["scoringSystem"]
    try:
        params["scoringSystem"] = resolve_system(params)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Species drives family cross-reactivity scoping when the miRNA is pasted
    # without a name prefix (otherwise the name prefix is authoritative). [A3]
    params["species"] = data.get("sequence", {}).get("species")
    # The frontend stores the resolved miRNA id in `mirnaName`; API/validator
    # callers use `mirnaId`. Read whichever is present so metadata.mirna_id is
    # populated — the off-target BLAST needs it to exclude the on-target miRNA
    # (an empty id makes the target itself show up as a hit).
    _seq_meta = data.get("sequence", {})
    mirna_name = (_seq_meta.get("mirnaName") or _seq_meta.get("mirnaId") or "").strip()
    # miRBase accession (MIMAT…) — MIQE 2.0 §1 requires the sequence accession number.
    mirna_accession = (_seq_meta.get("mirbaseId") or _seq_meta.get("accession") or "").strip()

    # Hardening: if the miRNA was pasted as a raw sequence (no id — e.g. the user
    # submitted before the client-side reverse lookup finished), resolve the id
    # locally from the mature sequence. This keeps metadata.mirna_id populated so
    # the off-target BLAST can still exclude the on-target. Local SQLite only —
    # offline, no remote call, no added latency; a novel sequence not in the
    # cache simply leaves the name empty (unchanged behaviour).
    if not mirna_name or not mirna_accession:
        try:
            from db import local_db
            _hit = local_db.lookup(seq) or (local_db.lookup(mirna_name) if mirna_name else None)
            if _hit:
                if not mirna_name and _hit.get("name"):
                    mirna_name = _hit["name"]
                if not mirna_accession and _hit.get("accession"):
                    mirna_accession = _hit["accession"]
        except Exception:
            pass  # resolution is best-effort; never block a design on it

    # Accession travels via params so the pipeline can record it in metadata
    # (MIQE 2.0 §1 "Official gene symbol, species and sequence accession number").
    params["mirna_accession"] = mirna_accession

    # ── 2. Run pipeline ───────────────────────────────────────────
    result = _run_pipeline(seq, params, mirna_name)

    if "error" in result:
        return jsonify(result), 422
    return jsonify(result)
