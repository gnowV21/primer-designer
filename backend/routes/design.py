# ================================================================
# routes/design.py — POST /api/design
# Phase 2 main endpoint: run full primer design algorithm.
# ================================================================

import time
from flask import Blueprint, jsonify, request
from algorithm.stemloop_rt import design_stemloop_rt
from algorithm.forward_primer import generate_forward_candidates
from algorithm.universal_reverse import get_universal_reverse
from algorithm.structure_check import run_all_structure_checks
from algorithm.scoring import score_candidate
from algorithm.sequence_utils import validate_rna_sequence
from algorithm.constants import (
    CANDIDATES_TOP_N, OUTPUT_BASE_INDEX,
    SYBR_GREEN_NON_SPECIFIC_RISK, SYBR_GREEN_WARNING_MESSAGE,
)

design_bp = Blueprint("design", __name__)


@design_bp.route("/design", methods=["POST"])
def design_primers():
    start = time.time()
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

    # Global warnings to surface to user
    global_warnings = []

    # SYBR Green warning [V07]
    if params.get("signalMethod", "taqman") == "sybr":
        global_warnings.append({
            "field": "signalMethod",
            "severity": "critical",
            "message": SYBR_GREEN_WARNING_MESSAGE,
        })

    # ── 2. Stem-loop RT primer ───────────────────────────────────
    stemloop = design_stemloop_rt(seq, params)

    # ── 3. Universal reverse primer ──────────────────────────────
    reverse = get_universal_reverse(params)

    # ── 4. Generate forward candidates ───────────────────────────
    candidates, rejection_log = generate_forward_candidates(seq, params)

    if not candidates:
        reasons = {}
        for r in rejection_log:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1

        return jsonify({
            "error": "No valid forward primer candidates found with current parameters.",
            "suggestion": "Try relaxing the Tm range, GC% bounds, or amplicon size constraints.",
            "rejection_summary": reasons,
        }), 422

    # ── 5. Structure checks ───────────────────────────────────────
    for c in candidates:
        c["structure_checks"] = run_all_structure_checks(
            forward_seq=c["sequence"],
            reverse_seq=reverse["sequence"],
            params=params,
        )

    # ── 6. Score all candidates ───────────────────────────────────
    scored = []
    for c in candidates:
        result = score_candidate(c, stemloop, reverse, params)
        scored.append({**c, **result})

    # ── 7. Rank → Top N ──────────────────────────────────────────
    top_n = sorted(scored, key=lambda x: x["total_score"], reverse=True)[:CANDIDATES_TOP_N]
    for i, p in enumerate(top_n):
        p["rank"] = i + 1
        # 1-based output positions [P3P PRIMER_FIRST_BASE_INDEX = 1]
        p["binding_start_1based"] = (p.get("tail_length", 0)) + OUTPUT_BASE_INDEX
        p["binding_end_1based"]   = len(p["sequence"]) + OUTPUT_BASE_INDEX - 1

    elapsed = round(time.time() - start, 2)

    rejection_summary = {}
    for r in rejection_log:
        rejection_summary[r["reason"]] = rejection_summary.get(r["reason"], 0) + 1

    return jsonify({
        "top3": top_n,
        "stemloop_rt": stemloop,
        "universal_reverse": reverse,
        "global_warnings": global_warnings,
        "metadata": {
            "mirna_sequence": seq,
            "mirna_length": len(seq),
            "candidates_generated": len(candidates) + len(rejection_log),
            "candidates_passed_prefilter": len(candidates),
            "candidates_rejected": len(rejection_log),
            "rejection_summary": rejection_summary,
            "elapsed_seconds": elapsed,
            "algorithm_version": "2.8.1",
            "scoring_version": "V3 (11 criteria)",
            "sources": [
                "Chen et al. 2005", "Kramer 2011 Unit 15.10",
                "Varkonyi-Gasic et al. 2007", "Primer3Plus",
                "IDT OligoAnalyzer", "SantaLucia 1998", "PrimerAST 2024",
            ],
        },
    })
