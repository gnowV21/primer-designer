# ================================================================
# scoring.py — Module 6: weighted scoring
# V3 (12 criteria, SCORING_WEIGHTS_V3) — Phase 2, kept as reference.
# V4 (15 criteria, SCORING_WEIGHTS_V4) — Phase 3 default.
# Total score 0–100. Grade: Excellent(≥80), Good(65–79), Acceptable(50–64), Poor(<50).
# ================================================================

from .constants import (
    SCORING_WEIGHTS_V3, SCORING_WEIGHTS_V4, UNSCORED_CRITERIA_V4,
    COMBINED_RISK_SCORE,
    TM_FORWARD_TARGET, TM_FORWARD_TOLERANCE,
    TM_BINDING_TARGET, TM_BINDING_TOLERANCE,
    TM_PAIR_DIFF_MAX, GC_MIN, GC_MAX, GC_OPTIMAL,
    HAIRPIN_DG_MAX_INTERNAL, SELF_DIMER_DG_3PRIME_MAX, END_STABILITY_MAX,
    AMPLICON_MIN_QPCR, AMPLICON_MAX_QPCR, AMPLICON_IDEAL,
    FORWARD_OPTIMAL_LENGTH, GC_SKEW_WARNING_THRESHOLD,
    GC_CLAMP_SCORE_OPTIMAL, GC_CLAMP_SCORE_1GC_CONSERVATIVE,
    GC_CLAMP_SCORE_WEAK, GC_CLAMP_SCORE_TRIPLE_C, GC_CLAMP_1GC_AS_OPTIMAL,
    DIMER_FULL_DG_CRITICAL,
    PRIMER_SIZE_MODE, FORWARD_SPECIFIC_LEN_REF,
)
from .sequence_utils import calculate_gc_skew
from .stemloop_rt import mfe_thresholds
from .bound_fraction import (
    annealing_temp_c,
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
    overhang_collision: dict | None = None,
) -> dict:
    """
    Score a complete primer set.
    use_v4=True (default): 15 criteria (SCORING_WEIGHTS_V4, Phase 3).
    use_v4=False: 12 criteria (SCORING_WEIGHTS_V3, Phase 2 compat).
    cross_reactivity: seed-family output (kept for the biological-context panel; NOT scored).
    overhang_collision: primer-axis output from check_overhang_collision — drives the
        family_discrimination criterion (RT 3' overhang x forward 5' prefix). [Week2 C5]
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

    # ── 4. GC-skew (0.02 V3 / 0.02 V4) [PAST24] ─────────────────
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
    mfe        = stemloop.get("mfe")
    mfe_method = stemloop.get("mfe_method", "")
    _t_min, _t_max, _mfe_opt = mfe_thresholds(mfe_method)
    mfe_min    = float(params.get("mfeMin", _t_min))
    mfe_max    = float(params.get("mfeMax", _t_max))
    if mfe is None:
        # No folding engine: leave the criterion out (total is renormalised) — SCI-03.
        explanations["mfe_stemloop"] = (
            "Stem-loop MFE could not be computed (no folding engine available) — "
            "excluded from the total score."
        )
    else:
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
            f"The 44-nt body is fixed, so this barely differs between candidates. "
            f"Method: {mfe_method}. "
            f"Source: Chen et al. 2005; window derived in constants.py (not wet-lab calibrated)."
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

    # Full-structure check [Kang17]: ΔG_total < -9 kcal/mol → inhibits qPCR
    sd_full       = sc.get("self_dimer", {}).get("dg_overall", 0.0)
    hd_full       = sc.get("hetero_dimer", {}).get("dg_overall", 0.0)
    worst_full    = min(sd_full, hd_full)
    full_critical = worst_full < DIMER_FULL_DG_CRITICAL

    # Breakpoints derived from SELF_DIMER_DG_3PRIME_MAX so a single constant change
    # keeps scoring tiers and the explanation text in sync.
    _dt = SELF_DIMER_DG_3PRIME_MAX  # -5.0 kcal/mol
    if critical or full_critical:      dimer_score = 0
    elif worst > _dt + 1.0:           dimer_score = 100   # > -4.0: well clear of threshold
    elif worst > _dt:                 dimer_score = 75    # > -5.0: approaching threshold
    elif worst > _dt - 1.0:           dimer_score = 40    # > -6.0: exceeded threshold
    else:                              dimer_score = 0
    scores["dimer_penalty"] = dimer_score
    explanations["dimer_penalty"] = (
        f"3'-end dimer ΔG = {worst:.2f} kcal/mol (threshold: > {SELF_DIMER_DG_3PRIME_MAX} kcal/mol). "
        f"Full-structure dimer ΔG = {worst_full:.2f} kcal/mol (threshold: > {DIMER_FULL_DG_CRITICAL} kcal/mol). "
        + ("CRITICAL: polymerase can extend 3'-end dimer. " if critical else "")
        + ("CRITICAL: full-structure ΔG below -9 kcal/mol — qPCR inhibition expected [Kang17]. " if full_critical else "")
        + "Sources: IDT OligoAnalyzer, Premier Biosoft qPCR guidelines; Kang 2017 (DOI 10.1261/rna.061150.117)."
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

    # ── 9. Primer size (0.04 V3 / 0.02 V4) ──────────────────────────
    # PRIMER_SIZE_MODE="specific" [Busk14 I6]: score by binding-region length only.
    # The 5' tail is added solely to reach target Tm and should not penalize the primer.
    # Longer specific region → higher sequence identity requirement → better discrimination.
    # PRIMER_SIZE_MODE="full" (legacy): penalize by deviation from FORWARD_OPTIMAL_LENGTH.
    if PRIMER_SIZE_MODE == "specific":
        spec_len = forward.get("specific_length", forward.get("length", FORWARD_SPECIFIC_LEN_REF))
        primer_size_score = round(min(100.0, (spec_len ** 2 / FORWARD_SPECIFIC_LEN_REF ** 2) * 100), 1)
        explanations["primer_size"] = (
            f"Specific region = {spec_len} nt (reference max: {FORWARD_SPECIFIC_LEN_REF} nt). "
            f"Score = min(100, (len/ref)²×100) = {primer_size_score}. "
            f"Longer specific region → more discriminating. 5' tail excluded — tail adjusts Tm only. "
            f"Source: Busk 2014 (DOI 10.1186/1471-2105-15-29), miRNA-specific scoring."
        )
    else:
        primer_len = forward.get("length", FORWARD_OPTIMAL_LENGTH)
        size_diff  = abs(primer_len - FORWARD_OPTIMAL_LENGTH)
        primer_size_score = round(max(0.0, 100 - size_diff * 10), 1)
        explanations["primer_size"] = (
            f"Primer length = {primer_len} nt (optimal: {FORWARD_OPTIMAL_LENGTH} nt). "
            f"Δ = {size_diff} nt. Source: Primer3Plus Penalties — Size Lt=Gt=1.0 per nt."
        )
    scores["primer_size"] = primer_size_score

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

    # ── 11. Tm pair match (0.05 V3 / 0.01 V4) ───────────────────
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

    # ── 12. GC clamp at 3' end (0.03 V3 / 0.04 V4) [Busk14+IDT] ───
    # Two-tier logic (PROMPT 1):
    # (a) LOCKED multi-source: CCC→25, 3 G/C→50, 0 G/C→50, 2 G/C→100.
    # (b) PENDING single-source: 1 G/C → 75 (conservative, GC_CLAMP_1GC_AS_OPTIMAL=False)
    #     or 100 (Busk14-style, flag=True) — enable after calibrate_weights.py confirms.
    # Trade-off: IDT prefers ≥2 G/C for PCR efficiency (anchor); Busk14 (miRNA-specific)
    # accepts 1 G/C as optimal for mismatch discrimination. Default: conservative.
    last3    = forward["sequence"][-3:].upper()
    gc_last3 = sum(1 for b in last3 if b in "GC")
    if last3 == "CCC":       gc_clamp_score = GC_CLAMP_SCORE_TRIPLE_C         # 25 — (a)
    elif gc_last3 == 3:      gc_clamp_score = GC_CLAMP_SCORE_WEAK             # 50 — (a)
    elif gc_last3 == 0:      gc_clamp_score = GC_CLAMP_SCORE_WEAK             # 50 — (a)
    elif gc_last3 == 2:      gc_clamp_score = GC_CLAMP_SCORE_OPTIMAL          # 100 — (a)
    else:                    gc_clamp_score = (GC_CLAMP_SCORE_OPTIMAL         # 100 — (b) Busk14
                                               if GC_CLAMP_1GC_AS_OPTIMAL
                                               else GC_CLAMP_SCORE_1GC_CONSERVATIVE)  # 75 — (b) default
    scores["gc_clamp"] = gc_clamp_score
    explanations["gc_clamp"] = (
        f"3'-end composition: {gc_last3} G/C in last 3 nt ('{last3}') → score {gc_clamp_score}. "
        f"Rule: 2 G/C = optimal anchor+specificity [Busk14+IDT]; "
        f"1 G/C = good specificity, weaker anchor "
        f"[trade-off: IDT prefers G/C for PCR efficiency; Busk 2014 (miRNA-specific, DOI 10.1186/1471-2105-15-29) "
        f"accepts 1 G/C as optimal — single-source heuristic, pending calibration; default conservative]; "
        f"0 or 3 G/C = suboptimal [Busk14+IDT]; CCC at 3' = severe penalty [Busk14, multi-source]."
    )

    # ── V4-only criteria ─────────────────────────────────────────
    weights = SCORING_WEIGHTS_V4 if use_v4 else SCORING_WEIGHTS_V3

    if use_v4:
        # ── 13. Bound fraction — binding region (0.05) [SL04] ────
        specific_region = forward.get("specific_region") or forward["sequence"][-forward.get("specific_length", len(forward["sequence"])):]
        # Informational only (UNSCORED_CRITERIA_V4, audit SCI-02): no score key,
        # so it never enters the total or the score breakdown.
        bf_binding = calculate_bound_fraction_binding(specific_region, params)
        scores["bound_fraction_binding_pct"] = bf_binding
        explanations["bound_fraction_binding"] = (
            f"Cycle-1 occupancy = {bf_binding:.1f}% of the specific region "
            f"({forward.get('specific_length', '?')} nt) bound to first-strand cDNA at "
            f"Ta = {annealing_temp_c(params):g}°C. In cycle 1 only the specific region has a "
            f"template (the 5' tail pairs from cycle 2 on), so low values are normal. "
            f"Shown for information — not scored (no published threshold). "
            f"Formula: [SL04] SantaLucia & Hicks 2004."
        )

        # ── 14. Bound fraction — full primer (0.03) [SL04] ───────
        bf_full = calculate_bound_fraction_full(forward["sequence"], params)
        bf_full_result = score_bound_fraction(bf_full)
        scores["bound_fraction_full"] = bf_full_result["score"]
        scores["bound_fraction_full_pct"] = bf_full  # raw % for display
        explanations["bound_fraction_full"] = (
            f"Full primer bound fraction = {bf_full:.1f}% at Ta=55°C (Tm−5°C qPCR annealing) "
            f"(optimal ≥ 80%, acceptable ≥ 60%). "
            f"Round 2: full primer ({forward.get('length', '?')} nt) binds amplicon. "
            f"Evaluated at Tm−5°C, not Tm — at Tm all primers are 50% unbound by definition. "
            f"Formula: [SL04] SantaLucia & Hicks 2004."
        )

        # ── 15. Family discrimination — PRIMER-BINDING axis (0.05) [Chen05][Kwok90] ──
        # Scored on the RT 3'-overhang x forward 5'-prefix collision analysis, NOT the seed
        # family (which is the mRNA-targeting axis). [Week2 C5]
        worst_risk = _extract_worst_primer_axis_risk(overhang_collision)
        fam_score = COMBINED_RISK_SCORE.get(worst_risk, 100)
        scores["family_discrimination"] = fam_score
        if worst_risk == "no_index_data":
            explanations["family_discrimination"] = (
                "No overhang index available — this criterion did not contribute discriminating "
                "information (scored 100). Run scripts/build_overhang_index.py to enable it."
            )
        else:
            oc = overhang_collision or {}
            n_crit = oc.get("summary", {}).get("CRITICAL", 0)
            worst_name = next((e.get("mirna") for e in oc.get("collisions", [])
                               if e.get("combined_risk") == "CRITICAL"), None)
            explanations["family_discrimination"] = (
                f"Primer-binding specificity — worst combined risk: {worst_risk}. "
                f"Axis: RT 3' overhang ({oc.get('overhang_len', 6)} nt) x forward 5' prefix "
                f"({oc.get('forward_specific_len', '?')} nt). {n_crit} CRITICAL collider(s)"
                + (f"; worst = {worst_name}" if worst_name else "") + ". "
                "Score 100=SAFE, 70=LOW, 0=CRITICAL. Seed-family membership (positions 2-8) is "
                "the mRNA-targeting axis and is NOT used for scoring. Source: Chen 2005; Kwok 1990."
            )

    # ── Total weighted score ──────────────────────────────────────
    # Renormalised over the criteria actually scored: an unscored criterion
    # (UNSCORED_CRITERIA_V4) or one that could not be computed (e.g. MFE with no
    # folding engine, audit SCI-03) is left out instead of being given a fake
    # value. The locked nominal weights keep their relative proportions.
    unscored = UNSCORED_CRITERIA_V4 if use_v4 else frozenset()
    scored = [k for k in weights
              if k not in unscored and isinstance(scores.get(k), (int, float))]
    w_sum = sum(weights[k] for k in scored)
    effective = {k: round(weights[k] / w_sum, 4) for k in scored} if w_sum else {}
    total = round(sum(scores[k] * weights[k] for k in scored) / w_sum, 1) if w_sum else 0.0

    return {
        "total_score": total,
        "grade": _grade(total),
        "scores": scores,
        "weights": effective,
        "weights_nominal": weights,
        "unscored_criteria": sorted(set(weights) - set(scored)),
        "explanations": explanations,
        "scoring_version": "V4" if use_v4 else "V3",
        "pass_all_structure_checks": sc.get("overall_pass", False),
        "has_critical_flag": sc.get("has_critical_flag", False),
    }


def _extract_worst_primer_axis_risk(overhang_collision: dict | None) -> str:
    """Worst combined RT+forward risk from check_overhang_collision (Week2 C5).

    Returns 'no_index_data' when the overhang index is unavailable so the criterion stays
    neutral (100) instead of silently penalising or crediting a design.
    """
    if not overhang_collision:
        return "no_index_data"
    worst = overhang_collision.get("worst_combined_risk", "no_index_data")
    return worst if worst in ("SAFE", "LOW", "CRITICAL") else "no_index_data"


def _grade(total: float) -> str:
    if total >= 80:   return "Excellent"
    elif total >= 65: return "Good"
    elif total >= 50: return "Acceptable"
    else:             return "Poor"
