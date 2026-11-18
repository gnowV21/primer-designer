# ================================================================
# tiered_scoring.py — tiered, specificity-first ranking of forward primer candidates
# (algorithm 4.0.0, docs/SPEC_scoring_tiered_4.0.0.md).
#
# Pure functions only: metric → level 1–5, tier totals, detailed score, ranking key,
# specificity elimination. The metrics themselves (BLAST, assay ΔCq, Tm, structure)
# are computed elsewhere and passed in. Thresholds: constants.py, section
# "TIERED SCORING (4.0.0)". Order of the ranking key (SPEC QD 1):
#   specificity → structure veto → PCR → flexible → detailed score → |Tm − Ta| → sequence
# ================================================================

from .constants import (
    TIERED_S1_BY_RISK, TIERED_S2_DCQ, TIERED_S3_MARGIN_C,
    TIERED_P1_TM_PAIR_C, TIERED_P2_TM_TA_C,
    TIERED_F3_LENGTH, TIERED_F4_BINDING_TM_DEV_C,
    TIERED_F5_HAIRPIN_TM_C, TIERED_F5_DIMER_DG, TIERED_F5_END_DIMER_TM_C,
    TIERED_DETAIL_WEIGHTS, TIERED_DETAIL_ANCHORS,
    TIERED_F4_FLOOR_C, TIERED_DETAIL_TM_BINDING_FLOOR, TIERED_GRADE_A_MIN,
    TM_BINDING_TARGET,
)
from . import constants as _K   # flags read at call time (TIERED_F4_FLOOR, TIERED_GRADE_BY_TIERS)


def _floor(f4_floor: bool | None) -> bool:
    """QD 29 flag: explicit argument, else constants.TIERED_F4_FLOOR."""
    return _K.TIERED_F4_FLOOR if f4_floor is None else bool(f4_floor)


# ── generic level helpers ─────────────────────────────────────────

def level_at_least(x: float, edges: tuple) -> int:
    """Higher is better: x ≥ edges[0] → 5, ≥ edges[1] → 4, ≥ edges[2] → 3, ≥ edges[3] → 2, else 1."""
    for lvl, e in zip((5, 4, 3, 2), edges):
        if x >= e:
            return lvl
    return 1


def level_at_most(x: float, edges: tuple) -> int:
    """Lower is better, edges inclusive: x ≤ edges[0] → 5 … x ≤ edges[3] → 2, else 1."""
    for lvl, e in zip((5, 4, 3, 2), edges):
        if x <= e:
            return lvl
    return 1


def level_below(x: float, edges: tuple) -> int:
    """Lower is better, edges exclusive: x < edges[0] → 5 … x < edges[3] → 2, else 1."""
    for lvl, e in zip((5, 4, 3, 2), edges):
        if x < e:
            return lvl
    return 1


def level_above(x: float, edges: tuple) -> int:
    """Higher is better, edges exclusive (for negative ΔG): x > edges[0] → 5 … else 1."""
    for lvl, e in zip((5, 4, 3, 2), edges):
        if x > e:
            return lvl
    return 1


def piecewise(x: float, anchors: tuple) -> float:
    """Linear interpolation through (value, score) anchors sorted by value; clamped at
    the ends. Works for increasing or decreasing scores."""
    pts = sorted(anchors)
    if x <= pts[0][0]:
        return float(pts[0][1])
    if x >= pts[-1][0]:
        return float(pts[-1][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return float(y0 + (y1 - y0) * (x - x0) / (x1 - x0))
    return float(pts[-1][1])   # unreachable


# ── tier 1: specificity ───────────────────────────────────────────

def s1_blast(overall_risk: str | None, n_medium_hits: int = 0) -> int | None:
    """BLAST overall_risk → 1–5; None when BLAST did not run (blast_unavailable)."""
    if overall_risk is None:
        return None
    if overall_risk == "MEDIUM":
        return TIERED_S1_BY_RISK["MEDIUM_1" if n_medium_hits <= 1 else "MEDIUM_2+"]
    return TIERED_S1_BY_RISK[overall_risk]


def s2_assay_dcq(min_delta_cq: float | None) -> int:
    """min ΔCq_assay over same-species miRNAs; None = nothing below the 10-Cq floor."""
    return 5 if min_delta_cq is None else level_at_least(min_delta_cq, TIERED_S2_DCQ)


def s3_tm_margin(margin_c: float | None) -> int:
    """Tm_on − max Tm_off over RT-captured off-targets; None = no such off-target."""
    return 5 if margin_c is None else level_at_least(margin_c, TIERED_S3_MARGIN_C)


# ── tier 2: PCR ───────────────────────────────────────────────────

def p1_tm_pair(tm_forward: float, tm_reverse: float) -> int:
    return level_at_most(abs(tm_forward - tm_reverse), TIERED_P1_TM_PAIR_C)


def p2_tm_vs_ta(tm_forward: float, ta: float) -> int:
    return level_at_most(abs(tm_forward - ta), TIERED_P2_TM_TA_C)


# ── tier 3: flexible ──────────────────────────────────────────────

def f1_gc(gc_pct: float) -> int:
    """40–60 → 5; 35–<40 or >60–65 → 4; 30–<35 or >65–70 → 3; 25–<30 or >70–75 → 2."""
    if 40 <= gc_pct <= 60:
        return 5
    dev = 40 - gc_pct if gc_pct < 40 else gc_pct - 60
    for lvl, edge in ((4, 5), (3, 10), (2, 15)):
        if dev <= edge:
            return lvl
    return 1


def f2_gc_clamp(sequence: str) -> int:
    """G/C in the last 5 nt of the 3' end: 2 → 5; 3 with the last 3 not all G/C → 4;
    1 → 3; last 3 all G/C or 4 G/C → 2; 0 or 5 → 1."""
    s = sequence.upper()
    n5 = sum(b in "GC" for b in s[-5:])
    last3_all = all(b in "GC" for b in s[-3:])
    if n5 in (0, 5):
        return 1
    if n5 == 4 or last3_all:
        return 2
    if n5 == 2:
        return 5
    if n5 == 3:
        return 4
    return 3   # n5 == 1


def f3_specific_length(length: int) -> int:
    return TIERED_F3_LENGTH.get(int(length), 1)


def f4_binding_tm(tm_binding: float) -> int:
    """Two-sided F4 (4.0.0 as approved in Giai đoạn 1): |Tm_binding − 45 °C|."""
    return level_at_most(abs(tm_binding - TM_BINDING_TARGET), TIERED_F4_BINDING_TM_DEV_C)


def f4_binding_tm_floor(tm_binding: float) -> int:
    """One-sided F4 (QD 29): ≥ 45 → 5, 43–<45 → 4, 41–<43 → 3, 39–<41 → 2, < 39 → 1."""
    return level_at_least(tm_binding, TIERED_F4_FLOOR_C)


def f5_structure(hairpin_tm: float | None, dimer_dg: float | None,
                 end_dimer_tm: float | None) -> dict:
    """Three sub-indices; F5 = their minimum; any sub-index of 1 → structure_veto.
    A missing value (structure not formed / not computed) counts as 5."""
    subs = {
        "hairpin_tm": 5 if hairpin_tm is None else level_below(hairpin_tm, TIERED_F5_HAIRPIN_TM_C),
        "dimer_dg": 5 if dimer_dg is None else level_above(dimer_dg, TIERED_F5_DIMER_DG),
        "end_dimer_tm": 5 if end_dimer_tm is None else level_below(end_dimer_tm, TIERED_F5_END_DIMER_TM_C),
    }
    return {"score": min(subs.values()), "sub_scores": subs, "veto": 1 in subs.values()}


# ── whole candidate ───────────────────────────────────────────────

def _detail_weights_raw(f4_floor: bool | None = None) -> dict:
    w = dict(TIERED_DETAIL_WEIGHTS)
    if _floor(f4_floor):
        w.pop("primer_size")          # QD 29: length is report-only
    return w


def detailed_score(m: dict, f4_floor: bool | None = None) -> float:
    """0–100 tie-break (SPEC §3.4). m carries the raw metrics and the V4 sub-scores
    tm_accuracy, tm_binding_accuracy, gc_content, gc_clamp, primer_size, amplicon_size."""
    parts = detailed_parts(m, f4_floor)
    w = _detail_weights_raw(f4_floor)
    return round(sum(parts[k] * w[k] for k in w) / sum(w.values()), 1)


def detailed_weights(f4_floor: bool | None = None) -> dict:
    """Effective weights of the detailed score (raw weights / their sum)."""
    w = _detail_weights_raw(f4_floor)
    total = sum(w.values())
    return {k: round(v / total, 4) for k, v in w.items()}


def detailed_parts(m: dict, f4_floor: bool | None = None) -> dict:
    """The 0–100 sub-scores of the detailed score (see detailed_score). With the QD 29
    floor: tm_binding_accuracy is one-sided and primer_size is dropped."""
    a = TIERED_DETAIL_ANCHORS
    v4 = m["v4_scores"]
    dcq = 10.0 if m.get("min_delta_cq") is None else min(m["min_delta_cq"], 10.0)
    margin = 20.0 if m.get("tm_margin") is None else min(m["tm_margin"], 20.0)
    struct = [
        100.0 if m.get("hairpin_tm") is None else piecewise(m["hairpin_tm"], a["hairpin_tm"]),
        100.0 if m.get("dimer_dg") is None else piecewise(m["dimer_dg"], a["dimer_dg"]),
        100.0 if m.get("end_dimer_tm") is None else piecewise(m["end_dimer_tm"], a["end_dimer_tm"]),
    ]
    parts = {
        "min_delta_cq": piecewise(dcq, a["min_delta_cq"]),
        "tm_margin": piecewise(margin, a["tm_margin"]),
        "tm_accuracy": v4["tm_accuracy"],
        "tm_binding_accuracy": v4["tm_binding_accuracy"],
        "gc_content": v4["gc_content"],
        "gc_clamp": v4["gc_clamp"],
        "primer_size": v4["primer_size"],
        "structure": sum(struct) / 3.0,
        "amplicon_size": v4["amplicon_size"],
    }
    if _floor(f4_floor):
        parts["tm_binding_accuracy"] = piecewise(m["tm_binding"], TIERED_DETAIL_TM_BINDING_FLOOR)
        parts.pop("primer_size")
    return {k: float(v) for k, v in parts.items()}   # unrounded: the tie-break uses them


def blast_s1_inputs(result: dict) -> tuple[str, int, str | None]:
    """(overall_risk, MEDIUM-hit count, worst hit) from a check_offtarget result — the
    inputs of s1_blast. MEDIUM counts classified hits and same-molecule variants."""
    summ = result["summary"]
    n_med = sum(h.get("risk") == "MEDIUM" for h in result["forward_primer_hits"]) + sum(
        v["risk"] == "MEDIUM" for v in result.get("identical_sequence_risk", {}).values())
    worst = next((h.get("subject_id") for h in result["forward_primer_hits"]
                  if h.get("risk") == summ["overall_risk"]), None)
    if worst is None and summ["overall_risk"] != "SAFE":
        worst = next((sid for sid, v in result.get("identical_sequence_risk", {}).items()
                      if v["risk"] == summ["overall_risk"]), None)
    return summ["overall_risk"], n_med, worst


def score(m: dict, f4_floor: bool | None = None) -> dict:
    """All levels, tier totals and the detailed score of one candidate.

    m: sequence, specific_length, tm_full, tm_binding, tm_reverse, ta, gc_percent,
       blast_risk (None if BLAST unavailable), blast_medium_hits, min_delta_cq,
       tm_margin, hairpin_tm, dimer_dg, end_dimer_tm, v4_scores.
    """
    s1 = s1_blast(m.get("blast_risk"), m.get("blast_medium_hits", 0))
    s2 = s2_assay_dcq(m.get("min_delta_cq"))
    s3 = s3_tm_margin(m.get("tm_margin"))
    p1 = p1_tm_pair(m["tm_full"], m["tm_reverse"])
    p2 = p2_tm_vs_ta(m["tm_full"], m["ta"])
    f5 = f5_structure(m.get("hairpin_tm"), m.get("dimer_dg"), m.get("end_dimer_tm"))
    floor = _floor(f4_floor)
    f3 = f3_specific_length(m["specific_length"])
    f = {"gc": f1_gc(m["gc_percent"]), "gc_clamp": f2_gc_clamp(m["sequence"])}
    if not floor:
        f["specific_length"] = f3
    f["binding_tm"] = (f4_binding_tm_floor if floor else f4_binding_tm)(m["tm_binding"])
    f["structure"] = f5["score"]
    s_parts = [x for x in (s1, s2, s3) if x is not None]
    # P1 is report-only (constants.py, Tier 2): the fixed universal reverse primer makes it
    # a function of Tm_forward that opposes P2. PCR tier = P2.
    return {
        "specificity": {"blast": s1, "assay_dcq": s2, "tm_margin": s3,
                        "total": sum(s_parts), "max": 5 * len(s_parts)},
        "pcr": {"tm_vs_ta": p2, "total": p2, "max": 5,
                "tm_pair_report_only": p1},
        "flexible": {**f, "total": sum(f.values()), "max": 5 * len(f),
                     "structure_sub_scores": f5["sub_scores"],
                     # QD 29: length (F3) is reported, not scored
                     **({"specific_length_report_only": f3} if floor else {})},
        "structure_veto": f5["veto"],
        # QD 36: binding Tm below the one-sided floor (< 39 °C); ranked as a soft veto
        # when TIERED_BINDING_FLOOR_VETO (and only meaningful with the floor, QD 29).
        "binding_floor_fail": floor and f["binding_tm"] == 1,
        "eliminated": (s1 == 1) or (s2 == 1),
        "detailed_score": detailed_score(m, floor),
    }


def grade_tiers(r: dict, specificity_fallback: bool) -> dict:
    """QD 30: grade of one returned set from its tiers. r = score(m).
    A — passed the elimination with S1 ≥ 4, S2 ≥ 3, S3 ≥ 4 and no structure veto;
    B — passed it with a weakness (S1 2–3, S2 2, S3 ≤ 3, veto), or without BLAST
        (S1 unknown: never A);
    C — specificity_fallback (every candidate failed specificity)."""
    sp = r["specificity"]
    if specificity_fallback:
        return {"grade": "C", "reasons": ["specificity_fallback: every candidate failed "
                                          "specificity (BLAST CRITICAL or ΔCq CO-AMPLIFIED)"]}
    names = {"blast": "S1 BLAST", "assay_dcq": "S2 assay ΔCq", "tm_margin": "S3 Tm margin"}
    reasons = []
    if sp["blast"] is None:
        reasons.append("BLAST unavailable: S1 unknown, grade capped at B")
    for k, lo in TIERED_GRADE_A_MIN.items():
        if sp[k] is not None and sp[k] < lo:
            reasons.append(f"{names[k]} level {sp[k]} (< {lo})")
    if r["structure_veto"]:
        reasons.append("structure veto (a structure sub-index at level 1)")
    if r.get("binding_floor_fail") and _K.TIERED_BINDING_FLOOR_VETO:
        reasons.append("binding Tm below the 39 °C floor (F4 level 1)")
    return {"grade": "B" if reasons else "A", "reasons": reasons}


def rank_key(m: dict, r: dict, v4_compliant_first: bool | None = None,
             binding_floor_veto: bool | None = None) -> tuple:
    """SPEC §3.5: (−S, structure_veto, [binding_floor_fail,] [has_v4_violation,] −P, −F,
    −detailed, |Tm − Ta|, sequence). The soft vetoes and the QD 34 V4-rule step only
    reorder candidates with the same S total, because S comes first (QD 8).
    binding_floor_fail (QD 36) is on with TIERED_BINDING_FLOOR_VETO; has_v4_violation =
    bool(m["v4_violation"]) (the candidate's v4_rule_violations), on with
    TIERED_V4_COMPLIANT_FIRST."""
    on = _K.TIERED_V4_COMPLIANT_FIRST if v4_compliant_first is None else v4_compliant_first
    fv = _K.TIERED_BINDING_FLOOR_VETO if binding_floor_veto is None else binding_floor_veto
    return (-r["specificity"]["total"], r["structure_veto"],
            bool(r.get("binding_floor_fail")) if fv else False,
            bool(m.get("v4_violation")) if on else False,
            -r["pcr"]["total"], -r["flexible"]["total"], -r["detailed_score"],
            abs(m["tm_full"] - m["ta"]), m["sequence"])


def rank(candidates: list[tuple[dict, dict]], v4_compliant_first: bool | None = None,
         binding_floor_veto: bool | None = None) -> dict:
    """candidates: [(metrics, score(metrics))]. Drops eliminated candidates (SPEC QD 4);
    if all are eliminated keeps all and flags specificity_fallback. Returns the
    ranked list and the flags; top-N selection (select_diverse_top) is the caller's."""
    kept = [c for c in candidates if not c[1]["eliminated"]]
    fallback = not kept and bool(candidates)
    pool = candidates if fallback else kept
    ranked = sorted(pool, key=lambda c: rank_key(*c, v4_compliant_first, binding_floor_veto))
    return {"ranked": ranked, "specificity_fallback": fallback,
            "eliminated": len(candidates) - len(kept)}
