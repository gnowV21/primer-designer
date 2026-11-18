"""
scripts/tiered_stage2b_report.py — Giai đoạn 2b of docs/SPEC_scoring_tiered_4.0.0.md:
measure QD 29 (one-sided F4 floor, F3 report-only) and QD 30 (grade by tiers) behind
their flags, and the QD 32 / Kết quả numbers, on all 2472 hsa designs WITH BLAST.

    python backend/scripts/tiered_stage2b_report.py [--out benchmark/tiered_stage2b_report.json]

Inputs (no new BLAST; the cache of Giai đoạn 2):
  outputs/freeze_cache/tiered_pools_hsa.jsonl.gz       (tiered_scoring_dryrun.py record)
  outputs/freeze_cache/tiered_blast_full_hsa.jsonl.gz  (tiered_stage2_report.py blast)
Ranking = algorithm/tiered_scoring.py + select_diverse_top, exactly as the pipeline
(the pipeline matches this offline ranking on 20/20 timed designs, SPEC §10).

Writes benchmark/tiered_stage2b_report.json and benchmark/tiered_fallback_list.csv.
Systems compared: "v4" (3.8.2 API #1), "tiered" (4.0.0 as in Giai đoạn 2: F3 + two-sided
F4), "qd29" (F4 floor, no F3).
"""
import argparse
import csv
import gzip
import json
import os
import statistics as st
import sys
from collections import Counter, defaultdict

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "scripts"))
OUT = os.path.join(ROOT, "benchmark", "tiered_stage2b_report.json")
CSV_OUT = os.path.join(ROOT, "benchmark", "tiered_fallback_list.csv")
SYSTEMS = (("tiered", False), ("qd29", True))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    os.chdir(BACKEND)
    import warnings
    warnings.filterwarnings("ignore")
    import tiered_stage2_report as S2
    from algorithm import tiered_scoring as ts
    from algorithm.forward_primer import select_diverse_top
    from algorithm.constants import CANDIDATES_TOP_N, TM_BINDING_TARGET
    from algorithm.scoring import _grade
    from algorithm.specificity_check.assay_model import variant_category
    from algorithm.specificity_check.family_crossreactivity import get_family_id
    from algorithm.specificity_check.overhang_collision import _load_index

    if not os.path.exists(S2.BLAST_FULL):
        raise SystemExit(f"{S2.BLAST_FULL} missing — run tiered_stage2_report.py blast (QD 24e)")
    bl = {}
    with gzip.open(S2.BLAST_FULL, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["error"]:
                raise SystemExit(f"BLAST failed for {r['mirna']} (QD 24e)")
            bl[r["mirna"]] = r["results"]
    recs = [r for r in S2._load_pools() if any(m["in_tiered_pool"] for m in r["candidates"])]
    hsa = {k: v.upper().replace("U", "T") for k, v in _load_index()["mature"]["hsa"].items()}
    dist, v4rules = S2._dist, S2._v4_rules

    def metrics(rec, m):
        mm = dict(m)
        x = bl[rec["mirna"]].get(m["sequence"])
        mm["blast_risk"] = x["risk"] if x else None
        mm["blast_medium_hits"] = x["n_medium"] if x else 0
        mm["blast_worst"] = x["worst"] if x else None
        return mm

    def tiers(m, r):
        return {"S": r["specificity"]["total"], "veto": r["structure_veto"], "P": r["pcr"]["total"],
                "F": r["flexible"]["total"], "detail": r["detailed_score"],
                "tm": abs(m["tm_full"] - m["ta"]), "seq": m["sequence"]}

    def decided_by(a, b):
        for k in ("S", "veto", "P", "F", "detail", "tm"):
            if a[k] != b[k]:
                return k
        return "sequence"

    # ── rank every design under each system (+ the QD 32 simulation) ──
    R = {}
    for name, floor in SYSTEMS:
        per = {}
        for rec in recs:
            sc = [(mm, ts.score(mm, floor)) for mm in
                  (metrics(rec, m) for m in rec["candidates"] if m["in_tiered_pool"])]
            res = ts.rank(sc)
            pseudo = [{"specific_length": m["specific_length"], "sequence": m["sequence"],
                       "_m": m, "_r": r} for m, r in res["ranked"]]
            top = select_diverse_top(pseudo, CANDIDATES_TOP_N)
            # QD 32 simulation (not applied): same S total → a candidate breaking no V4
            # rule ranks first (after the veto).
            sim = sorted(res["ranked"], key=lambda c: (
                -c[1]["specificity"]["total"], c[1]["structure_veto"], bool(v4rules(c[0])),
                -c[1]["pcr"]["total"], -c[1]["flexible"]["total"], -c[1]["detailed_score"],
                abs(c[0]["tm_full"] - c[0]["ta"]), c[0]["sequence"]))
            per[rec["mirna"]] = {"res": res, "top": top, "sim_top1": sim[0],
                                 "by_seq": {m["sequence"]: (m, r) for m, r in sc},
                                 "f4_varies": len({r["flexible"]["binding_tm"] for _, r in sc}) > 1}
        R[name] = per

    v4_top1 = {}
    missing_v4_blast = 0
    for rec in recs:
        if rec["v4"]["top3"]:
            s = rec["v4"]["top3"][0]
            m = next(c for c in rec["candidates"] if c["sequence"] == s)
            if s not in bl[rec["mirna"]]:
                missing_v4_blast += 1
            v4_top1[rec["mirna"]] = metrics(rec, m)
    v4_failed = {r["mirna"] for r in recs if r["v4"]["failed"]}
    out = {"spec": "docs/SPEC_scoring_tiered_4.0.0.md Giai đoạn 2b (QD 29, 30, 32)",
           "designs": len(recs), "designs_with_v4_top1": len(v4_top1),
           "v4_top1_without_blast_result": missing_v4_blast}

    # ── 1. QD 29 vs tiered vs V4 ──
    def top1(name, n):
        t = R[name][n]["top"][0]
        return t["_m"], t["_r"]

    def summary_top1(get):
        L, tb = [], []
        for n in v4_top1:
            m = get(n)
            L.append(m["specific_length"]); tb.append(m["tm_binding"])
        return {"specific_length": dict(sorted(Counter(L).items())),
                "mean_specific_length": round(st.mean(L), 2),
                "binding_tm_c": dist(tb),
                "pct_binding_tm_below_45": round(100 * sum(x < TM_BINDING_TARGET for x in tb) / len(tb), 1),
                "f4_floor_level": dict(sorted(Counter(ts.f4_binding_tm_floor(x) for x in tb).items()))}

    item1 = {"v4_382": summary_top1(lambda n: v4_top1[n])}
    for name, floor in SYSTEMS:
        per = R[name]
        s = summary_top1(lambda n: top1(name, n)[0])
        s["top1_changed_vs_v4_382"] = sum(top1(name, n)[0]["sequence"] != v4_top1[n]["sequence"] for n in v4_top1)
        if name != "tiered":
            s["top1_changed_vs_tiered"] = sum(top1(name, n)[0]["sequence"] != top1("tiered", n)[0]["sequence"]
                                              for n in per)
        s["top1_f4_level"] = dict(sorted(Counter(top1(name, n)[1]["flexible"]["binding_tm"] for n in per).items()))
        s["top1_f4_level_floor_scale"] = dict(sorted(Counter(
            ts.f4_binding_tm_floor(top1(name, n)[0]["tm_binding"]) for n in per).items()))
        s["pct_designs_f4_varies"] = round(100 * sum(p["f4_varies"] for p in per.values()) / len(per), 1)
        dec = Counter()
        for p in per.values():
            rk = p["res"]["ranked"]
            if len(rk) > 1:
                dec[decided_by(tiers(*rk[0]), tiers(*rk[1]))] += 1
        s["top1_vs_top2_decided_by"] = dict(dec.most_common())
        s["specificity_fallback"] = sum(p["res"]["specificity_fallback"] for p in per.values())
        s["top1_structure_veto"] = sum(p["top"][0]["_r"]["structure_veto"] for p in per.values())
        item1[name] = s
    out["item1_qd29"] = item1

    # ── 2. QD 30 grades ──
    item2 = {}
    for name, _ in SYSTEMS:
        per = R[name]
        new = {n: ts.grade_tiers(p["top"][0]["_r"], p["res"]["specificity_fallback"])
               for n, p in per.items()}
        old = {n: _grade(p["top"][0]["_r"]["detailed_score"]) for n, p in per.items()}
        cross = defaultdict(Counter)
        for n in per:
            cross[old[n]][new[n]["grade"]] += 1
        reasons = Counter(r.split(" (")[0].split(":")[0] for g in new.values() for r in g["reasons"])
        item2[name] = {"top1_grade": dict(sorted(Counter(g["grade"] for g in new.values()).items())),
                       "old_detailed_grade_x_new_grade": {k: dict(v) for k, v in cross.items()},
                       "old_excellent_now_c": cross["Excellent"]["C"],
                       "grade_reasons_count": dict(reasons.most_common())}
    out["item2_qd30"] = item2

    # ── 3. S1 of the V4 #1 vs the tiered #1 ──
    def s1(m):
        return ts.s1_blast(m["blast_risk"], m["blast_medium_hits"])
    v4_s1 = {n: s1(m) for n, m in v4_top1.items()}
    item3 = {"v4_top1_s1_level": dict(sorted(Counter(v4_s1.values()).items(), key=lambda x: (x[0] is None, x[0] or 0))),
             "v4_top1_blast_risk": dict(Counter(m["blast_risk"] for m in v4_top1.values()).most_common())}
    for name, _ in SYSTEMS:
        t_s1 = {n: top1(name, n)[1]["specificity"]["blast"] for n in v4_top1}
        low = [n for n in v4_top1 if v4_s1[n] is not None and v4_s1[n] <= 2]
        better = [n for n in low if t_s1[n] is not None and t_s1[n] > v4_s1[n]]
        trans = Counter((v4_s1[n], t_s1[n]) for n in low)
        item3[name] = {
            "tiered_top1_s1_level": dict(sorted(Counter(t_s1.values()).items(), key=lambda x: (x[0] is None, x[0] or 0))),
            "v4_top1_s1_le_2": len(low),
            "of_which_tiered_top1_s1_higher": len(better),
            "transitions_v4_to_tiered": {f"{a}->{b}": c for (a, b), c in sorted(trans.items())},
            "v4_top1_eliminated_in_tiered": sum(R[name][n]["by_seq"][v4_top1[n]["sequence"]][1]["eliminated"]
                                                for n in v4_top1 if v4_top1[n]["sequence"] in R[name][n]["by_seq"]),
            "designs_s_total_higher_than_v4": sum(
                top1(name, n)[1]["specificity"]["total"]
                > R[name][n]["by_seq"][v4_top1[n]["sequence"]][1]["specificity"]["total"]
                for n in v4_top1),
            "mirnas_v4_s1_le_2_improved": sorted(better),
        }
    out["item3_s1_v4_vs_tiered"] = item3

    # ── 4. QD 32: tiered #1 breaks a V4 rule, V4 #1 does not ──
    item4 = {}
    for name, floor in SYSTEMS:
        per = R[name]
        rows = []
        for n, v in v4_top1.items():
            if n in v4_failed:
                continue
            tm, tr = top1(name, n)
            tv, vv = v4rules(tm), v4rules(v)
            if not tv or vv:
                continue
            vr = per[n]["by_seq"][v["sequence"]][1]
            rows.append((n, tm, tr, tv, v, vr))
        pos = [x for x in rows if x[2]["specificity"]["total"] > x[5]["specificity"]["total"]]
        zero = [x for x in rows if x[2]["specificity"]["total"] == x[5]["specificity"]["total"]]
        neg = [x for x in rows if x[2]["specificity"]["total"] < x[5]["specificity"]["total"]]
        zero_dec = Counter(decided_by(tiers(x[1], x[2]), tiers(x[4], x[5])) for x in zero)
        dg = [x[1]["dimer_dg"] for x in zero if "hard_dimer_full_dg" in x[3]]
        dg_pos = [x[1]["dimer_dg"] for x in pos if "hard_dimer_full_dg" in x[3]]
        # simulation
        changed, d_s1, d_s3, compliant = 0, Counter(), Counter(), 0
        for n, p in per.items():
            base_m, base_r = p["top"][0]["_m"], p["top"][0]["_r"]
            sm, sr = p["sim_top1"]
            if sm["sequence"] != base_m["sequence"]:
                changed += 1
                d_s1[(sr["specificity"]["blast"] or 0) - (base_r["specificity"]["blast"] or 0)] += 1
                d_s3[sr["specificity"]["tm_margin"] - base_r["specificity"]["tm_margin"]] += 1
                compliant += not v4rules(sm)
        item4[name] = {
            "designs_tiered_breaks_v4_does_not": len(rows),
            "delta_S_gt_0": {"n": len(pos), "rules": dict(Counter(r for x in pos for r in x[3]).most_common()),
                             "delta_S": dict(sorted(Counter(x[2]["specificity"]["total"] - x[5]["specificity"]["total"] for x in pos).items())),
                             "hard_dimer_full_dg_dG": dist(dg_pos)},
            "delta_S_eq_0": {"n": len(zero), "decided_by": dict(zero_dec.most_common()),
                             "rules": dict(Counter(r for x in zero for r in x[3]).most_common()),
                             "rules_by_deciding_tier": {k: dict(Counter(r for x in zero
                                                                         if decided_by(tiers(x[1], x[2]), tiers(x[4], x[5])) == k
                                                                         for r in x[3]).most_common())
                                                        for k in zero_dec},
                             "hard_dimer_full_dg_dG": dist(dg)},
            "delta_S_lt_0": {"n": len(neg), "note": "V4 #1 eliminated (S1 or S2 = 1) in the tiered system",
                             "v4_top1_eliminated": sum(x[5]["eliminated"] for x in neg)},
            "simulation_compliant_first_within_S_not_applied": {
                "top1_changed": changed, "new_top1_breaks_no_v4_rule": compliant,
                "delta_S1_of_top1": dict(sorted(d_s1.items())), "delta_S3_of_top1": dict(sorted(d_s3.items())),
                "note": "S total of #1 unchanged by construction; S1/S3 may trade."},
        }
    out["item4_qd32"] = item4

    # ── 5. specificity_fallback list ──
    def cat(name, other):
        o = hsa.get(other) if other else None
        return variant_category(hsa[name], o) if o and name in hsa else ("" if not other else "unknown")
    rows = []
    for n, p in sorted(R["tiered"].items()):
        if not p["res"]["specificity_fallback"]:
            continue
        sc = list(p["by_seq"].values())
        m, r = p["top"][0]["_m"], p["top"][0]["_r"]
        sp = r["specificity"]
        bad_s1 = sum(x[1]["specificity"]["blast"] == 1 for x in sc)
        bad_s2 = sum(x[1]["specificity"]["assay_dcq"] == 1 for x in sc)
        s2_targets = Counter(x[0]["worst"] for x in sc if x[1]["specificity"]["assay_dcq"] == 1)
        s1_targets = Counter(x[0]["blast_worst"] for x in sc if x[1]["specificity"]["blast"] == 1)
        main_s2 = s2_targets.most_common(1)[0][0] if s2_targets else ""
        main_s1 = s1_targets.most_common(1)[0][0] if s1_targets else ""
        rows.append({
            "mirna": n, "seed_family": get_family_id(n) or "", "candidates": len(sc),
            "candidates_s1_critical": bad_s1, "candidates_s2_coamplified": bad_s2,
            "main_s2_offtarget": main_s2, "main_s2_offtarget_category": cat(n, main_s2),
            "main_s1_offtarget": main_s1, "main_s1_offtarget_category": cat(n, main_s1),
            "top1_sequence": m["sequence"], "top1_specific_length": m["specific_length"],
            "top1_s1": sp["blast"], "top1_blast_risk": m["blast_risk"], "top1_blast_worst": m["blast_worst"] or "",
            "top1_s2": sp["assay_dcq"], "top1_min_delta_cq": m["min_delta_cq"], "top1_s2_worst": m["worst"] or "",
            "top1_s3": sp["tm_margin"], "top1_tm_margin": m["tm_margin"],
            "top1_tm_margin_worst": m["tm_margin_worst"] or "",
            "wetlab_check": (f"co-detection of {main_s2 or main_s1}"
                             + (f" ({cat(n, main_s2 or main_s1)})" if (main_s2 or main_s1) else "")),
        })
    with open(CSV_OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    out["item5_fallback"] = {
        "n": len(rows), "csv": "benchmark/tiered_fallback_list.csv",
        "seed_families": dict(Counter(r["seed_family"] or "(none)" for r in rows).most_common()),
        "main_s2_offtarget_category": dict(Counter(r["main_s2_offtarget_category"] or "(S2 not eliminating)" for r in rows).most_common()),
        "main_s1_offtarget_category": dict(Counter(r["main_s1_offtarget_category"] or "(S1 not eliminating)" for r in rows).most_common()),
        "eliminated_by": dict(Counter(("S1" if r["candidates_s1_critical"] else "") + ("+" if r["candidates_s1_critical"] and r["candidates_s2_coamplified"] else "")
                                      + ("S2" if r["candidates_s2_coamplified"] else "") for r in rows).most_common()),
        "same_list_under_qd29": sorted(r["mirna"] for r in rows) == sorted(
            n for n, p in R["qd29"].items() if p["res"]["specificity_fallback"]),
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(json.dumps(out, indent=1, ensure_ascii=False)[:20000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
