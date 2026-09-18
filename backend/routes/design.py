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
