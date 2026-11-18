# ================================================================
# tiered_pipeline.py — the tiered, specificity-first ranking inside /api/design
# (algorithm 4.0.0, docs/SPEC_scoring_tiered_4.0.0.md §3.5, §4, QD 24–27).
#
# design_pipeline.run() generates the forward candidates (without the GC % / G-C clamp
# pre-filter, QD 15) and their structure checks, then calls rank() here:
#   1. metrics per candidate: assay screen (S2 min ΔCq, S3 Tm margin, per specific
#      length), Tm vs Ta (P2), GC / clamp / length / binding Tm / structure (F1–F5),
#      and the V4 sub-scores the detailed score reuses;
#   2. BLAST (S1) for every candidate S2 does not eliminate — one batched call
#      (check_offtarget_batch), cached per candidate; without BLAST the ranking runs
#      on S2 + S3 and says so (blast_unavailable, QD 24e);
#   3. tiered_scoring.rank (eliminate S1 CRITICAL / S2 CO-AMPLIFIED, fallback when all
#      are), then select_diverse_top.
# The scoring functions themselves are pure (tiered_scoring.py); thresholds live in
# constants.py, section "TIERED SCORING (4.0.0)". The V4 path is design_pipeline's own.
# ================================================================

import json
import os
import time

from . import tiered_scoring as ts
from .constants import (
    CANDIDATES_TOP_N, TM_ANNEALING_TEMP_DEFAULT, TM_BINDING_TARGET,
    OVERHANG_LENGTH_DEFAULT, OVERHANG_LENGTH_MIN, OVERHANG_LENGTH_MAX,
    BLAST_CLASSIFIER_VERSION, SCORING_SYSTEM_DEFAULT, SCORING_SYSTEMS,
    TIERED_DETAIL_WEIGHTS, TIERED_RT_CAPTURE_BELOW, TIERED_DETAIL_TM_BINDING_FLOOR,
)
from .forward_primer import _prefilter, _GC_PREFILTER_REASONS, select_diverse_top
from .hard_filters import apply_hard_filters
from .scoring import score_candidate, _grade
from .structure_check import full_dimer_dg
from .thermodynamics import calculate_tm_nn, _get_p3_params
from .specificity_check import blast_offtarget as bo
from .specificity_check.assay_model import assay_label
from .specificity_check.family_crossreactivity import _resolve_species_prefix
from .specificity_check.overhang_collision import assay_screen

_V4_SUBSCORES = ("tm_accuracy", "tm_binding_accuracy", "gc_content", "gc_clamp",
                 "primer_size", "amplicon_size")

BLAST_UNAVAILABLE_MESSAGE = (
    "BLAST off-target search unavailable ({reason}) — specificity ranking reduced to "
    "S2 + S3 (assay ΔCq model and Tm margin); BLAST hits were not considered.")


def resolve_system(params: dict) -> str:
    """Scoring system of one design: params['scoringSystem'], else the SCORING_SYSTEM
    environment variable, else SCORING_SYSTEM_DEFAULT. Raises ValueError otherwise."""
    s = (params.get("scoringSystem") or os.environ.get("SCORING_SYSTEM")
         or SCORING_SYSTEM_DEFAULT)
    s = str(s).strip().lower()
    if s not in SCORING_SYSTEMS:
        raise ValueError(f"scoringSystem must be one of {', '.join(SCORING_SYSTEMS)} (got {s!r})")
    return s


def v4_rule_violations(candidate: dict, params: dict) -> list[str]:
    """V4 rules this candidate breaks (SPEC QD 25): the GC pre-filter rules
    (gc_out_of_range, gc_clamp_fail, gc_end_window_fail — same params as V4) and the
    three structural hard filters (hard_dimer_full_dg, hard_dimer_3prime_critical,
    hard_hairpin_tm). Empty = V4 would have accepted it. Needs structure_checks."""
    hard, _ = _prefilter(candidate, params)
    out = [r for r in hard if r in _GC_PREFILTER_REASONS]
    out += [r.split(" ", 1)[0] for r in apply_hard_filters(candidate)]
    return out


# ── metrics ──────────────────────────────────────────────────────

def _metrics(c: dict, v4_scores: dict, screen_l: dict, ta: float, tm_rev: float) -> dict:
    sc = c.get("structure_checks") or {}
    ends = [x for x in ((sc.get("self_dimer") or {}).get("end_tm"),
                        (sc.get("hetero_dimer") or {}).get("end_tm")) if x is not None]
    return {
        "sequence": c["sequence"], "specific_length": c["specific_length"],
        "tm_full": c["tm_full"], "tm_binding": c["tm_binding"], "gc_percent": c["gc_percent"],
        "tm_reverse": tm_rev, "ta": ta,
        "hairpin_tm": (sc.get("hairpin") or {}).get("tm"), "dimer_dg": full_dimer_dg(sc)[0],
        "end_dimer_tm": max(ends) if ends else None,
        "min_delta_cq": screen_l["min_delta_cq"], "worst": screen_l["worst"],
        "tm_margin": screen_l["tm_margin"], "tm_margin_worst": screen_l["tm_margin_worst"],
        "tm_on": screen_l.get("tm_on"),
        "blast_risk": None, "blast_medium_hits": 0, "blast_worst": None,
        "v4_violation": bool(c.get("v4_rule_violations")),   # QD 34 rank step
        "v4_scores": {k: v4_scores[k] for k in _V4_SUBSCORES},
        # Cycle-1 occupancy at Ta: informational, never scored or ranked (audit SCI-02).
        "bound_fraction_binding_pct": v4_scores.get("bound_fraction_binding_pct"),
    }


# ── BLAST (S1) ───────────────────────────────────────────────────

def _blast_db_version() -> str | None:
    """Build date of the BLAST DB (part of the cache key), read on every design so a DB
    rebuilt while the server runs gets new keys. None when the metadata is missing or
    unreadable — the cache is then not used, since its entries could belong to
    another DB build."""
    try:
        with open(bo._METADATA, encoding="utf-8") as f:
            return json.load(f).get("build_date") or None
    except (OSError, ValueError):
        return None


def _cache_enabled() -> bool:
    return os.environ.get("BLAST_CACHE_DISABLED", "").strip().lower() not in ("1", "true", "yes")


def cache_context(target_rna: str, species: str | None, rt_seq: str, p3: dict) -> str:
    """Design context of a BLAST cache entry (with forward, reverse, DB build date and
    miRNA name it forms the key): classifier version, target, species, RT primer, salt."""
    target_dna = target_rna.upper().replace("U", "T")
    return "|".join([f"design-clf{BLAST_CLASSIFIER_VERSION}", target_dna, species or "", rt_seq]
                    + [f"{k}={p3[k]:g}" for k in sorted(p3)])


def blast_candidates(seqs: list[str], target_rna: str, mirna_name: str, reverse_seq: str,
                     rt_seq: str, p3: dict, species: str | None) -> dict:
    """check_offtarget_batch for the candidate pool, through the BLAST sqlite cache.
    Returns {"results": {seq: result}, "available": bool, "reason": str|None,
    "cache_hits": int, "ms": int}. Any failure → available False and no results, so
    S1 is either known for every candidate or for none (comparable totals)."""
    t0 = time.perf_counter()
    out = {"results": {}, "available": False, "reason": None, "cache_hits": 0, "ms": 0,
           "cache_write_error": None}
    ok, why = bo.blast_available()
    if not ok:
        out["reason"] = why
        return out
    from .specificity_check.blast_cache import BlastCache
    target_dna = target_rna.upper().replace("U", "T")
    context = cache_context(target_rna, species, rt_seq, p3)
    db_version = _blast_db_version()
    # The cache is optional: a locked / unreadable sqlite file only skips it.
    cache, cached = None, {}
    if _cache_enabled() and db_version:
        try:
            cache = BlastCache()
            cached = cache.get_results(seqs, reverse_seq, db_version, mirna_name, context)
        except Exception:   # noqa: BLE001
            cache, cached = None, {}
    missing = [s for s in seqs if s not in cached]
    try:
        fresh = bo.check_offtarget_batch(
            missing, reverse_seq, mirna_id=mirna_name or None, target_sequence=target_dna,
            conditions=p3, species=species, rt_primer=rt_seq) if missing else {}
    except Exception as e:   # noqa: BLE001 — SPEC §4: a BLAST failure never fails the request
        out["reason"] = f"BLAST run failed: {type(e).__name__}"
        out["ms"] = round(1000 * (time.perf_counter() - t0))
        return out
    if cache and fresh:
        try:
            cache.set_results(fresh, reverse_seq, db_version, mirna_name, context)
        except Exception as e:   # noqa: BLE001 — reported, never fails the design
            out["cache_write_error"] = f"{type(e).__name__}: {e}"
    out.update(results={**cached, **fresh}, available=True, cache_hits=len(cached),
               ms=round(1000 * (time.perf_counter() - t0)))
    return out


# ── ranking ──────────────────────────────────────────────────────

def _score_all(metrics: list[dict]) -> list[tuple[dict, dict]]:
    return [(m, ts.score(m)) for m in metrics]


def _apply_blast(metrics: list[dict], results: dict) -> None:
    for m in metrics:
        r = results.get(m["sequence"])
        if r is not None:
            m["blast_risk"], m["blast_medium_hits"], m["blast_worst"] = ts.blast_s1_inputs(r)


def rank(seq: str, params: dict, mirna_name: str, binding_len: int, stemloop: dict,
         reverse: dict, candidates: list[dict]) -> dict:
    """Tiered ranking of the candidates (structure_checks already attached).

    Returns {"top": [sets], "warnings": [...], "summary": ranking_summary,
             "overhang_suggestion": dict|None, "screen": assay screen by length}."""
    ta = float(params.get("annealingTemp", TM_ANNEALING_TEMP_DEFAULT))
    tm_rev = round(calculate_tm_nn(reverse["sequence"], params), 2)
    prefix = _resolve_species_prefix(mirna_name, params.get("species"))
    species = prefix.rstrip("-") if bo.is_mirbase_species(prefix.rstrip("-")) else None
    screen = assay_screen(seq, mirna_name, params, binding_len,
                          {c["specific_length"] for c in candidates}, species=species,
                          rt_capture_below=TIERED_RT_CAPTURE_BELOW)

    metrics = []
    for c in candidates:
        v4 = score_candidate(c, stemloop, reverse, params, use_v4=True)
        metrics.append(_metrics(c, v4["scores"], screen[c["specific_length"]], ta, tm_rev))

    # S1: BLAST every candidate S2 does not eliminate (SPEC §5); all of them when S2
    # eliminates every one (the fallback ranks them all, so all need S1).
    p3 = _get_p3_params(params)
    p3 = {k: p3[k] for k in ("mv_conc", "dv_conc", "dntp_conc", "dna_conc")}
    s2_kept = [m for m in metrics if ts.s2_assay_dcq(m["min_delta_cq"]) > 1]
    to_blast = [m["sequence"] for m in (s2_kept or metrics)]
    blast = blast_candidates(to_blast, seq, mirna_name, reverse["sequence"],
                             stemloop["sequence"], p3, species)
    _apply_blast(metrics, blast["results"])
    res = ts.rank(_score_all(metrics))
    if blast["available"] and res["specificity_fallback"] and s2_kept:
        # Every S2 survivor is BLAST CRITICAL: the fallback ranks all candidates, so the
        # S2-eliminated ones need S1 too.
        rest = [m["sequence"] for m in metrics if m["blast_risk"] is None]
        more = blast_candidates(rest, seq, mirna_name, reverse["sequence"],
                                stemloop["sequence"], p3, species)
        blast["ms"] += more["ms"]
        if more["available"]:
            _apply_blast(metrics, more["results"])
            blast["cache_hits"] += more["cache_hits"]
            blast["cache_write_error"] = blast.get("cache_write_error") or more.get("cache_write_error")
        else:
            # S1 must be known for every ranked candidate or for none (comparable totals).
            for m in metrics:
                m["blast_risk"], m["blast_medium_hits"], m["blast_worst"] = None, 0, None
            blast.update(available=False, reason=more["reason"], results={})
        res = ts.rank(_score_all(metrics))

    by_seq = {c["sequence"]: c for c in candidates}
    ranked = []
    for m, r in res["ranked"]:
        c = by_seq[m["sequence"]]
        c.update(_set_fields(m, r, c, res["specificity_fallback"]))
        ranked.append(c)
    top = select_diverse_top(ranked, CANDIDATES_TOP_N)

    warnings = []
    if not blast["available"]:
        warnings.append({"field": "blast_unavailable", "severity": "warning",
                         "message": BLAST_UNAVAILABLE_MESSAGE.format(reason=blast["reason"])})
    if res["specificity_fallback"]:
        warnings.append({"field": "specificity_fallback", "severity": "critical", "message": (
            "Every forward candidate fails specificity (BLAST CRITICAL or assay ΔCq "
            "CO-AMPLIFIED < 3.3). Returning the least bad sets; the assay will likely "
            "co-detect another miRNA — see each set's ranking.specificity.")})
    if len(top) < CANDIDATES_TOP_N:
        warnings.append({"field": "fewer_than_3_sets", "severity": "warning", "message": (
            f"Only {len(top)} primer set(s) returned: the other candidates were eliminated "
            "on specificity (BLAST CRITICAL or assay ΔCq CO-AMPLIFIED), or too few were "
            "generated. Eliminated candidates are not used to fill the list.")})

    summary = {
        "system": "tiered",
        "candidates_scored": len(metrics),
        "eliminated_specificity": res["eliminated"],
        "specificity_fallback": res["specificity_fallback"],
        "blast_available": blast["available"],
        "blast_unavailable_reason": blast["reason"],
        "blast_candidates": sum(m["blast_risk"] is not None for m in metrics),
        "blast_cache_hits": blast["cache_hits"],
        # set when results could not be written to the sqlite cache (counted by batch runs)
        "blast_cache_write_error": blast.get("cache_write_error"),
        "returned_sets": len(top),
        "timing_ms": {"blast": blast["ms"]},   # design_pipeline adds "total"
    }
    return {"top": top, "warnings": warnings, "summary": summary, "screen": screen,
            "overhang_suggestion": (overhang_suggestion(seq, params, mirna_name, binding_len,
                                                        top[0], species) if top else None)}


def _set_fields(m: dict, r: dict, c: dict, specificity_fallback: bool = False) -> dict:
    """API fields of one ranked candidate (SPEC §4). total_score / scores / weights /
    explanations keep the V4 shape so the current frontend still renders them.
    grade: by tiers (QD 30) when TIERED_GRADE_BY_TIERS, else from the detailed score."""
    from . import constants as K
    parts = ts.detailed_parts(m)
    weights = ts.detailed_weights()
    if K.TIERED_GRADE_BY_TIERS:
        g = ts.grade_tiers(r, specificity_fallback)
        grade, grade_reasons = g["grade"], g["reasons"]
    else:
        grade, grade_reasons = _grade(r["detailed_score"]), None
    f3 = r["flexible"].get("specific_length", r["flexible"].get("specific_length_report_only"))
    sp, pcr, fx = r["specificity"], r["pcr"], r["flexible"]
    margin = m["tm_margin"]
    dcq = m["min_delta_cq"]
    sc = c.get("structure_checks", {})
    return {
        "total_score": r["detailed_score"],
        "grade": grade,
        "grade_basis": "tiers (QD 30)" if K.TIERED_GRADE_BY_TIERS else "detailed score",
        "grade_reasons": grade_reasons,
        "scores": {**{k: round(v, 1) for k, v in parts.items()},
                   # informational, as in V4 (UNSCORED_CRITERIA_V4): not in weights/total
                   **({"bound_fraction_binding_pct": m["bound_fraction_binding_pct"]}
                      if m.get("bound_fraction_binding_pct") is not None else {})},
        "weights": weights,
        "weights_nominal": {k: v for k, v in TIERED_DETAIL_WEIGHTS.items() if k in weights},
        "unscored_criteria": [],
        "explanations": _explanations(m, parts),
        "scoring_version": "tiered",
        "pass_all_structure_checks": sc.get("overall_pass", False),
        "has_critical_flag": sc.get("has_critical_flag", False),
        "ranking": {
            "system": "tiered",
            "specificity": {
                "blast": {"score": sp["blast"], "overall_risk": m["blast_risk"],
                          "medium_hits": m["blast_medium_hits"] if m["blast_risk"] else None,
                          "worst_hit": m["blast_worst"]},
                "assay_dcq": {"score": sp["assay_dcq"], "min_delta_cq": dcq,
                              "worst_target": m["worst"],
                              "label": assay_label(dcq) if dcq is not None else "DISCRIMINATED"},
                "tm_margin": {"score": sp["tm_margin"], "tm_on": m["tm_on"],
                              "tm_off_max": (round(m["tm_on"] - margin, 1)
                                             if margin is not None and m["tm_on"] is not None else None),
                              "margin": margin, "worst_target": m["tm_margin_worst"]},
                "total": sp["total"], "max": sp["max"]},
            "pcr": {
                "tm_vs_ta": {"score": pcr["tm_vs_ta"], "tm": m["tm_full"], "ta": m["ta"],
                             "diff": round(abs(m["tm_full"] - m["ta"]), 2)},
                "tm_pair": {"score": pcr["tm_pair_report_only"], "report_only": True,
                            "tm_forward": m["tm_full"], "tm_reverse": m["tm_reverse"],
                            "diff": round(abs(m["tm_full"] - m["tm_reverse"]), 2)},
                "total": pcr["total"], "max": pcr["max"]},
            "flexible": {
                "gc": {"score": fx["gc"], "gc_percent": m["gc_percent"]},
                "gc_clamp": {"score": fx["gc_clamp"], "last5": m["sequence"][-5:]},
                "specific_length": {"score": f3, "length": m["specific_length"],
                                    "report_only": "specific_length" not in fx},
                "binding_tm": {"score": fx["binding_tm"], "tm_binding": m["tm_binding"],
                               "target": TM_BINDING_TARGET,
                               "mode": "floor (QD 29)" if K.TIERED_F4_FLOOR else "two-sided"},
                "structure": {"score": fx["structure"], "hairpin_tm": m["hairpin_tm"],
                              "dimer_dg": m["dimer_dg"], "end_dimer_tm": m["end_dimer_tm"],
                              "sub_scores": fx["structure_sub_scores"]},
                "total": fx["total"], "max": fx["max"]},
            "structure_veto": r["structure_veto"],
            "binding_floor_fail": r["binding_floor_fail"],
            "eliminated": r["eliminated"],
            "detailed_score": r["detailed_score"],
        },
    }


def _fmt(x, unit=""):
    return "n/a" if x is None else f"{x:g}{unit}"


def _explanations(m: dict, parts: dict) -> dict:
    from . import constants as K
    dcq, margin = m["min_delta_cq"], m["tm_margin"]
    out = {
        "min_delta_cq": (
            "No same-species miRNA within 10 Cq of the target (assay ΔCq model)."
            if dcq is None else
            f"Closest same-species miRNA {m['worst']}: ΔCq_assay {dcq:g} (RT + forward step); "
            f"capped at 10 for this sub-score."),
        "tm_margin": (
            "No same-species miRNA is captured by the RT primer (ΔCq_RT < 4.3)."
            if margin is None else
            f"Tm_on − max Tm_off = {margin:g} °C (worst {m['tm_margin_worst']}, most stable "
            f"register within ±2 nt); capped at 20 °C."),
        "tm_accuracy": f"Forward primer Tm {m['tm_full']:g} °C vs annealing temperature {m['ta']:g} °C.",
        "tm_binding_accuracy": (f"Specific-region (cycle-1) Tm {m['tm_binding']:g} °C vs target "
                                f"{TM_BINDING_TARGET:g} °C."),
        "gc_content": f"GC {m['gc_percent']:g} % of the full forward primer.",
        "gc_clamp": f"3' end {m['sequence'][-5:]} (G/C in the last 5 nt).",
        "primer_size": f"Specific region {m['specific_length']} nt.",
        "structure": (f"Mean of hairpin Tm {_fmt(m['hairpin_tm'], ' °C')}, dimer ΔG "
                      f"{_fmt(m['dimer_dg'], ' kcal/mol')}, 3'-end dimer Tm "
                      f"{_fmt(m['end_dimer_tm'], ' °C')} sub-scores."),
        "amplicon_size": "Amplicon length (V4 sub-score).",
    }
    if K.TIERED_F4_FLOOR:
        out["tm_binding_accuracy"] = (
            f"Specific-region (cycle-1) Tm {m['tm_binding']:g} °C; floor {TM_BINDING_TARGET:g} °C "
            f"(100 at or above, linear to 0 at {TIERED_DETAIL_TM_BINDING_FLOOR[0][0]:g} °C; "
            "QD 29, QD 33).")
    return {k: v for k, v in out.items() if k in parts}


# ── overhang suggestion (SPEC §3.6) ──────────────────────────────

def overhang_suggestion(seq: str, params: dict, mirna_name: str, binding_len: int,
                        best: dict, species: str | None) -> dict | None:
    """S2 of the #1 set's specific region with the other supported RT overhangs. If
    one gives a higher S2 level than the chosen overhang, suggest it; the design is
    not changed. None otherwise, or when the region does not fit that overhang."""
    L = best["specific_length"]
    current = ts.s2_assay_dcq(best["ranking"]["specificity"]["assay_dcq"]["min_delta_cq"])
    options = []
    for ov in range(OVERHANG_LENGTH_MIN, OVERHANG_LENGTH_MAX + 1):
        if ov == binding_len or L > len(seq) - ov:
            continue
        s = assay_screen(seq, mirna_name, params, ov, {L}, species=species,
                         rt_capture_below=TIERED_RT_CAPTURE_BELOW)[L]
        lvl = ts.s2_assay_dcq(s["min_delta_cq"])
        if lvl > current:
            dcq_key = 99.0 if s["min_delta_cq"] is None else s["min_delta_cq"]
            options.append(((lvl, dcq_key, -abs(ov - OVERHANG_LENGTH_DEFAULT), -ov), ov, s, lvl))
    if not options:
        return None
    _, ov, s, lvl = max(options)
    off_label = ov != OVERHANG_LENGTH_DEFAULT
    return {
        "length": ov, "min_delta_cq": s["min_delta_cq"], "worst_target": s["worst"],
        "s2_level": lvl, "s2_level_current": current, "specific_length": L,
        "note": (f"A {ov}-nt RT overhang gives S2 level {lvl} (vs {current} with {binding_len} nt) "
                 f"for the #1 set's {L}-nt specific region. Suggestion only — the design was "
                 "not changed. "
                 + ("Off-label: only 6 nt was validated by Chen et al. 2005; not verified "
                    "by wet-lab experiment." if off_label else
                    "6 nt is the length validated by Chen et al. 2005.")),
    }


def thresholds_table() -> dict:
    """Every TIERED_* constant — hashed into _provenance() (tiered_thresholds_sha256)."""
    from . import constants as K
    return {k: getattr(K, k) for k in sorted(dir(K)) if k.startswith("TIERED_")}
