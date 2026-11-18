"""freeze_criterion_variation.py — which tiered criteria actually separate candidates.

docs/THESIS_FREEZE_4.0.0.md "biến thiên tiêu chí" (PROMPT Phần 4.2), the 4.0.0
counterpart of the V4 analysis in benchmark/thesis_freeze_impact.json.

Input: the recorded hsa candidate pools + full BLAST summaries of Giai đoạn 2
(outputs/freeze_cache/, the data that reproduces the API #1 in 2472/2472 designs,
SPEC_scoring_tiered_4.0.0 §12–13), scored with the shipped configuration.

For every criterion level (S1, S2, S3, P2, F1, F2, F4, F5) and soft veto, per design:
  - varies_in_pool: the level is not the same for every candidate of the tiered pool;
  - varies_in_top_group: it varies among the candidates with the best S total (the
    group the later key steps choose from).
Also the tie-break (detailed score) range inside the top group, and the key step that
decides #1 over #2 of the ranked pool.

Output: benchmark/freeze_criterion_variation.json
Usage (repo root): python backend/scripts/freeze_criterion_variation.py
"""
from __future__ import annotations

import gzip
import json
import os
import statistics as st
import sys
from collections import Counter

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "scripts"))
OUT = os.path.join(ROOT, "benchmark", "freeze_criterion_variation.json")

LEVELS = {
    "S1_blast": lambda r: r["specificity"]["blast"],
    "S2_assay_dcq": lambda r: r["specificity"]["assay_dcq"],
    "S3_tm_margin": lambda r: r["specificity"]["tm_margin"],
    "P2_tm_vs_ta": lambda r: r["pcr"]["tm_vs_ta"],
    "F1_gc": lambda r: r["flexible"]["gc"],
    "F2_gc_clamp": lambda r: r["flexible"]["gc_clamp"],
    "F4_binding_tm_floor": lambda r: r["flexible"]["binding_tm"],
    "F5_structure": lambda r: r["flexible"]["structure"],
    "structure_veto": lambda r: r["structure_veto"],
    "binding_floor_fail": lambda r: bool(r["binding_floor_fail"]),
    "S_total": lambda r: r["specificity"]["total"],
    "P_total": lambda r: r["pcr"]["total"],
    "F_total": lambda r: r["flexible"]["total"],
}


def main() -> int:
    os.chdir(BACKEND)
    import warnings
    warnings.filterwarnings("ignore")
    import tiered_stage2_report as S2
    from algorithm import tiered_scoring as ts

    bl = {}
    with gzip.open(S2.BLAST_FULL, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["error"]:
                raise SystemExit(f"BLAST failed for {r['mirna']}")
            bl[r["mirna"]] = r["results"]
    recs = [r for r in S2._load_pools() if any(m["in_tiered_pool"] for m in r["candidates"])]

    n = 0
    in_pool, in_top = Counter(), Counter()
    detail_range, pool_sizes, top_sizes, decide = [], [], [], Counter()
    for rec in recs:
        ms = []
        for m in rec["candidates"]:
            if m["in_tiered_pool"]:
                x = bl[rec["mirna"]][m["sequence"]]
                ms.append({**m, "blast_risk": x["risk"], "blast_medium_hits": x["n_medium"],
                           "blast_worst": x["worst"], "v4_violation": bool(S2._v4_rules(m))})
        sc = [(m, ts.score(m)) for m in ms]
        res = ts.rank(sc)
        ranked = res["ranked"]
        n += 1
        pool_sizes.append(len(ranked))
        best_s = ranked[0][1]["specificity"]["total"]
        top = [c for c in ranked if c[1]["specificity"]["total"] == best_s]
        top_sizes.append(len(top))
        for k, f in LEVELS.items():
            in_pool[k] += len({f(r) for _, r in ranked}) > 1
            in_top[k] += len({f(r) for _, r in top}) > 1
        d = [r["detailed_score"] for _, r in top]
        detail_range.append(max(d) - min(d))
        if len(ranked) > 1:
            ka, kb = ts.rank_key(*ranked[0]), ts.rank_key(*ranked[1])
            names = ["S_total", "structure_veto", "binding_floor_fail", "v4_violation", "P_total",
                     "F_total", "detailed_score", "tm_vs_ta", "sequence"]
            decide[next((nm for nm, a, b in zip(names, ka, kb) if a != b), "identical")] += 1

    pct = lambda c: {k: {"n": v, "pct": round(100 * v / n, 1)} for k, v in c.items()}  # noqa: E731
    out = {
        "source": "outputs/freeze_cache/tiered_pools_hsa.jsonl.gz + tiered_blast_full_hsa.jsonl.gz",
        "denominator_designs": n,
        "ranked_pool_size_median": st.median(pool_sizes),
        "best_S_group_size_median": st.median(top_sizes),
        "varies_in_pool": pct(in_pool),
        "varies_in_best_S_group": pct(in_top),
        "tie_break_range_in_best_S_group_median": round(st.median(detail_range), 1),
        "deciding_step_ranked_1_vs_2_of_pool": dict(decide.most_common()),
        "note": ("Pool = candidates after the S2 screen, ranked by the shipped key (all four "
                 "TIERED_* flags on). 'Best S group' = candidates with the highest S total; "
                 "the soft vetoes, V4 step, P, F and the tie-break only choose inside it. The "
                 "API #1 vs #2 decision (after select_diverse_top) is in "
                 "benchmark/ui_tier_order_check.json."),
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print(json.dumps({k: out[k] for k in ("denominator_designs", "varies_in_pool",
                                          "varies_in_best_S_group")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
