# ================================================================
# scoring.py — Module 6: weighted scoring
# V3 (12 criteria, SCORING_WEIGHTS_V3) — Phase 2, kept as reference.
# V4 (15 criteria, SCORING_WEIGHTS_V4) — Phase 3 default.
# Total score 0–100. Grade: Excellent(≥80), Good(65–79), Acceptable(50–64), Poor(<50).
# ================================================================

from .constants import (
    SCORING_WEIGHTS_V3, SCORING_WEIGHTS_V4,
    FAMILY_DISCRIMINATION_RISK_SCORE,
    TM_FORWARD_TARGET, TM_FORWARD_TOLERANCE,
    TM_BINDING_TARGET, TM_BINDING_TOLERANCE,
    TM_PAIR_DIFF_MAX, GC_MIN, GC_MAX, GC_OPTIMAL,
    MFE_STEMLOOP_MIN, MFE_STEMLOOP_MAX, MFE_STEMLOOP_OPTIMAL,
    MFE_STEMLOOP_MIN_RNA, MFE_STEMLOOP_MAX_RNA, MFE_STEMLOOP_OPTIMAL_RNA,
    HAIRPIN_DG_MAX_INTERNAL, SELF_DIMER_DG_3PRIME_MAX, END_STABILITY_MAX,
    AMPLICON_MIN_QPCR, AMPLICON_MAX_QPCR, AMPLICON_IDEAL,
    FORWARD_OPTIMAL_LENGTH, GC_SKEW_WARNING_THRESHOLD,
)
from .sequence_utils import calculate_gc_skew
from .bound_fraction import (
    calculate_bound_fraction_binding,
    calculate_bound_fraction_full,
    score_bound_fraction,
)


def score_candidate(
    forward: dict,
    stemloop: dict,
    reverse: dict,
    params: dict,
    cross_reactivity: dict | None = None,
    use_v4: bool = True,
) -> dict:
    """
    Score a complete primer set.
    use_v4=True (default): 15 criteria (SCORING_WEIGHTS_V4, Phase 3).
    use_v4=False: 12 criteria (SCORING_WEIGHTS_V3, Phase 2 compat).
    cross_reactivity: output from check_family_crossreactivity (needed for V4).
    """
    scores = {}
    explanations = {}
    sc = forward.get("structure_checks", {})

    # ── 1. Full primer Tm accuracy (0.20) ────────────────────────
    tm = forward["tm_full"]
    tm_diff = abs(tm - TM_FORWARD_TARGET)
    scores["tm_accuracy"] = round(max(0, 100 - (tm_diff / TM_FORWARD_TOLERANCE) * 50), 1)
    explanations["tm_accuracy"] = (
        f"Forward primer Tm = {tm}°C (target: {TM_FORWARD_TARGET}°C, ±{TM_FORWARD_TOLERANCE}°C). "
        f"Δ = {tm_diff:.1f}°C. Method: SantaLucia 1998 nearest-neighbor + Mg²⁺ salt correction."
    )

    # ── 2. Binding-region Tm accuracy (0.10) [P3P 2-step logic] ──
    # v2.8 fix: target was 35°C — calibrated for probe oligos ≤10 nt, not for
    # 12-17 nt miRNA-specific regions whose SantaLucia 1998 Tm is 40-52°C.
    # New target: TM_BINDING_TARGET=45°C; tolerance ±10°C → score 100 at 45°C.
    tm_bind = forward.get("tm_binding", tm)
    tm_bind_diff = abs(tm_bind - TM_BINDING_TARGET)
    scores["tm_binding_accuracy"] = round(max(0, 100 - (tm_bind_diff / TM_BINDING_TOLERANCE) * 50), 1)
    explanations["tm_binding_accuracy"] = (
        f"Binding region Tm = {tm_bind}°C (specific {forward.get('specific_length', '?')} nt region, "
        f"target: {TM_BINDING_TARGET}°C ± {TM_BINDING_TOLERANCE}°C). "
        f"Based on Primer3Plus SEQUENCE_OVERHANG_LEFT principle (SantaLucia 1998 NN)."
    )

    # ── 3. GC content (0.07 V3 / 0.08 V4) ───────────────────────
    gc = forward["gc_percent"]
    if GC_MIN <= gc <= GC_MAX:
        gc_score = max(60, 100 - abs(gc - GC_OPTIMAL) * 2)
    else:
        gc_score = max(0, 30 - abs(gc - GC_OPTIMAL) * 2)
    scores["gc_content"] = round(gc_score, 1)
    explanations["gc_content"] = (
        f"GC content = {gc}% (optimal: {GC_MIN}–{GC_MAX}%, target: {GC_OPTIMAL}%). "
        f"Source: IDT guidelines, PrimerAST 2024."
    )

    # ── 4. GC-skew (0.02 V3 / 0.01 V4) [PAST24] ─────────────────
    skew = calculate_gc_skew(forward["sequence"])
    if skew <= 0:
        skew_score = 100
    elif skew <= 0.1:
        skew_score = 85
    elif skew <= GC_SKEW_WARNING_THRESHOLD:
        skew_score = 70
    else:
        skew_score = max(0, 70 - (skew - GC_SKEW_WARNING_THRESHOLD) * 200)
    scores["gc_skew"] = round(skew_score, 1)
    explanations["gc_skew"] = (
        f"GC-skew = {skew:.3f}. Optimal: ≤ 0 (more C than G). "
        f"Positive skew (more G) risks G-quadruplex formation. Source: PrimerAST 2026."
    )

    # ── 5. Stem-loop MFE (0.15) ──────────────────────────────────
    mfe        = stemloop["mfe"]
    mfe_method = stemloop.get("mfe_method", "")
    # Exact-match only: "primer3-py (ViennaRNA unavailable)" contains "ViennaRNA"
    # as substring but must NOT use RNA thresholds — it is a DNA proxy value.
    _rna_method = mfe_method in ("ViennaRNA", "RNAfold")
    _mfe_opt   = MFE_STEMLOOP_OPTIMAL_RNA if _rna_method else MFE_STEMLOOP_OPTIMAL
    mfe_min    = float(params.get("mfeMin", MFE_STEMLOOP_MIN_RNA if _rna_method else MFE_STEMLOOP_MIN))
    mfe_max    = float(params.get("mfeMax", MFE_STEMLOOP_MAX_RNA if _rna_method else MFE_STEMLOOP_MAX))
    if mfe_min <= mfe <= mfe_max:
        # Piecewise-linear: score=60 at both boundaries, score=100 at _mfe_opt.
        if mfe <= _mfe_opt:
            frac = (mfe - mfe_min) / (_mfe_opt - mfe_min) if (_mfe_opt - mfe_min) > 0 else 1.0
        else:
            frac = (mfe_max - mfe) / (mfe_max - _mfe_opt) if (mfe_max - _mfe_opt) > 0 else 1.0
        mfe_score = 60.0 + 40.0 * max(0.0, frac)
    elif mfe < mfe_min:
        mfe_score = max(0, 60 + (mfe - mfe_min) * 5)
    else:
        mfe_score = max(0, 60 - (mfe - mfe_max) * 5)
    scores["mfe_stemloop"] = round(mfe_score, 1)
    explanations["mfe_stemloop"] = (
        f"Stem-loop MFE = {mfe:.2f} kcal/mol (valid: {mfe_min} to {mfe_max} kcal/mol, "
        f"target: {_mfe_opt} kcal/mol). "
        f"Sweet spot balances RT efficiency vs PCR denaturability. "
        f"Method: {mfe_method}. "
        f"Source: Report 2 HG Lab, Chen et al. 2005."
    )

    # ── 6. Hairpin penalty (0.10 V3 / 0.08 V4) ───────────────────
    hp = sc.get("hairpin", {})
    hp_dg  = hp.get("dg", 0.0)
    sev    = hp.get("severity", "safe")
    hp_map = {"safe": 100, "acceptable": 80, "warning": 40, "critical": 0}
    scores["hairpin_penalty"] = hp_map.get(sev, 50)
    explanations["hairpin_penalty"] = (
        f"Hairpin ΔG = {hp_dg:.2f} kcal/mol (threshold: > {HAIRPIN_DG_MAX_INTERNAL} kcal/mol). "
        f"Severity: {sev}. Primer3Plus thermodynamic alignment enabled."
    )

    # ── 7. Dimer penalty (0.10 V3 / 0.08 V4) ────────────────────
    sd_end   = sc.get("self_dimer", {}).get("dg_3prime", 0.0)
    hd_end   = sc.get("hetero_dimer", {}).get("dg_3prime", 0.0)
    worst    = min(sd_end, hd_end)
    critical = sc.get("has_critical_flag", False)

    if critical:          dimer_score = 0
    elif worst > -4.0:    dimer_score = 100
    elif worst > -5.0:    dimer_score = 75
    elif worst > -6.0:    dimer_score = 40
    else:                 dimer_score = 0
    scores["dimer_penalty"] = dimer_score
    explanations["dimer_penalty"] = (
        f"Worst 3'-end dimer ΔG = {worst:.2f} kcal/mol (threshold: > {SELF_DIMER_DG_3PRIME_MAX} kcal/mol). "
        + ("CRITICAL: polymerase can extend this dimer. " if critical else "")
        + "Source: IDT OligoAnalyzer, Premier Biosoft qPCR guidelines."
    )

    # ── 8. 3' End stability (0.10 V3 / 0.08 V4) [P3P] ───────────
    es = sc.get("end_stability", {})
    es_val  = es.get("stability_kcal_mol", 0.0)
    es_pass = es.get("pass", True)
    if es_pass:
        es_score = 100
    else:
        es_score = max(0, 80 - (es_val - END_STABILITY_MAX) * 15)
    scores["end_stability"] = round(es_score, 1)
    explanations["end_stability"] = (
        f"3' end stability ('{es.get('last_5_bases', '')}') = {es_val:.2f} kcal/mol "
        f"(threshold: ≤ {END_STABILITY_MAX} kcal/mol). "
        f"Source: Primer3Plus PRIMER_MAX_END_STABILITY = 9.0 kcal/mol."
    )

    # ── 9. Primer size (0.04 V3 / 0.02 V4) [P3P Penalties] ───────
    primer_len = forward.get("length", FORWARD_OPTIMAL_LENGTH)
    size_diff  = abs(primer_len - FORWARD_OPTIMAL_LENGTH)
    scores["primer_size"] = round(max(0, 100 - size_diff * 10), 1)
    explanations["primer_size"] = (
        f"Primer length = {primer_len} nt (optimal: {FORWARD_OPTIMAL_LENGTH} nt). "
        f"Δ = {size_diff} nt. Source: Primer3Plus Penalties — Size Lt=Gt=1.0 per nt."
    )

    # ── 10. Amplicon size (0.04 V3 / 0.02 V4) ───────────────────
    amp = forward.get("amplicon_size", 0)
    if AMPLICON_MIN_QPCR <= amp <= AMPLICON_MAX_QPCR:
        amp_score = max(70, 100 - abs(amp - AMPLICON_IDEAL) * 0.5)
    else:
        amp_score = max(0, 30 - abs(amp - AMPLICON_IDEAL) * 0.3)
    scores["amplicon_size"] = round(amp_score, 1)
    explanations["amplicon_size"] = (
        f"Predicted amplicon = {amp} bp "
        f"(recommended: {AMPLICON_MIN_QPCR}–{AMPLICON_MAX_QPCR} bp, target: {AMPLICON_IDEAL} bp). "
        f"Source: IDT qPCR primer design guidelines."
    )

    # ── 11. Tm pair match (0.05 V3 / 0.03 V4) ───────────────────
    tm_rev       = reverse["tm"]
    tm_pair_diff = abs(tm - tm_rev)
    if tm_pair_diff <= 1.0:               pair_score = 100
    elif tm_pair_diff <= TM_PAIR_DIFF_MAX: pair_score = 80
    else:                                  pair_score = max(0, 80 - (tm_pair_diff - TM_PAIR_DIFF_MAX) * 20)
    scores["tm_pair_match"] = round(pair_score, 1)
    explanations["tm_pair_match"] = (
        f"Tm difference: forward {tm}°C vs reverse {tm_rev}°C = {tm_pair_diff:.1f}°C "
        f"(recommended: < {TM_PAIR_DIFF_MAX}°C). Source: PrimerAST 2024."
    )

    # ── 12. GC clamp at 3' end (0.03 V3 / 0.02 V4) [IDT] ────────
    last3    = forward["sequence"][-3:].upper()
    gc_last3 = sum(1 for b in last3 if b in "GC")
    if gc_last3 == 2:    gc_clamp_score = 100
    elif gc_last3 >= 3:  gc_clamp_score = 80
    elif gc_last3 == 1:  gc_clamp_score = 60
    else:                gc_clamp_score = 0
    scores["gc_clamp"] = gc_clamp_score
    explanations["gc_clamp"] = (
        f"GC clamp at 3' end: {gc_last3} G/C in last 3 nt ('{last3}'). "
        f"Optimal = exactly 2 G/C (score 100); 1 G/C = relaxed fallback (score 60). "
        f"Source: IDT PrimerQuest GC_clamp_code."
    )

    # ── V4-only criteria ─────────────────────────────────────────
    weights = SCORING_WEIGHTS_V4 if use_v4 else SCORING_WEIGHTS_V3

    if use_v4:
        # ── 13. Bound fraction — binding region (0.05) [SL04] ────
        specific_region = forward.get("specific_sequence") or forward["sequence"][-forward.get("specific_length", len(forward["sequence"])):]
        bf_binding = calculate_bound_fraction_binding(specific_region, params)
        bf_binding_result = score_bound_fraction(bf_binding)
        scores["bound_fraction_binding"] = bf_binding_result["score"]
        explanations["bound_fraction_binding"] = (
            f"Specific region bound fraction = {bf_binding:.1f}% at Ta=60°C "
            f"(optimal ≥ 97%, acceptable ≥ 90%). "
            f"Round 1: specific region ({forward.get('specific_length', '?')} nt) binds cDNA — "
            f"determines RT initiation. "
            f"Formula: [SL04] SantaLucia & Hicks 2004 (dH/dS from primer3-py heterodimer)."
        )

        # ── 14. Bound fraction — full primer (0.03) [SL04] ───────
        bf_full = calculate_bound_fraction_full(forward["sequence"], params)
        bf_full_result = score_bound_fraction(bf_full)
        scores["bound_fraction_full"] = bf_full_result["score"]
        explanations["bound_fraction_full"] = (
            f"Full primer bound fraction = {bf_full:.1f}% at Ta=60°C "
            f"(optimal ≥ 97%, acceptable ≥ 90%). "
            f"Round 2: full primer ({forward.get('length', '?')} nt) binds amplicon. "
            f"Formula: [SL04] SantaLucia & Hicks 2004."
        )

        # ── 15. Family discrimination (0.05) [Chen05] ────────────
        worst_risk = _extract_worst_family_risk(cross_reactivity)
        fam_score = FAMILY_DISCRIMINATION_RISK_SCORE.get(worst_risk, 50)
        scores["family_discrimination"] = fam_score
        family_name = cross_reactivity.get("family") if cross_reactivity else None
        overhang_used = cross_reactivity.get("overhang_used", 6) if cross_reactivity else 6
        explanations["family_discrimination"] = (
            f"Family cross-reactivity risk: {worst_risk} "
            f"(family: {family_name or 'unknown'}, overhang: {overhang_used} nt). "
            f"Score 100=SAFE/no data, 70=LOW, 30=HIGH, 0=IDENTICAL. "
            f"Source: Chen et al. 2005 Fig.7; miFam.dat."
        )

    # ── Total weighted score ──────────────────────────────────────
    total = round(sum(scores[k] * weights[k] for k in weights if k in scores), 1)

    return {
        "total_score": total,
        "grade": _grade(total),
        "scores": scores,
        "weights": weights,
        "explanations": explanations,
        "scoring_version": "V4" if use_v4 else "V3",
        "pass_all_structure_checks": sc.get("overall_pass", False),
        "has_critical_flag": sc.get("has_critical_flag", False),
    }


def _extract_worst_family_risk(cross_reactivity: dict | None) -> str:
    """Return the worst risk label from cross_reactivity result dict."""
    if not cross_reactivity:
        return "no_family_data"
    hits = cross_reactivity.get("cross_reactivity", [])
    if not hits:
        return "no_family_data"
    rank = {"IDENTICAL": 0, "HIGH": 1, "LOW": 2, "SAFE": 3}
    worst = min(hits, key=lambda h: rank.get(h.get("risk", "SAFE"), 3))
    return worst.get("risk", "no_family_data")


def _grade(total: float) -> str:
    if total >= 80:   return "Excellent"
    elif total >= 65: return "Good"
    elif total >= 50: return "Acceptable"
    else:             return "Poor"
