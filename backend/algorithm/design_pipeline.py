"""
design_pipeline.py — Core design logic extracted from routes/design.py.
Called by /api/design.

Input:  seq (str), params (dict), mirna_name (str)
Output: full result dict matching the /api/design JSON schema
"""

import time

from algorithm.stemloop_rt import design_stemloop_rt
from algorithm.forward_primer import generate_forward_candidates
from algorithm.universal_reverse import get_universal_reverse
from algorithm.structure_check import run_all_structure_checks
from algorithm.structure_check.heterodimer import (
    check_all_heterodimers,
    check_stemloop_reverse_heterodimer,
)
from algorithm.specificity_check.family_crossreactivity import check_family_crossreactivity
from algorithm.specificity_check.isomir_flag import check_isomir_flag
from algorithm.scoring import score_candidate
from algorithm.sequence_utils import validate_rna_sequence
from algorithm.edge_cases import detect_edge_cases
from algorithm.protocol_advisor import advise_protocol
from algorithm.hard_filters import apply_hard_filters
from algorithm.template_structure import check_template_structure
from algorithm.probe_design import design_probe
from algorithm.normalization_advisor import advise_normalization
from algorithm.constants import (
    CANDIDATES_TOP_N, OUTPUT_BASE_INDEX,
    SYBR_GREEN_NON_SPECIFIC_RISK, SYBR_GREEN_WARNING_MESSAGE,
    OVERHANG_LENGTH_DEFAULT, HARD_FILTER_ENABLED,
)


def run(seq: str, params: dict, mirna_name: str = "") -> dict:
    """
    Execute the full primer design pipeline.

    Parameters
    ----------
    seq        : mature miRNA sequence (RNA, uppercase, already validated)
    params     : flattened parameter dict (thermodynamic, primerConstraints, qpcr, …)
    mirna_name : optional miRNA identifier for specificity / isoMiR checks

    Returns
    -------
    dict matching the /api/design JSON response schema
    """
    start = time.time()

    global_warnings = []

    # SYBR Green warning
    if params.get("signalMethod", "taqman") == "sybr":
        global_warnings.append({
            "field": "signalMethod",
            "severity": "critical",
            "message": SYBR_GREEN_WARNING_MESSAGE,
        })

    # Off-label overhang warning
    binding_len = int(params.get("bindingRegion3prime", OVERHANG_LENGTH_DEFAULT))
    if binding_len != OVERHANG_LENGTH_DEFAULT:
        global_warnings.append({
            "field": "bindingRegion3prime",
            "severity": "warning",
            "message": (
                f"Off-label: {binding_len} nt binding region has not been experimentally "
                f"validated. Chen et al. 2005 only tested 6 nt. Interpret results with caution."
            ),
        })

    # Edge-case detection
    edge_cases = detect_edge_cases(seq)
    for ec in edge_cases:
        if ec["severity"] == "critical":
            global_warnings.append({
                "field": f"edge_case_{ec['code']}",
                "severity": "critical",
                "message": ec["message"],
            })

    # Stem-loop RT primer
    stemloop = design_stemloop_rt(seq, params)

    # Universal reverse primer
    reverse = get_universal_reverse(params)
    rev_ss = reverse["self_structure_check"]
    if rev_ss.get("calculation_error"):
        global_warnings.append({
            "field": "universal_reverse",
            "severity": "warning",
            "message": "Universal reverse primer self-structure check failed.",
        })
    elif rev_ss.get("hairpin_risk") == "critical" or rev_ss.get("self_dimer_risk") == "critical":
        global_warnings.append({
            "field": "universal_reverse",
            "severity": "warning",
            "message": (
                f"Universal reverse primer has a self-structure issue "
                f"(hairpin ΔG = {rev_ss['hairpin_dg']} kcal/mol, "
                f"self-dimer ΔG = {rev_ss['self_dimer_dg']} kcal/mol)."
            ),
        })

    # Stemloop × Reverse heterodimer
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
                f"Stem-loop RT × Universal Reverse heterodimer: ΔG = {stemloop_rev_check['dg']:.2f} "
                f"kcal/mol — {stemloop_rev_check['risk_level']} RISK. {stemloop_rev_check['protocol_note']}"
            ),
        })

    # Forward candidates
    candidates, rejection_log = generate_forward_candidates(seq, params)

    if not candidates:
        reasons = {}
        for r in rejection_log:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
        return {
            "error": "No valid forward primer candidates found with current parameters.",
            "suggestion": "Try relaxing the Tm range, GC% bounds, or amplicon size constraints.",
            "rejection_summary": reasons,
            "edge_cases": edge_cases,
            "global_warnings": global_warnings,
        }

    # Structure checks per candidate
    for c in candidates:
        c["structure_checks"] = run_all_structure_checks(
            forward_seq=c["sequence"],
            reverse_seq=reverse["sequence"],
            params=params,
        )
        c["heterodimer_checks"] = check_all_heterodimers(
            forward_seq=c["sequence"],
            stemloop_seq=stemloop["sequence"],
            reverse_seq=reverse["sequence"],
            params=params,
        )
        c["template_structure"] = check_template_structure(seq, c, params)

    # Hard-filter gate
    if HARD_FILTER_ENABLED:
        hard_passed = []
        for c in candidates:
            rejections = apply_hard_filters(c)
            if rejections:
                for reason in rejections:
                    rejection_log.append({"sequence": c.get("sequence", ""), "reason": reason})
            else:
                hard_passed.append(c)

        if not hard_passed and candidates:
            global_warnings.append({
                "field": "hard_filter_fallback",
                "severity": "warning",
                "message": (
                    "All candidates rejected by hard-filter gate. Returning best available "
                    "candidates without hard-filter enforcement."
                ),
            })
        else:
            candidates = hard_passed

    # Score candidates
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

    # Rank → Top N
    top_n = sorted(scored, key=lambda x: x["total_score"], reverse=True)[:CANDIDATES_TOP_N]
    for i, p in enumerate(top_n):
        p["rank"] = i + 1
        p["binding_start_1based"] = (p.get("tail_length", 0)) + OUTPUT_BASE_INDEX
        p["binding_end_1based"]   = len(p["sequence"]) + OUTPUT_BASE_INDEX - 1
        p["isomir_flag"] = check_isomir_flag(
            mirna_name=mirna_name,
            forward_3prime_position=p.get("specific_length", 0),
        )

    # Cross-reactivity warning
    cross_reactivity = cross_reactivity_shared
    if any(r.get("risk") in ("IDENTICAL", "HIGH") for r in cross_reactivity.get("cross_reactivity", [])):
        global_warnings.append({
            "field": "cross_reactivity",
            "severity": "warning",
            "message": (
                f"Cross-reactivity risk detected: {cross_reactivity['family']} family members "
                f"share ≤1 nt difference in the {binding_len}-nt stemloop overhang region."
            ),
        })

    # Template structure warnings
    for p in top_n:
        ts = p.get("template_structure", {})
        if ts.get("has_strong_local_hairpin"):
            global_warnings.append({
                "field": "template_structure",
                "severity": "warning",
                "message": (
                    f"Rank #{p['rank']} forward primer: "
                    + (ts.get("warning") or "Template hairpin detected at binding site.")
                ),
            })

    elapsed = round(time.time() - start, 2)

    rejection_summary = {}
    for r in rejection_log:
        rejection_summary[r["reason"]] = rejection_summary.get(r["reason"], 0) + 1

    # TaqMan probe
    signal_method = params.get("signalMethod", "taqman")
    probe_result = None
    probe_note   = None
    if signal_method == "taqman" and top_n:
        probe_result = design_probe(
            mature_seq=seq,
            stemloop_seq=stemloop["sequence"],
            forward_primer=top_n[0],
            params=params,
            mode=params.get("probeMode", "custom"),
            probe_type=params.get("probeType", "single_q"),
        )
    else:
        probe_note = (
            "No TaqMan probe designed (SYBR Green detection selected). "
            "Set detectionMethod.signalMethod='taqman' to enable probe design."
        )

    # Protocol advisor
    _partial = {
        "edge_cases": edge_cases,
        "specificity_warnings": {"cross_reactivity": cross_reactivity},
    }
    protocol_advice = advise_protocol(_partial, params)

    # Normalization advisor
    sample_type = params.get("sampleType", "")
    try:
        panel_size = int(params.get("panelSize") or 1)
    except (ValueError, TypeError):
        panel_size = 1
    normalization_advice = advise_normalization(sample_type, panel_size) if sample_type else None

    # LNA hints (edge case E1 / E4)
    lna_hints = None
    ec_codes = {ec.get("code") for ec in edge_cases}
    if "E1" in ec_codes or "E4" in ec_codes:
        lna_hints = {
            "applicable": True,
            "rationale": (
                "This miRNA is short (<18 nt) or has low GC content (<30%), "
                "which may result in a low forward primer Tm. "
                "Consider 2-3 LNA substitutions in the specific-region to raise Tm by ~2-8°C "
                "per position, or extend the 5′ tail to achieve the target Tm."
            ),
            "sources": [
                {"tag": "Andreasen10", "doi": "10.1016/j.ymeth.2010.01.006"},
                {"tag": "Kunwar23",    "doi": "10.3390/diagnostics13132170"},
            ],
            "disclaimer": "For research use only. LNA positions require empirical optimisation.",
        }

    return {
        "top3": top_n,
        "probe": probe_result,
        "probe_note": probe_note,
        "stemloop_rt": stemloop,
        "universal_reverse": {
            **reverse,
            "stemloop_reverse_heterodimer": stemloop_rev_check,
        },
        "global_warnings": global_warnings,
        "edge_cases": edge_cases,
        "protocol_advice": protocol_advice,
        "normalization_advice": normalization_advice,
        "lna_hints": lna_hints,
        "specificity_warnings": {
            "cross_reactivity": cross_reactivity,
            "data_note": (
                "Family data: miRBase CURRENT, seed-based grouping (positions 2-8). "
                "isoMiR data: curated from literature (7 entries, partial coverage). "
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
            "output_label": "predicted design quality",
            "output_note": (
                "Score reflects in-silico design quality (Tm, GC%, structure, specificity). "
                "It does NOT predict PCR amplification efficiency."
            ),
            "sources": [
                "Chen et al. 2005", "Kramer 2011 Unit 15.10",
                "Varkonyi-Gasic et al. 2007", "Primer3Plus",
                "IDT OligoAnalyzer", "SantaLucia 1998", "PrimerAST 2024",
            ],
        },
    }
