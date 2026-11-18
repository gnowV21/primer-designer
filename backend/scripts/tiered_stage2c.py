"""
scripts/tiered_stage2c.py — Giai đoạn 2c of docs/SPEC_scoring_tiered_4.0.0.md (QD 33–37).

    python backend/scripts/tiered_stage2c.py offline         [--out benchmark/tiered_stage2c_report.json]
    python backend/scripts/tiered_stage2c.py pipeline-check  [--log benchmark/logs/stage2c_pipeline_check.log]

offline — QD 36 acceptance and the 4-column comparison (V4 3.8.2 | tiered Giai đoạn 2 |
          QD 29 | final = QD 29 + 33 + 34 + 36), plus "final without QD 36" for the
          acceptance. Ranks the recorded pools (outputs/freeze_cache/tiered_pools_hsa.jsonl.gz)
          with algorithm/tiered_scoring.py, S1 of every candidate from the Giai đoạn 2
          BLAST run (outputs/freeze_cache/tiered_blast_full_hsa.jsonl.gz; QD 37 way a).
          Every table is given on all 2472 designs and on the 2253 V4 also designed.
pipeline-check — the 20 miRNAs of benchmark/tiered_design_timing.json (random.Random(2026))
          through the real pipeline (real BLAST, sqlite cache on), twice: the top 3 must
          equal the offline final top 3 (20/20), and the two runs must be identical.
"""
import argparse
import datetime as dt
import gzip
import json
import os
import statistics as st
import subprocess
import sys
from collections import Counter, defaultdict

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "scripts"))
OUT = os.path.join(ROOT, "benchmark", "tiered_stage2c_report.json")

_A25, _A35 = ((25.0, 0.0), (45.0, 100.0)), ((35.0, 0.0), (45.0, 100.0))
# system → F4 floor (QD 29), detailed binding-Tm anchors (QD 33), V4-compliant first
# (QD 34), binding-floor veto (QD 36)
SYSTEMS = {
    "tiered_g2":          dict(floor=False, anchors=_A35, v4first=False, floorveto=False),
    "qd29":               dict(floor=True, anchors=_A35, v4first=False, floorveto=False),
    "final_without_qd36": dict(floor=True, anchors=_A25, v4first=True, floorveto=False),
    "final":              dict(floor=True, anchors=_A25, v4first=True, floorveto=True),
}


def _setup():
    os.chdir(BACKEND)
    import warnings
    warnings.filterwarnings("ignore")


def offline(a):
    _setup()
    import tiered_stage2_report as S2
    from algorithm import constants as K
    from algorithm import tiered_scoring as ts
    from algorithm.forward_primer import select_diverse_top
    from algorithm.constants import CANDIDATES_TOP_N, TM_BINDING_TARGET
    dist, v4rules = S2._dist, S2._v4_rules

    bl = {}
    with gzip.open(S2.BLAST_FULL, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["error"]:
                raise SystemExit(f"BLAST failed for {r['mirna']} (QD 24e)")
            bl[r["mirna"]] = r["results"]
    recs = [r for r in S2._load_pools() if any(m["in_tiered_pool"] for m in r["candidates"])]
    pools = {}
    for rec in recs:
        ms = []
        for m in rec["candidates"]:
            if m["in_tiered_pool"]:
                x = bl[rec["mirna"]][m["sequence"]]
                ms.append({**m, "blast_risk": x["risk"], "blast_medium_hits": x["n_medium"],
                           "blast_worst": x["worst"], "v4_violation": bool(v4rules(m))})
        pools[rec["mirna"]] = ms
    v4_top1 = {}
    for rec in recs:
        if rec["v4"]["top3"]:
            m = next(c for c in rec["candidates"] if c["sequence"] == rec["v4"]["top3"][0])
            x = bl[rec["mirna"]].get(m["sequence"])
            v4_top1[rec["mirna"]] = {**m, "blast_risk": x["risk"], "blast_medium_hits": x["n_medium"],
                                     "v4_violation": bool(v4rules(m))}
    ALL, V4SET = sorted(pools), sorted(v4_top1)

    real = (ts.TIERED_DETAIL_TM_BINDING_FLOOR, K.TIERED_BINDING_FLOOR_VETO)
    R = {}
    for name, cfg in SYSTEMS.items():
        ts.TIERED_DETAIL_TM_BINDING_FLOOR = cfg["anchors"]
        K.TIERED_BINDING_FLOOR_VETO = cfg["floorveto"]           # grade reason follows the system
        per = {}
        for n, ms in pools.items():
            sc = [(m, ts.score(m, cfg["floor"])) for m in ms]
            res = ts.rank(sc, v4_compliant_first=cfg["v4first"], binding_floor_veto=cfg["floorveto"])
            pseudo = [{"specific_length": m["specific_length"], "sequence": m["sequence"], "_m": m, "_r": r}
                      for m, r in res["ranked"]]
            top = select_diverse_top(pseudo, CANDIDATES_TOP_N)
            per[n] = {"res": res, "top": top, "grade": ts.grade_tiers(top[0]["_r"], res["specificity_fallback"]),
                      "by_seq": {m["sequence"]: (m, r) for m, r in sc}}
        R[name] = (cfg, per)
        # the V4 #1 scored under this system (for ΔS)
    ts.TIERED_DETAIL_TM_BINDING_FLOOR, K.TIERED_BINDING_FLOOR_VETO = real

    def t1(name, n):
        return R[name][1][n]["top"][0]

    def key_parts(m, r, cfg):
        return {"S": r["specificity"]["total"], "structure_veto": r["structure_veto"],
                "binding_floor_veto": bool(r["binding_floor_fail"]) and cfg["floorveto"],
                "v4_rule": bool(m["v4_violation"]) and cfg["v4first"],
                "P": r["pcr"]["total"], "F": r["flexible"]["total"], "detail": r["detailed_score"],
                "tm": abs(m["tm_full"] - m["ta"])}

    def decided(a_, b_):
        for k in a_:
            if a_[k] != b_[k]:
                return k
        return "sequence"

    def column(name, names):
        """One column of the comparison, over `names` (denominator = len(names))."""
        if name == "v4_382":
            ms = [v4_top1[n] for n in names]
        else:
            ms = [t1(name, n)["_m"] for n in names]
        tb = [m["tm_binding"] for m in ms]
        L = [m["specific_length"] for m in ms]
        col = {"denominator": len(names),
               "mean_specific_length": round(st.mean(L), 2),
               "specific_length": dict(sorted(Counter(L).items())),
               "binding_tm_median": round(st.median(tb), 1),
               "binding_tm_p05_p95": [dist(tb)["p05"], dist(tb)["p95"]],
               "pct_binding_tm_below_45": round(100 * sum(x < TM_BINDING_TARGET for x in tb) / len(tb), 1),
               "f4_floor_level": dict(sorted(Counter(ts.f4_binding_tm_floor(x) for x in tb).items())),
               "top1_breaks_v4_rule": sum(bool(v4rules(m)) for m in ms)}
        s1 = ([ts.s1_blast(m["blast_risk"], m["blast_medium_hits"]) for m in ms] if name == "v4_382"
              else [t1(name, n)["_r"]["specificity"]["blast"] for n in names])
        col["top1_s1_level"] = dict(sorted(Counter(s1).items()))
        dcq = [m["min_delta_cq"] for m in ms]
        col["top1_s2_level"] = dict(sorted(Counter(ts.s2_assay_dcq(x) for x in dcq).items()))
        col["top1_min_delta_cq"] = {"ge_10_cq (None)": sum(x is None for x in dcq),
                                    "below_10": dist([x for x in dcq if x is not None])}
        if name != "v4_382":
            cfg, per = R[name]
            col["top1_changed_vs_v4"] = sum(t1(name, n)["_m"]["sequence"] != v4_top1[n]["sequence"]
                                            for n in names if n in v4_top1)
            col["top1_changed_vs_final_without_qd36"] = sum(
                t1(name, n)["_m"]["sequence"] != t1("final_without_qd36", n)["_m"]["sequence"] for n in names)
            dec = Counter()
            for n in names:
                rk = per[n]["res"]["ranked"]
                if len(rk) > 1:
                    dec[decided(key_parts(*rk[0], cfg), key_parts(*rk[1], cfg))] += 1
            col["top1_vs_top2_decided_by"] = dict(dec.most_common())
            g = Counter(per[n]["grade"]["grade"] for n in names)
            col["grade"] = dict(sorted(g.items()))
            col["grade_reasons"] = dict(Counter(x.split(" (")[0] for n in names
                                                for x in per[n]["grade"]["reasons"]).most_common())
            col["specificity_fallback"] = sum(per[n]["res"]["specificity_fallback"] for n in names)
            col["designs_with_eliminated"] = sum(per[n]["res"]["eliminated"] > 0 for n in names)
            col["fewer_than_3_sets"] = sum(len(per[n]["top"]) < CANDIDATES_TOP_N for n in names)
            col["top1_structure_veto"] = sum(t1(name, n)["_r"]["structure_veto"] for n in names)
            col["top1_binding_floor_fail"] = sum(bool(t1(name, n)["_r"]["binding_floor_fail"]) for n in names)
            # S1 improvement over the V4 #1
            low = [n for n in names if n in v4_top1
                   and (ts.s1_blast(v4_top1[n]["blast_risk"], v4_top1[n]["blast_medium_hits"]) or 9) <= 2]
            col["v4_top1_s1_le_2"] = len(low)
            col["of_which_top1_s1_higher"] = sum(
                (t1(name, n)["_r"]["specificity"]["blast"] or 0)
                > ts.s1_blast(v4_top1[n]["blast_risk"], v4_top1[n]["blast_medium_hits"]) for n in low)
            # QD 32: #1 breaks a V4 rule while the V4 #1 does not (V4-failed designs excluded)
            rows = []
            for n in names:
                if n not in v4_top1:
                    continue
                tm, tr = t1(name, n)["_m"], t1(name, n)["_r"]
                if v4rules(tm) and not v4rules(v4_top1[n]):
                    vr = per[n]["by_seq"][v4_top1[n]["sequence"]][1]
                    rows.append((tr["specificity"]["total"] - vr["specificity"]["total"], v4rules(tm),
                                 decided(key_parts(tm, tr, cfg), key_parts(v4_top1[n], vr, cfg))))
            col["v4_rule_breaks_vs_v4_top1"] = {
                "n": len(rows),
                "by_delta_S": {f"{k:+d}" if k else "0": c for k, c in sorted(Counter(x[0] for x in rows).items())},
                "rules_delta_S_gt_0": dict(Counter(r for x in rows if x[0] > 0 for r in x[1]).most_common()),
                "rules_delta_S_eq_0": dict(Counter(r for x in rows if x[0] == 0 for r in x[1]).most_common()),
                "delta_S_eq_0_decided_by": dict(Counter(x[2] for x in rows if x[0] == 0).most_common()),
            }
        return col

    out = {"spec": "docs/SPEC_scoring_tiered_4.0.0.md Giai đoạn 2c (QD 33–37)",
           "source": {"pools": "outputs/freeze_cache/tiered_pools_hsa.jsonl.gz",
                      "blast": "outputs/freeze_cache/tiered_blast_full_hsa.jsonl.gz (Giai đoạn 2, "
                               "batched BLAST of every pool candidate; QD 37 way a)",
                      "v4": "outputs/freeze_cache/pools_hsa_3.8.2.jsonl.gz (3.8.2 API #1)"},
           "configs": {k: {**v, "anchors": list(v["anchors"])} for k, v in SYSTEMS.items()}}
    cols = ("v4_382", "tiered_g2", "qd29", "final_without_qd36", "final")
    out["table_2472"] = {c: column(c, ALL) for c in cols if c != "v4_382"}
    out["table_2253"] = {c: column(c, V4SET) for c in cols}

    # QD 36 acceptance
    unavoidable = 0
    for n in ALL:
        cfg, per = R["final"]
        rk = per[n]["res"]["ranked"]
        g0 = (rk[0][1]["specificity"]["total"], rk[0][1]["structure_veto"])
        grp = [(m, r) for m, r in rk if (r["specificity"]["total"], r["structure_veto"]) == g0]
        unavoidable += not any(ts.f4_binding_tm_floor(m["tm_binding"]) >= 2 for m, _ in grp)
    f4_1 = sum(bool(t1("final", n)["_r"]["binding_floor_fail"]) for n in ALL)
    comp = Counter()
    for n in ALL:
        a_ = t1("final_without_qd36", n)["_r"]["specificity"]
        b_ = t1("final", n)["_r"]["specificity"]
        for k in ("blast", "assay_dcq", "tm_margin"):
            comp[k] += a_[k] != b_[k]
    out["qd36_acceptance"] = {
        "denominator": len(ALL),
        "top1_f4_level_1": f4_1,
        "designs_best_S_veto_group_without_f4_ge_2": unavoidable,
        "avoidable": f4_1 - unavoidable,
        "s1_s2_s3_of_top1_changed_vs_without_qd36": dict(comp),
        "top1_changed_vs_without_qd36": sum(t1("final", n)["_m"]["sequence"]
                                            != t1("final_without_qd36", n)["_m"]["sequence"] for n in ALL),
        "pass": f4_1 == unavoidable and not any(comp.values()),
    }
    out["final_top3"] = {n: [c["sequence"] for c in R["final"][1][n]["top"]] for n in ALL}
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(json.dumps(out["qd36_acceptance"], indent=1, ensure_ascii=False))
    return 0 if out["qd36_acceptance"]["pass"] else 1


def pipeline_check(a):
    _setup()
    from algorithm import constants as K
    from algorithm.design_pipeline import run
    from algorithm.specificity_check.overhang_collision import _load_index
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    log = open(a.log, "a", encoding="utf-8")

    def say(x):
        print(x, flush=True)
        log.write(x + "\n"); log.flush()
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    say(f"START {dt.datetime.now().isoformat(timespec='seconds')} git {sha} algorithm {K.ALGORITHM_VERSION} "
        f"flags " + json.dumps({f: getattr(K, f) for f in dir(K) if f.startswith("TIERED_") and isinstance(getattr(K, f), bool)}))
    rep = json.load(open(OUT, encoding="utf-8"))["final_top3"]
    names = [r["mirna"] for r in json.load(open(os.path.join(ROOT, "benchmark", "tiered_design_timing.json"),
                                                 encoding="utf-8"))["designs"]]
    hsa = _load_index()["mature"]["hsa"]

    def strip(d):
        rs = {k: v for k, v in (d.get("ranking_summary") or {}).items()
              if k not in ("timing_ms", "blast_cache_hits")}
        return json.dumps({"top3": d["top3"], "ranking_summary": rs, "warnings": d["global_warnings"],
                           "overhang_suggestion": d.get("overhang_suggestion")}, sort_keys=True, default=str)
    runs = []
    for i in (1, 2):
        res, hits, cands = {}, 0, 0
        for n in names:
            d = run(hsa[n].upper().replace("T", "U"), {}, n)
            res[n] = d
            hits += d["ranking_summary"]["blast_cache_hits"]
            cands += d["ranking_summary"]["blast_candidates"]
        say(f"run {i}: cache hits {hits}/{cands}")
        runs.append(res)
    match = [n for n in names if [s["sequence"] for s in runs[0][n]["top3"]] == rep[n]]
    same = [n for n in names if strip(runs[0][n]) == strip(runs[1][n])]
    out = {"designs": len(names), "top3_equal_offline": len(match),
           "mismatch": {n: {"pipeline": [s["sequence"] for s in runs[0][n]["top3"]], "offline": rep[n]}
                        for n in names if n not in match},
           "deterministic_identical": len(same),
           "pass": len(match) == len(names) and len(same) == len(names)}
    say("RESULT " + json.dumps(out, ensure_ascii=False))
    return 0 if out["pass"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("offline")
    o.add_argument("--out", default=OUT)
    p = sub.add_parser("pipeline-check")
    p.add_argument("--log", default=os.path.join(ROOT, "benchmark", "logs", "stage2c_pipeline_check.log"))
    a = ap.parse_args(argv)
    return {"offline": offline, "pipeline-check": pipeline_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
