"""
scripts/scoring_weight_sensitivity.py — how scoring-weight choices move primer #1.

Designs every hsa miRNA (POST /api/design through the Flask test client, empty
parameter groups = backend defaults, as crossreactivity/design_all.py does) and
records the FULL scored candidate pool of each design: every candidate that
reached score_candidate in the final (fixpoint) batch, with its per-criterion
scores. The legacy gc_skew score (scoring.gc_skew_score) is added to each
candidate so the 3.7.0 weight table can be evaluated too.

Pools are then re-ranked offline under alternative weight tables with the
pipeline's own rule: renormalised weighted mean rounded to 0.1, ties broken by
|Tm_full − Ta| and then sequence. The offline #1 under the active table is
checked against the #1 the API returned (it must agree for every design).
Limitation: family_discrimination is scored on the winner's specific length (the
overhang fixpoint); re-ranking keeps the recorded value, so a table that moves the
winner to another specific length is evaluated without re-running the fixpoint.

Written for the algorithm 3.8.0 decision (drop gc_skew, gc_clamp 0.04 → 0.06).

Usage (repo root):
    python backend/scripts/scoring_weight_sensitivity.py \
        [benchmark/scoring_weight_sensitivity.json] [--workers 14]
"""
import argparse
import json
import multiprocessing as mp
import os
import re
import statistics as st
import sys
import time
from collections import Counter

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")

# Weight table of algorithm 3.7.0 (SCORING_WEIGHTS_V4 before 3.8.0).
V4_370 = {
    "tm_accuracy": 0.20, "mfe_stemloop": 0.14, "tm_binding_accuracy": 0.10,
    "hairpin_penalty": 0.08, "dimer_penalty": 0.08, "end_stability": 0.08,
    "bound_fraction_binding": 0.05, "bound_fraction_full": 0.03, "gc_content": 0.08,
    "family_discrimination": 0.05, "tm_pair_match": 0.01, "gc_clamp": 0.04,
    "primer_size": 0.02, "amplicon_size": 0.02, "gc_skew": 0.02,
}
# Canonical intramolecular G-quadruplex motif: four G-tracts of ≥ 3, loops 1–7 nt.
G4_MOTIF = re.compile(r"G{3,}\w{1,7}G{3,}\w{1,7}G{3,}\w{1,7}G{3,}")


def _without_skew(**delta):
    w = {k: v for k, v in V4_370.items() if k != "gc_skew"}
    for k, d in delta.items():
        w[k] = round(w[k] + d, 4)
    return w


OPTIONS = {
    "3.7.0 (with gc_skew)": dict(V4_370),
    "drop gc_skew only": _without_skew(),
    "gc_clamp +0.02 (3.8.0)": _without_skew(gc_clamp=0.02),
    "primer_size +0.02": _without_skew(primer_size=0.02),
    "primer_size +0.01, gc_clamp +0.01": _without_skew(primer_size=0.01, gc_clamp=0.01),
    "tm_accuracy +0.02": _without_skew(tm_accuracy=0.02),
    "tm_binding_accuracy +0.02": _without_skew(tm_binding_accuracy=0.02),
    "family_discrimination +0.02": _without_skew(family_discrimination=0.02),
    "dimer_penalty +0.02": _without_skew(dimer_penalty=0.02),
}

# ── worker ─────────────────────────────────────────────────────────
_client = None
_pool_rec: dict = {}


def _init_worker():
    global _client
    sys.path.insert(0, BACKEND)
    os.chdir(BACKEND)
    import algorithm.design_pipeline as dp
    from algorithm.scoring import gc_skew_score
    original = dp.score_candidate

    def recorder(c, stemloop, reverse, params, **kw):
        res = original(c, stemloop, reverse, params, **kw)
        scores = {k: v for k, v in res["scores"].items() if isinstance(v, (int, float))}
        scores["gc_skew"] = gc_skew_score(c["sequence"])
        # the last call per sequence is the final fixpoint batch
        _pool_rec[c["sequence"]] = {"seq": c["sequence"], "tm_full": c.get("tm_full"),
                                    "specific_length": c.get("specific_length"),
                                    "scores": scores}
        return res

    dp.score_candidate = recorder
    from app import app
    app.config["TESTING"] = True
    _client = app.test_client()


def _design(item):
    name, dna = item
    _pool_rec.clear()
    body = {"thermodynamic": {}, "primerConstraints": {}, "qpcr": {},
            "detectionMethod": {}, "experimentalContext": {},
            "sequence": {"matureSequence": dna.replace("T", "U"), "mirnaId": name}}
    r = _client.post("/api/design", json=body)
    d = r.get_json(silent=True) or {}
    top = (d.get("top3") or [{}])[0]
    from algorithm.constants import TM_ANNEALING_TEMP_DEFAULT   # empty request → default Ta
    return {"mirna": name, "status": r.status_code, "api_top1": top.get("sequence"),
            "ta": float(TM_ANNEALING_TEMP_DEFAULT),
            "pool": list(_pool_rec.values())}


# ── offline ranking ────────────────────────────────────────────────
def total(scores: dict, w: dict, unscored: frozenset) -> float:
    keys = [k for k in w if k not in unscored and isinstance(scores.get(k), (int, float))]
    ws = sum(w[k] for k in keys)
    return round(sum(scores[k] * w[k] for k in keys) / ws, 1)


def ranked(pool: list, w: dict, unscored: frozenset, ta: float) -> list:
    return sorted(pool, key=lambda c: (-total(c["scores"], w, unscored),
                                       abs((c["tm_full"] or 0) - ta), c["seq"]))


def analyse(recs: list, active: dict, unscored: frozenset) -> dict:
    recs = [r for r in recs if r["status"] == 200 and r["pool"] and r["api_top1"]]
    n = len(recs)
    agree = sum(ranked(r["pool"], active, unscored, r["ta"])[0]["seq"] == r["api_top1"]
                for r in recs)

    variability = {}
    for k in [k for k in V4_370 if k not in unscored]:
        in_pool = in_top5 = 0
        for r in recs:
            in_pool += len({c["scores"].get(k) for c in r["pool"]}) > 1
            top5 = ranked(r["pool"], V4_370, unscored, r["ta"])[:5]
            in_top5 += len({c["scores"].get(k) for c in top5}) > 1
        variability[k] = {"pools_where_it_varies_pct": round(100 * in_pool / n, 1),
                          "top5_where_it_varies_pct": round(100 * in_top5 / n, 1)}

    ref = {r["mirna"]: ranked(r["pool"], V4_370, unscored, r["ta"]) for r in recs}
    margins = [total(v[0]["scores"], V4_370, unscored) - total(v[1]["scores"], V4_370, unscored)
               for v in ref.values() if len(v) > 1]

    options = {}
    for name, w in OPTIONS.items():
        tops = [ranked(r["pool"], w, unscored, r["ta"])[0] for r in recs]
        sc = lambda key: [t["scores"].get(key) for t in tops]       # noqa: E731
        sl = [t["specific_length"] for t in tops]
        options[name] = {
            "weights": w,
            "top1_changed_vs_370": sum(t["seq"] != ref[r["mirna"]][0]["seq"]
                                       for t, r in zip(tops, recs)),
            "top1_gc_clamp_below_100": sum(v < 100 for v in sc("gc_clamp")),
            "top1_gc_clamp_le_50": sum(v <= 50 for v in sc("gc_clamp")),
            "top1_tm_accuracy_below_100": sum(v < 100 for v in sc("tm_accuracy")),
            "top1_gc_skew_score_below_70": sum(v < 70 for v in sc("gc_skew")),
            "top1_dimer_penalty_below_100": sum(v < 100 for v in sc("dimer_penalty")),
            "top1_family_co_amplified": sum(v == 0 for v in sc("family_discrimination")),
            "top1_mean_specific_length": round(st.mean(sl), 2),
            "top1_specific_length_ge_15": sum(x >= 15 for x in sl),
            "top1_mean_tm_binding_accuracy": round(st.mean(sc("tm_binding_accuracy")), 1),
            "top1_with_G4_motif": sum(bool(G4_MOTIF.search(t["seq"])) for t in tops),
        }
    return {
        "designs_with_pool": n,
        "offline_top1_equals_api_top1": agree,
        "candidates_total": sum(len(r["pool"]) for r in recs),
        "candidates_with_G4_motif": sum(bool(G4_MOTIF.search(c["seq"]))
                                        for r in recs for c in r["pool"]),
        "margin_top1_minus_top2_under_370": {
            "median": st.median(margins), "le_0_5": sum(m <= 0.5 for m in margins),
            "n": len(margins)},
        "criterion_variability_under_370": variability,
        "options": options,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=os.path.join(ROOT, "benchmark",
                                                           "scoring_weight_sensitivity.json"))
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    sys.path.insert(0, ROOT)
    sys.path.insert(0, BACKEND)
    from crossreactivity.model import load_mature
    from algorithm.constants import ALGORITHM_VERSION, SCORING_WEIGHTS_V4, UNSCORED_CRITERIA_V4

    mature = load_mature(os.path.join(BACKEND, "data", "mirbase_overhang_index.json"), "hsa")
    items = sorted(mature.items())[: a.limit]
    t0 = time.time()
    recs = []
    with mp.Pool(a.workers, initializer=_init_worker) as pool:
        for i, rec in enumerate(pool.imap_unordered(_design, items, chunksize=4), 1):
            recs.append(rec)
            if i % 500 == 0 or i == len(items):
                print(f"  {i}/{len(items)}  {time.time() - t0:.0f}s", flush=True)

    out = {
        "generated_by": "backend/scripts/scoring_weight_sensitivity.py",
        "run_date": time.strftime("%Y-%m-%d"),
        "algorithm_version": ALGORITHM_VERSION,
        "species": "hsa", "mirbase_release": "22.1", "mirnas": len(items),
        "design_request": "empty parameter groups (backend defaults)",
        "active_weights": SCORING_WEIGHTS_V4,
        "note": ("Offline re-ranking of recorded pools. 'top1_changed_vs_370' counts designs "
                 "whose #1 differs from the #1 under the 3.7.0 table. Counts describe the "
                 "ranking, not wet-lab outcomes."),
        **analyse(recs, SCORING_WEIGHTS_V4, frozenset(UNSCORED_CRITERIA_V4)),
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"wrote {a.out}: {out['designs_with_pool']} designs, offline #1 == API #1 for "
          f"{out['offline_top1_equals_api_top1']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
