# ================================================================
# scoring.py — Module 6: 12-criterion weighted scoring (v2.8.3 / V3)
# Total score 0–100. Grade: Excellent(≥80), Good(65–79), Acceptable(50–64), Poor(<50).
# Weights: SCORING_WEIGHTS_V3 (Section 27/I of spec)
# ================================================================

from .constants import (
    SCORING_WEIGHTS_V3, TM_FORWARD_TARGET, TM_FORWARD_TOLERANCE,
    TM_BINDING_TARGET, TM_BINDING_TOLERANCE,
    TM_PAIR_DIFF_MAX, GC_MIN, GC_MAX, GC_OPTIMAL,
    MFE_STEMLOOP_MIN, MFE_STEMLOOP_MAX, MFE_STEMLOOP_OPTIMAL,
    MFE_STEMLOOP_MIN_RNA, MFE_STEMLOOP_MAX_RNA, MFE_STEMLOOP_OPTIMAL_RNA,
    HAIRPIN_DG_MAX_INTERNAL, SELF_DIMER_DG_3PRIME_MAX, END_STABILITY_MAX,
    AMPLICON_MIN_QPCR, AMPLICON_MAX_QPCR, AMPLICON_IDEAL,
    FORWARD_OPTIMAL_LENGTH, GC_SKEW_WARNING_THRESHOLD,
)
from .sequence_utils import calculate_gc_skew


def score_candidate(forward: dict, stemloop: dict, reverse: dict, params: dict) -> dict:
    """
    Score a complete primer set across 11 weighted criteria (SCORING_WEIGHTS_V3).
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

    # ── 3. GC content (0.09) ──────────────────────────────────────
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

    # ── 4. GC-skew (0.03) [PAST24] ────────────────────────────────
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
        # Continuous with out-of-range penalties — no floor discontinuity.
        if mfe <= _mfe_opt:
            frac = (mfe - mfe_min) / (_mfe_opt - mfe_min) if (_mfe_opt - mfe_min) > 0 else 1.0
        else:
            frac = (mfe_max - mfe) / (mfe_max - _mfe_opt) if (mfe_max - _mfe_opt) > 0 else 1.0
        mfe_score = 60.0 + 40.0 * max(0.0, frac)
    elif mfe < mfe_min:
        # Too stable: penalise proportionally (60 → 0 as mfe moves below mfe_min)
        mfe_score = max(0, 60 + (mfe - mfe_min) * 5)
    else:
        # Too weak: penalise proportionally (60 → 0 as mfe rises above mfe_max).
        # v2.8 fix: was (mfe_max - mfe) — negative when mfe > mfe_max → score inflated
        mfe_score = max(0, 60 - (mfe - mfe_max) * 5)
    scores["mfe_stemloop"] = round(mfe_score, 1)
    explanations["mfe_stemloop"] = (
        f"Stem-loop MFE = {mfe:.2f} kcal/mol (valid: {mfe_min} to {mfe_max} kcal/mol, "
        f"target: {_mfe_opt} kcal/mol). "
        f"Sweet spot balances RT efficiency vs PCR denaturability. "
        f"Method: {mfe_method}. "
        f"Source: Report 2 HG Lab, Chen et al. 2005."
    )

    # ── 6. Hairpin penalty (0.10) ─────────────────────────────────
    hp = sc.get("hairpin", {})
    hp_dg  = hp.get("dg", 0.0)
    sev    = hp.get("severity", "safe")
    hp_map = {"safe": 100, "acceptable": 80, "warning": 40, "critical": 0}
    scores["hairpin_penalty"] = hp_map.get(sev, 50)
    explanations["hairpin_penalty"] = (
        f"Hairpin ΔG = {hp_dg:.2f} kcal/mol (threshold: > {HAIRPIN_DG_MAX_INTERNAL} kcal/mol). "
        f"Severity: {sev}. Primer3Plus thermodynamic alignment enabled."
    )

    # ── 7. Dimer penalty (0.10) ───────────────────────────────────
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

    # ── 8. 3' End stability (0.10) [P3P] ──────────────────────────
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

    # ── 9. Primer size (0.04) [P3P Penalties] ─────────────────────
    primer_len = forward.get("length", FORWARD_OPTIMAL_LENGTH)
    size_diff  = abs(primer_len - FORWARD_OPTIMAL_LENGTH)
    scores["primer_size"] = round(max(0, 100 - size_diff * 10), 1)
    explanations["primer_size"] = (
        f"Primer length = {primer_len} nt (optimal: {FORWARD_OPTIMAL_LENGTH} nt). "
        f"Δ = {size_diff} nt. Source: Primer3Plus Penalties — Size Lt=Gt=1.0 per nt."
    )

    # ── 10. Amplicon size (0.04) ──────────────────────────────────
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

    # ── 11. Tm pair match (0.05) ──────────────────────────────────
    tm_rev      = reverse["tm"]
    tm_pair_diff = abs(tm - tm_rev)
    if tm_pair_diff <= 1.0:          pair_score = 100
    elif tm_pair_diff <= TM_PAIR_DIFF_MAX: pair_score = 80
    else:                            pair_score = max(0, 80 - (tm_pair_diff - TM_PAIR_DIFF_MAX) * 20)
    scores["tm_pair_match"] = round(pair_score, 1)
    explanations["tm_pair_match"] = (
        f"Tm difference: forward {tm}°C vs reverse {tm_rev}°C = {tm_pair_diff:.1f}°C "
        f"(recommended: < {TM_PAIR_DIFF_MAX}°C). Source: PrimerAST 2024."
    )

    # ── 12. GC clamp at 3' end (0.03) [IDT PrimerQuest] ──────────
    last3    = forward["sequence"][-3:].upper()
    gc_last3 = sum(1 for b in last3 if b in "GC")
    if gc_last3 == 2:    gc_clamp_score = 100   # optimal anchor
    elif gc_last3 >= 3:  gc_clamp_score = 80    # over-stabilised — minor penalty
    elif gc_last3 == 1:  gc_clamp_score = 60    # relaxed fallback — suboptimal
    else:                gc_clamp_score = 0     # no anchor — shouldn't reach scoring
    scores["gc_clamp"] = gc_clamp_score
    explanations["gc_clamp"] = (
        f"GC clamp at 3' end: {gc_last3} G/C in last 3 nt ('{last3}'). "
        f"Optimal = exactly 2 G/C (score 100); 1 G/C = relaxed fallback (score 60). "
        f"Source: IDT PrimerQuest GC_clamp_code."
    )

    # ── Total weighted score ───────────────────────────────────────
    total = round(sum(scores[k] * SCORING_WEIGHTS_V3[k] for k in SCORING_WEIGHTS_V3), 1)

    return {
        "total_score": total,
        "grade": _grade(total),
        "scores": scores,
        "weights": SCORING_WEIGHTS_V3,
        "explanations": explanations,
        "pass_all_structure_checks": sc.get("overall_pass", False),
        "has_critical_flag": sc.get("has_critical_flag", False),
    }


def _grade(total: float) -> str:
    if total >= 80:  return "Excellent"
    elif total >= 65: return "Good"
    elif total >= 50: return "Acceptable"
    else:             return "Poor"
