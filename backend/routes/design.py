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
from algorithm.structure_check.heterodimer import check_all_heterodimers, check_stemloop_reverse_heterodimer
from algorithm.specificity_check.family_crossreactivity import check_family_crossreactivity
from algorithm.specificity_check.isomir_flag import check_isomir_flag
from algorithm.scoring import score_candidate
from algorithm.sequence_utils import validate_rna_sequence
from algorithm.edge_cases import detect_edge_cases
from algorithm.constants import (
    CANDIDATES_TOP_N, OUTPUT_BASE_INDEX,
    SYBR_GREEN_NON_SPECIFIC_RISK, SYBR_GREEN_WARNING_MESSAGE,
    OVERHANG_LENGTH_DEFAULT,
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

    # Off-label overhang warning — surfaced as a global warning in results
    binding_len = int(params.get("bindingRegion3prime", 6))
    if binding_len != 6:
        global_warnings.append({
            "field": "bindingRegion3prime",
            "severity": "warning",
            "message": (
                f"Off-label: {binding_len} nt binding region has not been experimentally "
                f"validated. Chen et al. 2005 (the definitive stem-loop RT-qPCR reference) "
                f"only tested 6 nt. Interpret results with caution."
            ),
        })

    mirna_name = data.get("sequence", {}).get("mirnaId", "") or ""

    # ── 2. Stem-loop RT primer ───────────────────────────────────
    stemloop = design_stemloop_rt(seq, params)

    # ── 3. Universal reverse primer ──────────────────────────────
    reverse = get_universal_reverse(params)
    rev_ss = reverse["self_structure_check"]
    if rev_ss.get("calculation_error"):
        global_warnings.append({
            "field": "universal_reverse",
            "severity": "warning",
            "message": "Universal reverse primer self-structure check failed (primer3 error under current buffer conditions).",
        })
    elif rev_ss.get("hairpin_risk") == "critical" or rev_ss.get("self_dimer_risk") == "critical":
        global_warnings.append({
            "field": "universal_reverse",
            "severity": "warning",
            "message": (
                f"Universal reverse primer has a self-structure issue under current buffer "
                f"conditions (hairpin ΔG = {rev_ss['hairpin_dg']} kcal/mol, "
                f"self-dimer ΔG = {rev_ss['self_dimer_dg']} kcal/mol). "
                f"Consider adjusting salt/Mg²⁺ concentration."
            ),
        })

    # ── 3b. Stemloop × Reverse heterodimer (one-step RT-qPCR global check) ──
    # Both stemloop and reverse are fixed sequences — computed once, not per candidate.
    stemloop_rev_check = check_stemloop_reverse_heterodimer(
        stemloop_seq=stemloop["sequence"],
        reverse_seq=reverse["sequence"],
        params=params,
    )
    if stemloop_rev_check["risk_level"] in ("HIGH", "MODERATE"):
        severity = "critical" if stemloop_rev_check["risk_level"] == "HIGH" else "warning"
        global_warnings.append({
            "field": "stemloop_reverse_heterodimer",
            "severity": severity,
            "message": (
                f"Stem-loop RT × Universal Reverse heterodimer: ΔG = {stemloop_rev_check['dg']:.2f} kcal/mol "
                f"— {stemloop_rev_check['risk_level']} RISK. "
                f"{stemloop_rev_check['protocol_note']}"
            ),
        })

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

    # ── 5. Structure checks (per candidate) ──────────────────────
    for c in candidates:
        c["structure_checks"] = run_all_structure_checks(
            forward_seq=c["sequence"],
            reverse_seq=reverse["sequence"],
            params=params,
        )
        # Heterodimer: forward × stemloop RT (RT step) + forward × reverse (PCR step)
        c["heterodimer_checks"] = check_all_heterodimers(
            forward_seq=c["sequence"],
            stemloop_seq=stemloop["sequence"],
            reverse_seq=reverse["sequence"],
            params=params,
        )

    # ── 6. Score all candidates (V4: includes bound_fraction + family) ─
    # cross_reactivity is the same for all candidates (depends on miRNA, not primer)
    cross_reactivity_shared = check_family_crossreactivity(
        mature_seq=seq,
        mirna_name=mirna_name,
        params=params,
        overhang_len=binding_len,
    )
    scored = []
    for c in candidates:
        result = score_candidate(
            c, stemloop, reverse, params,
            cross_reactivity=cross_reactivity_shared,
            use_v4=True,
        )
        scored.append({**c, **result})

    # ── 7. Rank → Top N ──────────────────────────────────────────
    top_n = sorted(scored, key=lambda x: x["total_score"], reverse=True)[:CANDIDATES_TOP_N]
    for i, p in enumerate(top_n):
        p["rank"] = i + 1
        p["binding_start_1based"] = (p.get("tail_length", 0)) + OUTPUT_BASE_INDEX
        p["binding_end_1based"]   = len(p["sequence"]) + OUTPUT_BASE_INDEX - 1
        # isoMiR flag per candidate (depends on forward primer 3' end position)
        p["isomir_flag"] = check_isomir_flag(
            mirna_name=mirna_name,
            forward_3prime_position=p.get("specific_length", 0),
        )

    # ── 8. Global specificity checks — reuse pre-computed result ─────
    cross_reactivity = cross_reactivity_shared

    # Promote HIGH cross-reactivity to global_warnings for immediate visibility
    if any(r["risk"] in ("IDENTICAL", "HIGH") for r in cross_reactivity.get("cross_reactivity", [])):
        global_warnings.append({
            "field": "cross_reactivity",
            "severity": "warning",
            "message": (
                f"Cross-reactivity risk detected: {cross_reactivity['family']} family members "
                f"share ≤1 nt difference in the {binding_len}-nt stemloop overhang region. "
                f"See specificity_warnings.cross_reactivity for details."
            ),
        })

    # ── Edge-case detection ──────────────────────────────────────
    edge_cases = detect_edge_cases(seq)
    for ec in edge_cases:
        if ec["severity"] == "critical":
            global_warnings.append({
                "field": f"edge_case_{ec['code']}",
                "severity": "critical",
                "message": ec["message"],
            })

    elapsed = round(time.time() - start, 2)

    rejection_summary = {}
    for r in rejection_log:
        rejection_summary[r["reason"]] = rejection_summary.get(r["reason"], 0) + 1

    return jsonify({
        "top3": top_n,
        "stemloop_rt": stemloop,
        "universal_reverse": {
            **reverse,
            "stemloop_reverse_heterodimer": stemloop_rev_check,
        },
        "global_warnings": global_warnings,
        "edge_cases": edge_cases,
        "specificity_warnings": {
            "cross_reactivity": cross_reactivity,
            "data_note": (
                "Family data: miRBase CURRENT, seed-based grouping (positions 2-8). "
                "isoMiR data: curated from literature (7 entries, partial coverage — treat as informational only). "
                "Re-run scripts/build_mirbase_data.py after miRBase updates."
            ),
        },
        "metadata": {
            "mirna_id": mirna_name,
            "mirna_sequence": seq,
            "mirna_length": len(seq),
            "binding_region_nt": binding_len,
            "candidates_generated": len(candidates) + len(rejection_log),
            "candidates_passed_prefilter": len(candidates),
            "candidates_rejected": len(rejection_log),
            "rejection_summary": rejection_summary,
            "elapsed_seconds": elapsed,
            "algorithm_version": "3.0.0",
            "scoring_version": "V4 (15 criteria)",
            "sources": [
                "Chen et al. 2005", "Kramer 2011 Unit 15.10",
                "Varkonyi-Gasic et al. 2007", "Primer3Plus",
                "IDT OligoAnalyzer", "SantaLucia 1998", "PrimerAST 2024",
            ],
        },
    })
