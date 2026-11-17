"""
scripts/thesis_freeze_impact.py — offline impact of the 4.0.0 freeze changes.

Measures, on every hsa miRNA of miRBase 22.1 (2656), what the changes proposed in
docs/PROMPT_thesis_freeze_4.0.0.md would do BEFORE any algorithm code is changed:

  1.1  REV-23  family_discrimination scored per candidate (assay ΔCq on the
               candidate's own specific length) instead of once on the winner's.
  1.2          end_stability — is it saturated? (report only)
  1.3  REV-21  Primer3 PRIMER_MAX_SELF_END_TH / PRIMER_PAIR_MAX_COMPL_END_TH = 47 °C
               as a hard filter (3'-anchored dimer Tm, primer3 calc_end_stability).
  1.4          criterion variability and the #1 − #2 margin after 1.1–1.3.
  2.1  D-8     why the failed designs fail (forward pre-filter reasons).

Step 1 (`record`) designs every miRNA through the Flask test client (empty parameter
groups = backend defaults, as crossreactivity/design_all.py and
scoring_weight_sensitivity.py do) and records, per design:
  - every candidate that reached the hard-filter gate, with its current rejections
    and the structure numbers needed for REV-21 and end_stability;
  - the V4 scores of EVERY gate candidate (rejected ones are scored afterwards with
    the same stem-loop/reverse/params, so a design that would fall back under a new
    rule can be re-ranked);
  - the worst assay label of check_overhang_collision for each specific length
    present (REV-23);
  - for failed designs, the pre-filter reason set of every generated candidate.
The recorded pools go to outputs/freeze_cache/ (git-ignored, ~tens of MB).

Step 2 (`analyse`) re-ranks the recorded pools offline with the pipeline's own rule
(renormalised weighted mean rounded to 0.1, ties by |Tm_full − Ta| then sequence;
top 3 by select_diverse_top) and checks that the unchanged ranking reproduces the
API #1 and top 3 for every design.

Usage (repo root):
    python backend/scripts/thesis_freeze_impact.py record [--workers 14] [--limit N]
    python backend/scripts/thesis_freeze_impact.py analyse [--out benchmark/thesis_freeze_impact.json]
"""
import argparse
import copy
import gzip
import json
import multiprocessing as mp
import os
import statistics as st
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
CACHE_DIR = os.path.join(ROOT, "outputs", "freeze_cache")

# Primer3 defaults (primer3 manual): PRIMER_MAX_SELF_END_TH = 47.0,
# PRIMER_PAIR_MAX_COMPL_END_TH = 47.0, PRIMER_MAX_HAIRPIN_TH = 47.0 — "10 degrees
# lower than the default value of PRIMER_MIN_TM" (57 °C).
P3_END_TH_DEFAULT = 47.0

WETLAB = ["hsa-miR-16-5p", "hsa-miR-21-5p", "hsa-let-7a-5p", "hsa-miR-451a",
          "hsa-miR-126-3p", "hsa-miR-223-3p"]

# SantaLucia 1998 unified NN ΔG°37 (kcal/mol), 5'→3' / 3'→5'. Used for the
# Primer3 definition of end stability: ΔG of disruption of the last 5 bases as a
# perfect duplex (primer3 oligotm.c end_oligodg, santalucia): init 1.96 kcal/mol
# (+0.05 per terminal A·T).
_NN_DG = {"AA": -1.00, "TT": -1.00, "AT": -0.88, "TA": -0.58, "CA": -1.45, "TG": -1.45,
          "GT": -1.44, "AC": -1.44, "CT": -1.28, "AG": -1.28, "GA": -1.30, "TC": -1.30,
          "CG": -2.17, "GC": -2.24, "GG": -1.84, "CC": -1.84}


def nn_end_stability(seq5: str) -> float:
    s = seq5.upper()
    dg = sum(_NN_DG[s[i:i + 2]] for i in range(len(s) - 1))
    dg += 1.96 + 0.05 * sum(b in "AT" for b in (s[0], s[-1]))
    return round(-dg, 2)


# ── worker (record) ───────────────────────────────────────────────
_client = None
_state: dict = {}


def _init_worker():
    global _client
    sys.path.insert(0, BACKEND)
    os.chdir(BACKEND)
    import algorithm.design_pipeline as dp
    import algorithm.forward_primer as fp
    import algorithm.primer3_safe as p3s
    from algorithm.thermodynamics import _get_p3_params

    orig_score = dp.score_candidate
    orig_hard = dp.apply_hard_filters
    orig_gen = dp.generate_forward_candidates
    orig_prefilter = fp._prefilter
    orig_oc = dp.check_overhang_collision

    def gen(seq, params):
        _state["params"] = params
        _state["seq"] = seq
        return orig_gen(seq, params)

    def prefilter(c, params):
        hard, warn = orig_prefilter(c, params)
        _state.setdefault("prefilter", []).append(
            (c["specific_length"], tuple(sorted(hard)), c["gc_percent"], c["tm_full"],
             c["tm_binding"], c["gc_specific_percent"]))
        return hard, warn

    def end_tm(a, b):
        p3 = _get_p3_params(_state["params"])
        with p3s._LOCK:
            r = p3s._primer3.calc_end_stability(a, b, mv_conc=p3["mv_conc"],
                                                dv_conc=p3["dv_conc"],
                                                dntp_conc=p3["dntp_conc"],
                                                dna_conc=p3["dna_conc"])
        return round(float(r.tm), 1)

    def hard(c):
        rej = orig_hard(c)
        sc = c.get("structure_checks", {})
        from algorithm.structure_check import full_dimer_dg
        from algorithm.constants import UNIVERSAL_REVERSE
        rev = _state.get("reverse") or UNIVERSAL_REVERSE
        s = c["sequence"]
        _state.setdefault("gate", []).append({
            "cand": c, "rej": rej,
            "hp_tm": sc.get("hairpin", {}).get("tm"),
            "dg3_self": sc.get("self_dimer", {}).get("dg_3prime"),
            "dg3_het": sc.get("hetero_dimer", {}).get("dg_3prime"),
            "full_dg": full_dimer_dg(sc)[0],
            "end_stab_cur": sc.get("end_stability", {}).get("stability_kcal_mol"),
            "end_stab_pass": sc.get("end_stability", {}).get("pass"),
            "end_tm_self": end_tm(s, s),
            "end_tm_fr": end_tm(s, rev),
            "end_tm_rf": end_tm(rev, s),
        })
        return rej

    def score(c, stemloop, reverse, params, **kw):
        _state["score_args"] = (stemloop, reverse, params, kw)
        res = orig_score(c, stemloop, reverse, params, **kw)
        _state.setdefault("scored", {})[c["sequence"]] = res
        return res

    def oc(**kw):
        _state["oc_kwargs"] = {k: v for k, v in kw.items() if k != "forward_specific_len"}
        return orig_oc(**kw)

    dp.generate_forward_candidates = gen
    fp._prefilter = prefilter
    dp.apply_hard_filters = hard
    dp.score_candidate = score
    dp.check_overhang_collision = oc
    _state["orig_score"] = orig_score
    _state["orig_oc"] = orig_oc
    from algorithm.universal_reverse import get_universal_reverse
    _state["reverse_fn"] = get_universal_reverse
    from app import app
    app.config["TESTING"] = True
    _client = app.test_client()


def _num_scores(res: dict) -> dict:
    return {k: v for k, v in res["scores"].items() if isinstance(v, (int, float))}


def _design(item):
    name, dna = item
    keep = {k: _state[k] for k in ("orig_score", "orig_oc", "reverse_fn")}
    _state.clear()
    _state.update(keep)
    from algorithm.constants import UNIVERSAL_REVERSE, TM_ANNEALING_TEMP_DEFAULT
    _state["reverse"] = UNIVERSAL_REVERSE
    body = {"thermodynamic": {}, "primerConstraints": {}, "qpcr": {},
            "detectionMethod": {}, "experimentalContext": {},
            "sequence": {"matureSequence": dna.replace("T", "U"), "mirnaId": name}}
    r = _client.post("/api/design", json=body)
    d = r.get_json(silent=True) or {}
    top3 = [p.get("sequence") for p in (d.get("top3") or [])]
    warn_fields = [w.get("field") for w in d.get("global_warnings", [])]
    rec = {"mirna": name, "dna": dna, "status": r.status_code,
           "ta": float(TM_ANNEALING_TEMP_DEFAULT), "api_top3": top3,
           "api_scores": [p.get("total_score") for p in (d.get("top3") or [])],
           "fallback": "hard_filter_fallback" in warn_fields,
           "error": d.get("error"), "rejection_summary": d.get("rejection_summary")}

    if not top3:
        # D-8: reason set of every generated candidate, by specific length
        by_L = defaultdict(Counter)
        props = defaultdict(lambda: {"gc_full": [], "tm_full": []})
        spec = {}
        for L, reasons, gc, tm, tmb, gcs in _state.get("prefilter", []):
            by_L[L]["|".join(reasons) or "PASS"] += 1
            props[L]["gc_full"].append(gc)
            props[L]["tm_full"].append(tm)
            spec[L] = {"tm_binding": tmb, "gc_specific": gcs}
        rec["failed"] = {
            str(L): {"reason_sets": dict(by_L[L]), **spec[L],
                     "gc_full_min": min(props[L]["gc_full"]),
                     "gc_full_max": max(props[L]["gc_full"]),
                     "tm_full_min": min(props[L]["tm_full"]),
                     "tm_full_max": max(props[L]["tm_full"])}
            for L in sorted(by_L)}
        return rec

    stemloop, reverse, params, kw = _state["score_args"]
    scored = _state.get("scored", {})
    gate = []
    for g in _state.get("gate", []):
        c = g.pop("cand")
        res = scored.get(c["sequence"])
        if res is None:   # rejected at the gate: score it with the same inputs
            res = _state["orig_score"](copy.deepcopy(c), stemloop, reverse, params, **kw)
        g.update({"seq": c["sequence"], "L": c["specific_length"],
                  "tail_length": c.get("tail_length"), "tm_full": c.get("tm_full"),
                  "gc": c.get("gc_percent"), "scores": _num_scores(res),
                  "in_api_pool": c["sequence"] in scored})
        gate.append(g)
    rec["gate"] = gate

    # REV-23: worst assay label for every specific length present
    ock = _state["oc_kwargs"]
    fam = {}
    for L in sorted({g["L"] for g in gate}):
        o = _state["orig_oc"](**ock, forward_specific_len=L)
        worst = o.get("worst_assay_label")
        we = next((e for e in o.get("collisions", []) if e.get("assay_label") == worst), None)
        fam[str(L)] = {"label": worst, "summary": o.get("summary"),
                       "worst_mirna": we and we.get("mirna"),
                       "worst_dcq": we and we.get("delta_cq")}
    rec["fam_by_L"] = fam
    return rec


def record(a) -> int:
    sys.path.insert(0, ROOT)
    sys.path.insert(0, BACKEND)
    from crossreactivity.model import load_mature
    from algorithm.constants import ALGORITHM_VERSION
    mature = load_mature(os.path.join(BACKEND, "data", "mirbase_overhang_index.json"), "hsa")
    items = sorted(mature.items())
    if a.only:
        items = [i for i in items if i[0] in set(a.only.split(","))]
    items = items[: a.limit]
    os.makedirs(CACHE_DIR, exist_ok=True)
    out = os.path.join(CACHE_DIR, f"pools_hsa_{ALGORITHM_VERSION}.jsonl.gz")
    t0 = time.time()
    n = 0
    with gzip.open(out, "wt", encoding="utf-8") as f, \
            mp.Pool(a.workers, initializer=_init_worker) as pool:
        for rec in pool.imap_unordered(_design, items, chunksize=2):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
            if n % 250 == 0 or n == len(items):
                print(f"  {n}/{len(items)}  {time.time() - t0:.0f}s", flush=True)
    print(f"wrote {out}")
    return 0


# ── offline ranking ───────────────────────────────────────────────
def total(scores: dict, w: dict, unscored: frozenset) -> float:
    keys = [k for k in w if k not in unscored and isinstance(scores.get(k), (int, float))]
    ws = sum(w[k] for k in keys)
    return round(sum(scores[k] * w[k] for k in keys) / ws, 1)


class Ranker:
    def __init__(self, weights, unscored, label_score):
        self.w, self.u, self.ls = weights, unscored, label_score

    def scores(self, g, rec, per_candidate_family):
        s = dict(g["scores"])
        if per_candidate_family:
            s["family_discrimination"] = self.ls.get(rec["fam_by_L"][str(g["L"])]["label"], 100)
        return s

    def rank(self, rec, gate_rule, per_candidate_family):
        """Return (ranked list of (total, cand), fallback flag)."""
        passed = [g for g in rec["gate"] if gate_rule(g)]
        fallback = not passed
        pool = rec["gate"] if fallback else passed
        out = []
        for g in pool:
            t = total(self.scores(g, rec, per_candidate_family), self.w, self.u)
            out.append((t, g))
        out.sort(key=lambda x: (-x[0], abs((x[1]["tm_full"] or 0) - rec["ta"]), x[1]["seq"]))
        return out, fallback


def top3(ranked):
    from algorithm.forward_primer import select_diverse_top
    from algorithm.constants import CANDIDATES_TOP_N
    pseudo = [{"specific_length": g["L"], "sequence": g["seq"], "_t": t, "_g": g}
              for t, g in ranked]
    return select_diverse_top(pseudo, CANDIDATES_TOP_N)


# Gate rules: the current three (as recorded) and the REV-21 Primer3 end-Tm rule.
def rule_current(g):
    return not g["rej"]


def rule_rev21(g):
    return rule_current(g) and rev21_reject(g) is None


def rev21_reject(g):
    if g["end_tm_self"] >= P3_END_TH_DEFAULT:
        return "self_end_th"
    if max(g["end_tm_fr"], g["end_tm_rf"]) >= P3_END_TH_DEFAULT:
        return "pair_compl_end_th"
    return None


def _pct(n, d):
    return round(100 * n / d, 1) if d else 0.0


def _dist(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return {}
    q = lambda p: xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))]   # noqa: E731
    return {"n": len(xs), "min": xs[0], "p05": q(0.05), "median": q(0.5), "p95": q(0.95),
            "max": xs[-1]}


def analyse(a) -> int:
    sys.path.insert(0, BACKEND)
    os.chdir(BACKEND)
    from algorithm.constants import (ALGORITHM_VERSION, SCORING_WEIGHTS_V4,
                                     UNSCORED_CRITERIA_V4, ASSAY_LABEL_SCORE,
                                     END_STABILITY_MAX)
    src = os.path.join(CACHE_DIR, f"pools_hsa_{a.version or ALGORITHM_VERSION}.jsonl.gz")
    with gzip.open(src, "rt", encoding="utf-8") as f:
        recs = [json.loads(line) for line in f]
    recs.sort(key=lambda r: r["mirna"])
    ok = [r for r in recs if r["api_top3"]]
    failed = [r for r in recs if not r["api_top3"]]
    R = Ranker(SCORING_WEIGHTS_V4, frozenset(UNSCORED_CRITERIA_V4), ASSAY_LABEL_SCORE)
    crit = [k for k in SCORING_WEIGHTS_V4 if k not in UNSCORED_CRITERIA_V4]

    scenarios = {
        "3.8.1 (current)": (rule_current, False),
        "1.1 REV-23 per-candidate family": (rule_current, True),
        "1.3 REV-21 end Tm >= 47 C": (rule_rev21, False),
        "1.1 + 1.3": (rule_rev21, True),
    }
    res = {}
    base_top = {}
    for name, (rule, fam) in scenarios.items():
        tops, top3s, fallbacks, margins_pool, margins_set2, margins_set3 = {}, {}, 0, [], [], []
        var_pool, var_top5 = Counter(), Counter()
        n_rows = 0
        for r in ok:
            ranked, fb = R.rank(r, rule, fam)
            fallbacks += fb
            tops[r["mirna"]] = ranked[0]
            t3 = top3(ranked)
            top3s[r["mirna"]] = t3
            if len(ranked) > 1:
                margins_pool.append(round(ranked[0][0] - ranked[1][0], 1))
            if len(t3) > 1:
                margins_set2.append(round(t3[0]["_t"] - t3[1]["_t"], 1))
            if len(t3) > 2:
                margins_set3.append(round(t3[0]["_t"] - t3[2]["_t"], 1))
            n_rows += 1
            for k in crit:
                vals = {R.scores(g, r, fam).get(k) for _, g in ranked}
                var_pool[k] += len(vals) > 1
                vals5 = {R.scores(g, r, fam).get(k) for _, g in ranked[:5]}
                var_top5[k] += len(vals5) > 1
        if name == "3.8.1 (current)":
            base_top = {m: (t[1]["seq"], top3s[m]) for m, t in tops.items()}
            agree1 = sum(tops[r["mirna"]][1]["seq"] == r["api_top3"][0] for r in ok)
            agree3 = sum([c["sequence"] for c in top3s[r["mirna"]]] == r["api_top3"] for r in ok)
        ch1 = [m for m, t in tops.items() if t[1]["seq"] != base_top[m][0]]
        ch_set = [m for m in tops if [c["sequence"] for c in top3s[m]]
                  != [c["sequence"] for c in base_top[m][1]]]
        top1_labels = Counter(r["fam_by_L"][str(tops[r["mirna"]][1]["L"])]["label"] for r in ok)
        dL = Counter(tops[m][1]["L"] - next(g["L"] for g in r["gate"] if g["seq"] == base_top[m][0])
                     for r in ok for m in [r["mirna"]] if m in ch1)
        res[name] = {
            "designs": n_rows,
            "hard_filter_fallback": fallbacks,
            "top1_changed_vs_3.8.1": len(ch1),
            "top3_changed_vs_3.8.1": len(ch_set),
            "top1_changed_examples": ch1[:25],
            "top1_specific_length_shift": {str(k): v for k, v in sorted(dL.items())},
            "top1_assay_label_own_length": dict(top1_labels),
            "top1_specific_length": dict(sorted(Counter(t[1]["L"] for t in tops.values()).items())),
            "margin_top1_minus_next_in_pool": {
                "median": st.median(margins_pool), "eq_0": sum(m == 0 for m in margins_pool),
                "le_0_5": sum(m <= 0.5 for m in margins_pool),
                "lt_1": sum(m < 1 for m in margins_pool), "n": len(margins_pool)},
            "margin_set1_minus_set2": {
                "median": st.median(margins_set2), "eq_0": sum(m == 0 for m in margins_set2),
                "le_0_5": sum(m <= 0.5 for m in margins_set2),
                "lt_1": sum(m < 1 for m in margins_set2), "n": len(margins_set2)},
            "margin_set1_minus_set3": {
                "median": st.median(margins_set3), "lt_1": sum(m < 1 for m in margins_set3),
                "n": len(margins_set3)},
            "criterion_variability": {
                k: {"pools_where_it_varies_pct": _pct(var_pool[k], n_rows),
                    "top5_where_it_varies_pct": _pct(var_top5[k], n_rows)} for k in crit},
            "wetlab_candidates": {
                m: [{"rank": i + 1, "sequence": c["sequence"], "L": c["specific_length"],
                     "score": c["_t"], "selection": c.get("selection"),
                     "assay_label_own_length": next(r for r in ok if r["mirna"] == m)
                     ["fam_by_L"][str(c["specific_length"])]["label"]}
                    for i, c in enumerate(top3s[m])]
                for m in WETLAB if m in top3s},
        }
    res["3.8.1 (current)"]["offline_top1_equals_api_top1"] = agree1
    res["3.8.1 (current)"]["offline_top3_equals_api_top3"] = agree3

    # ── 1.1 detail: does the per-L label vary inside a design? ──
    fam_varies = sum(len({v["label"] for v in r["fam_by_L"].values()}) > 1 for r in ok)
    fam_varies_pool = 0
    for r in ok:
        Ls = {g["L"] for g in r["gate"] if rule_current(g)} or {g["L"] for g in r["gate"]}
        fam_varies_pool += len({r["fam_by_L"][str(L)]["label"] for L in Ls}) > 1
    rev23 = {"designs_where_label_differs_between_lengths_in_pool": fam_varies_pool,
             "designs_where_label_differs_between_any_recorded_lengths": fam_varies,
             "pct_of_designs": _pct(fam_varies_pool, len(ok))}

    # ── 1.2 end_stability ──
    all_gate = [g for r in ok for g in r["gate"]]
    api_pool = [g for g in all_gate if g["in_api_pool"]]
    nn_vals = [nn_end_stability(g["seq"][-5:]) for g in api_pool]
    import itertools
    all5 = {"".join(p): nn_end_stability("".join(p)) for p in itertools.product("ACGT", repeat=5)}
    mx = max(all5.values())
    endstab = {
        "candidates_scored": len(api_pool),
        "pass_false": sum(g["end_stab_pass"] is False for g in api_pool),
        "end_stability_score_below_100": sum(g["scores"].get("end_stability", 100) < 100
                                             for g in api_pool),
        "current_value_kcal_mol": _dist([g["end_stab_cur"] for g in api_pool]),
        "current_method": "primer3 calc_hairpin(last 5 nt) at 37 °C, |ΔG|",
        "threshold_kcal_mol": END_STABILITY_MAX,
        "primer3_definition_value_kcal_mol": _dist(nn_vals),
        "primer3_definition_note": ("ΔG of disruption of the last 5 bases as a perfect "
                                    "duplex, SantaLucia 1998 unified NN, init 1.96 (+0.05 per "
                                    "terminal A·T) — primer3 end_oligodg (santalucia)"),
        "max_possible_any_5mer": {"value": mx, "sequences": [k for k, v in all5.items() if v == mx]},
        "candidates_ge_threshold_primer3_definition": sum(v > END_STABILITY_MAX for v in nn_vals),
        "nn_value_varies_within_pool_pct": _pct(sum(
            len({nn_end_stability(g["seq"][-5:]) for g in r["gate"] if g["in_api_pool"]}) > 1
            for r in ok), len(ok)),
    }

    # ── 1.3 REV-21 detail ──
    gate_pass = [g for g in all_gate if rule_current(g)]
    rej21 = Counter(rev21_reject(g) for g in gate_pass)
    rule2_fired = sum(any("hard_dimer_3prime" in x for x in g["rej"]) for g in all_gate)
    new_fb = [r["mirna"] for r in ok if R.rank(r, rule_rev21, False)[1]
              and not R.rank(r, rule_current, False)[1]]
    rev21 = {
        "gate_candidates": len(all_gate),
        "passing_current_rules": len(gate_pass),
        "current_rule2_dg8nt_fired": rule2_fired,
        "newly_rejected": {k: v for k, v in rej21.items() if k},
        "newly_rejected_total": sum(v for k, v in rej21.items() if k),
        "designs_with_any_new_rejection": sum(
            any(rule_current(g) and rev21_reject(g) for g in r["gate"]) for r in ok),
        "new_hard_filter_fallback": new_fb,
        "end_tm_self_c": _dist([g["end_tm_self"] for g in all_gate]),
        "end_tm_pair_max_c": _dist([max(g["end_tm_fr"], g["end_tm_rf"]) for g in all_gate]),
        "conditions": "primer3 calc_end_stability (thal END1), design salts (mv 50 mM eff., "
                      "Mg 1.5 mM, dNTP 0.8 mM, primer 200 nM); pair = max(F×R, R×F)",
    }

    # ── 2.1 D-8 failed designs ──
    sole, any_fail, by_reason_L_block = Counter(), Counter(), Counter()
    rows = []
    for r in failed:
        f = r.get("failed") or {}
        sets = Counter()
        for L, v in f.items():
            for k, n in v["reason_sets"].items():
                sets[k] += n
        reasons_present = Counter()
        sole_r = Counter()
        for k, n in sets.items():
            rs = k.split("|")
            for x in rs:
                reasons_present[x] += n
            if len(rs) == 1:
                sole_r[rs[0]] += n
        min_n = min((len(k.split("|")) for k in sets), default=0)
        rescue = sorted({x for x in sole_r})
        for x in reasons_present:
            any_fail[x] += 1
        for x in rescue:
            sole[x] += 1
        # reasons that block a whole specific length (every candidate of that L)
        for L, v in f.items():
            common = None
            for k in v["reason_sets"]:
                s = set(k.split("|"))
                common = s if common is None else common & s
            for x in common or ():
                by_reason_L_block[x] += 1
        dna = r["dna"]
        gc = round(100 * sum(b in "GC" for b in dna) / len(dna), 1)
        num = None
        import re
        mm = re.match(r"hsa-(?:miR|let)-(\d+)", r["mirna"])
        if mm:
            num = int(mm.group(1))
        rows.append({"mirna": r["mirna"], "len": len(dna), "gc": gc, "number": num,
                     "n_candidates": sum(sets.values()),
                     "min_reasons_per_candidate": min_n,
                     "single_relaxation_rescues": rescue,
                     "candidates_by_reason": dict(reasons_present.most_common()),
                     "specific_lengths": {L: {"gc_specific": v["gc_specific"],
                                              "tm_binding": v["tm_binding"],
                                              "gc_full_range": [v["gc_full_min"], v["gc_full_max"]],
                                              "tm_full_range": [v["tm_full_min"], v["tm_full_max"]]}
                                          for L, v in f.items()}})
    nf = len(failed)
    gcs_f = [x["gc"] for x in rows]
    gcs_ok = [round(100 * sum(b in "GC" for b in r["dna"]) / len(r["dna"]), 1) for r in ok]
    d8 = {
        "failed": nf,
        "error_messages": dict(Counter(r.get("error") for r in failed)),
        "gc_median_failed": st.median(gcs_f) if gcs_f else None,
        "gc_median_designed": st.median(gcs_ok),
        "designs_where_reason_hits_some_candidate": dict(any_fail.most_common()),
        "designs_rescued_by_relaxing_only_this_reason": dict(sole.most_common()),
        "designs_needing_two_or_more_relaxations": sum(not x["single_relaxation_rescues"]
                                                       for x in rows),
        "specific_lengths_blocked_entirely_by_reason": dict(by_reason_L_block.most_common()),
        "low_number_mirnas": sorted([x for x in rows if x["number"] is not None
                                     and x["number"] < 1000], key=lambda x: (x["number"], x["mirna"])),
        "all": rows,
    }

    out = {
        "generated_by": "backend/scripts/thesis_freeze_impact.py",
        "run_date": time.strftime("%Y-%m-%d"),
        "algorithm_version": a.version or ALGORITHM_VERSION,
        "species": "hsa", "mirbase_release": "22.1", "mirnas": len(recs),
        "designed": len(ok), "failed": nf,
        "note": ("Offline re-ranking of recorded candidate pools (backend defaults). Counts "
                 "describe the tool's ranking, not wet-lab outcomes."),
        "scenarios": res,
        "rev23_label_variation": rev23,
        "end_stability": endstab,
        "rev21": rev21,
        "d8_failed_designs": d8,
    }
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print(f"wrote {a.out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    r.add_argument("--limit", type=int)
    r.add_argument("--only", help="comma-separated miRNA names")
    an = sub.add_parser("analyse")
    an.add_argument("--out", default=os.path.join(ROOT, "benchmark", "thesis_freeze_impact.json"))
    an.add_argument("--version", help="pool file version (default: current ALGORITHM_VERSION)")
    a = ap.parse_args(argv)
    return record(a) if a.cmd == "record" else analyse(a)


if __name__ == "__main__":
    sys.exit(main())
