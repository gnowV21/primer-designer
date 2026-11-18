"""
scripts/tiered_stage2_report.py — end of Giai đoạn 2 of docs/SPEC_scoring_tiered_4.0.0.md:
the implemented tiered ranking, with BLAST (S1) on EVERY hsa design, compared with V4
3.8.2, and the QD 26 indicators.

    python backend/scripts/tiered_stage2_report.py blast   [--workers 14]
    python backend/scripts/tiered_stage2_report.py analyse [--out benchmark/tiered_stage2_report.json]

blast   — check_offtarget_batch (QD 24b; identical to the per-primer check, see
          benchmark/blast_batch_equivalence.json) for every candidate of the tiered pool
          of all 2472 hsa designs that have candidates (pools recorded by
          tiered_scoring_dryrun.py record). Superset of what the pipeline BLASTs (it
          skips S2-eliminated candidates unless every candidate is eliminated), so the
          ranking is the pipeline's. → outputs/freeze_cache/tiered_blast_full_hsa.jsonl.gz
analyse — ranks every design with algorithm/tiered_scoring.py + select_diverse_top,
          with and without S1, and reports:
            QD 26 (1) within-design correlation of F3 (specific length) and F4 (binding Tm)
            QD 26 (2) specific length and binding Tm of #1: V4 3.8.2 vs tiered
            QD 26 (3) in the designs whose #1 changed: is the new #1's binding Tm closer
                      to or further from TM_BINDING_TARGET (45 °C) than V4's
            QD 25     v4_rule_violations of the tiered #1 (incl. the designs V4 failed)
          plus the ranking counts of the dry run, now with S1 for every design.
Fails if BLAST is unavailable or any BLAST call failed (QD 24e).
"""
import argparse
import gzip
import json
import multiprocessing as mp
import os
import statistics as st
import sys
import time
from collections import Counter

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
CACHE = os.path.join(ROOT, "outputs", "freeze_cache")
POOLS = os.path.join(CACHE, "tiered_pools_hsa.jsonl.gz")
BLAST_FULL = os.path.join(CACHE, "tiered_blast_full_hsa.jsonl.gz")
OUT = os.path.join(ROOT, "benchmark", "tiered_stage2_report.json")


def _init():
    sys.path.insert(0, BACKEND)
    os.chdir(BACKEND)
    import warnings
    warnings.filterwarnings("ignore")
    import algorithm.specificity_check.blast_offtarget as bo
    bo.BLAST_BATCH_PROCESSES = 1          # parallel over designs instead (performance only)


def _load_pools():
    with gzip.open(POOLS, "rt", encoding="utf-8") as f:
        return sorted((json.loads(x) for x in f), key=lambda r: r["mirna"])


# ── blast ─────────────────────────────────────────────────────────
def _blast_one(rec):
    from algorithm.specificity_check.blast_offtarget import check_offtarget_batch
    from algorithm.constants import UNIVERSAL_REVERSE
    from algorithm import tiered_scoring as ts
    seqs = [c["sequence"] for c in rec["candidates"] if c["in_tiered_pool"]]
    t = time.perf_counter()
    try:
        res = check_offtarget_batch(seqs, UNIVERSAL_REVERSE, mirna_id=rec["mirna"],
                                    target_sequence=rec["rna"], species="hsa",
                                    rt_primer=rec["rt_primer"])
        out = {}
        for s in seqs:
            risk, n_med, worst = ts.blast_s1_inputs(res[s])
            out[s] = {"risk": risk, "n_medium": n_med, "worst": worst}
        err = None
    except Exception as e:   # noqa: BLE001
        out, err = {}, f"{type(e).__name__}: {e}"
    return {"mirna": rec["mirna"], "results": out, "error": err,
            "seconds": round(time.perf_counter() - t, 2), "n": len(seqs)}


def blast(a):
    _init()
    from algorithm.specificity_check.blast_offtarget import blast_available
    ok, why = blast_available()
    if not ok:
        raise SystemExit(f"BLAST not available: {why} (QD 24e)")
    recs = [r for r in _load_pools() if any(c["in_tiered_pool"] for c in r["candidates"])]
    print(f"BLAST (batched): {len(recs)} designs, "
          f"{sum(sum(c['in_tiered_pool'] for c in r['candidates']) for r in recs)} candidates", flush=True)
    t0, rows = time.time(), []
    with mp.Pool(a.workers, initializer=_init) as p:
        for i, row in enumerate(p.imap_unordered(_blast_one, recs), 1):
            rows.append(row)
            if i % 100 == 0 or i == len(recs):
                print(f"  {i}/{len(recs)}  {time.time() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: r["mirna"])
    with gzip.open(BLAST_FULL, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    n_err = sum(1 for r in rows if r["error"])
    print(f"wrote {BLAST_FULL}; {n_err} designs with errors; wall {time.time() - t0:.0f}s")
    return 1 if n_err else 0


# ── analyse ───────────────────────────────────────────────────────
def _dist(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    q = lambda p: round(xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))], 2)   # noqa: E731
    return {"n": len(xs), "mean": round(st.mean(xs), 2), "p05": q(.05), "p25": q(.25),
            "median": q(.5), "p75": q(.75), "p95": q(.95), "min": xs[0], "max": xs[-1]}


def _pearson(x, y):
    if len(x) < 2:
        return None
    mx, my = st.mean(x), st.mean(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = sum((a - mx) ** 2 for a in x) ** .5
    sy = sum((b - my) ** 2 for b in y) ** .5
    return round(sxy / (sx * sy), 3) if sx and sy else None


def _v4_rules(m):
    """V4 rules broken (tiered_pipeline.v4_rule_violations on the recorded metrics,
    backend defaults): GC pre-filter rules + the three structural hard filters."""
    from algorithm.constants import (GC_MIN, GC_MAX, GC_CLAMP_HARD_MIN_IN_LAST3,
                                     GC_MAX_IN_3PRIME_WINDOW, DIMER_FULL_DG_CRITICAL,
                                     HAIRPIN_TM_HARD_MAX, END_DIMER_TM_HARD_MAX)
    s = m["sequence"].upper()
    out = []
    if not GC_MIN <= m["gc_percent"] <= GC_MAX:
        out.append("gc_out_of_range")
    if sum(b in "GC" for b in s[-3:]) < GC_CLAMP_HARD_MIN_IN_LAST3:
        out.append("gc_clamp_fail")
    if sum(b in "GC" for b in s[-5:]) >= GC_MAX_IN_3PRIME_WINDOW:
        out.append("gc_end_window_fail")
    if m["dimer_dg"] is not None and m["dimer_dg"] < DIMER_FULL_DG_CRITICAL:
        out.append("hard_dimer_full_dg")
    if m["end_dimer_tm"] is not None and m["end_dimer_tm"] >= END_DIMER_TM_HARD_MAX:
        out.append("hard_dimer_3prime_critical")
    if (m["hairpin_tm"] or 0.0) >= HAIRPIN_TM_HARD_MAX:
        out.append("hard_hairpin_tm")
    return out


def analyse(a):
    _init()
    from algorithm import tiered_scoring as ts
    from algorithm.forward_primer import select_diverse_top
    from algorithm.constants import CANDIDATES_TOP_N, TM_BINDING_TARGET, ALGORITHM_VERSION

    if not os.path.exists(BLAST_FULL):
        raise SystemExit(f"{BLAST_FULL} missing — run the blast step (QD 24e)")
    bl = {}
    with gzip.open(BLAST_FULL, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["error"]:
                raise SystemExit(f"BLAST failed for {r['mirna']}: {r['error']} (QD 24e)")
            bl[r["mirna"]] = r["results"]
    recs = _load_pools()

    def rank(rec, with_blast, adjust=None):
        b = bl.get(rec["mirna"], {}) if with_blast else {}
        sc = []
        for m in rec["candidates"]:
            if not m["in_tiered_pool"]:
                continue
            mm = dict(m)
            x = b.get(m["sequence"])
            mm["blast_risk"] = x["risk"] if x else None
            mm["blast_medium_hits"] = x["n_medium"] if x else 0
            r = ts.score(mm)
            sc.append((mm, adjust(r) if adjust else r))
        res = ts.rank(sc)
        pseudo = [{"specific_length": m["specific_length"], "sequence": m["sequence"],
                   "_m": m, "_r": r} for m, r in res["ranked"]]
        return sc, res, select_diverse_top(pseudo, CANDIDATES_TOP_N)

    dev = lambda m: abs(m["tm_binding"] - TM_BINDING_TARGET)   # noqa: E731
    out = {"spec": "docs/SPEC_scoring_tiered_4.0.0.md Giai đoạn 2, QD 25, QD 26",
           "algorithm_version": ALGORITHM_VERSION,
           "source": "outputs/freeze_cache/tiered_pools_hsa.jsonl.gz (dry-run record) + "
                     "tiered_blast_full_hsa.jsonl.gz (batched BLAST, every pool candidate)"}

    # QD 26 (1): F3–F4 within a design
    fx, fy, per_r = [], [], []
    rx, ry = [], []
    for rec in recs:
        pool = [m for m in rec["candidates"] if m["in_tiered_pool"]]
        if len(pool) < 2:
            continue
        f3 = [ts.f3_specific_length(m["specific_length"]) for m in pool]
        f4 = [ts.f4_binding_tm(m["tm_binding"]) for m in pool]
        m3, m4 = st.mean(f3), st.mean(f4)
        fx += [v - m3 for v in f3]
        fy += [v - m4 for v in f4]
        L = [m["specific_length"] for m in pool]
        d = [dev(m) for m in pool]
        mL, md = st.mean(L), st.mean(d)
        rx += [v - mL for v in L]
        ry += [v - md for v in d]
        r = _pearson(f3, f4)
        if r is not None:
            per_r.append(r)
    pooled = _pearson(fx, fy)
    # Within one design the specific region of length L is always dna[:L], so its
    # binding Tm — hence F4 — is a function of L, like F3. Check it directly.
    f4_function_of_L = sum(
        1 for rec in recs
        if all(len({ts.f4_binding_tm(m["tm_binding"]) for m in rec["candidates"]
                    if m["in_tiered_pool"] and m["specific_length"] == L}) <= 1
               for L in {m["specific_length"] for m in rec["candidates"] if m["in_tiered_pool"]}))
    abs_r = [abs(r) for r in per_r]
    out["qd26_1_f3_f4_within_design"] = {
        "per_design_abs_pearson_levels": _dist(abs_r),
        "designs_abs_r_above_0_7": sum(r > 0.7 for r in abs_r),
        "designs_where_f4_is_a_function_of_length": f4_function_of_L,
        "pooled_within_design_pearson_levels": pooled,
        "per_design_pearson_levels": _dist(per_r),
        "pooled_within_design_pearson_raw_length_vs_abs_binding_tm_dev": _pearson(rx, ry),
        "designs": len(per_r),
        "note": ("Within-design = values centred on each design's mean before pooling, so "
                 "between-design differences do not inflate r. Levels: F3 (length) and F4 "
                 "(|Tm_binding − 45 °C|), both higher = better."),
        "above_0_7": bool(pooled is not None and abs(pooled) > 0.7),
    }

    # rank every design with and without S1
    systems = {}
    for label, wb in (("tiered_no_blast", False), ("tiered_with_blast", True)):
        tops, stats = {}, Counter()
        for rec in recs:
            if not any(m["in_tiered_pool"] for m in rec["candidates"]):
                continue
            sc, res, top = rank(rec, wb)
            tops[rec["mirna"]] = top
            stats["designs"] += 1
            stats["designs_with_eliminated"] += res["eliminated"] > 0
            stats["specificity_fallback"] += res["specificity_fallback"]
            stats["fewer_than_3_sets"] += len(top) < CANDIDATES_TOP_N
            stats["top1_structure_veto"] += top[0]["_r"]["structure_veto"]
            # total_score (= detailed score) is the last tie-break, so it can rise with
            # rank: the current frontend's "#1 vs #2" sentence (rankReason) assumes it falls.
            ds = [c["_r"]["detailed_score"] for c in top]
            stats["returned_total_score_not_decreasing"] += any(b > a for a, b in zip(ds, ds[1:]))
            stats["top1_total_score_below_top2"] += len(ds) > 1 and ds[1] > ds[0]
        systems[label] = (tops, dict(stats))

    by_seq = {rec["mirna"]: {m["sequence"]: m for m in rec["candidates"]} for rec in recs}
    v4_ok = [rec for rec in recs if rec["v4"]["top3"]]

    def qd26(label):
        tops, stats = systems[label]
        v4_L, v4_tb, t_L, t_tb = [], [], [], []
        closer = further = same = 0
        dd = []
        changed = 0
        s1_top1 = Counter()
        for rec in v4_ok:
            name = rec["mirna"]
            if name not in tops:
                continue
            v = by_seq[name][rec["v4"]["top3"][0]]
            t = tops[name][0]["_m"]
            v4_L.append(v["specific_length"]); v4_tb.append(v["tm_binding"])
            t_L.append(t["specific_length"]); t_tb.append(t["tm_binding"])
            s1_top1[tops[name][0]["_r"]["specificity"]["blast"]] += 1
            if t["sequence"] != v["sequence"]:
                changed += 1
                d = round(dev(t) - dev(v), 2)
                dd.append(d)
                if d < 0:
                    closer += 1
                elif d > 0:
                    further += 1
                else:
                    same += 1
        return {
            "ranking_counts": stats,
            "top1_changed_vs_v4_382": {"n": changed, "of": len(t_L)},
            "top1_s1_level": dict(sorted(s1_top1.items(), key=lambda x: (x[0] is None, x[0] or 0))),
            "qd26_2_top1_specific_length": {
                "v4_382": dict(sorted(Counter(v4_L).items())),
                label: dict(sorted(Counter(t_L).items())),
                "mean_v4": round(st.mean(v4_L), 2), "mean_tiered": round(st.mean(t_L), 2)},
            "qd26_2_top1_binding_tm_c": {"v4_382": _dist(v4_tb), label: _dist(t_tb),
                                         "abs_dev_from_45_v4": _dist([abs(x - TM_BINDING_TARGET) for x in v4_tb]),
                                         "abs_dev_from_45_tiered": _dist([abs(x - TM_BINDING_TARGET) for x in t_tb])},
            "qd26_3_changed_top1_binding_tm_vs_45": {
                "closer": closer, "further": further, "same": same,
                "delta_abs_dev_c (new − V4; < 0 = closer)": _dist(dd)},
        }

    out["no_blast"] = qd26("tiered_no_blast")
    out["with_blast"] = qd26("tiered_with_blast")

    # QD 26 follow-up: F3 and F4 are both functions of L within a design. Measured (not
    # applied — QD 26 says propose, do not change): flexible-tier variants, with BLAST.
    def _flex(fn):
        def adj(r):
            f = r["flexible"]
            return {**r, "flexible": {**f, "total": fn(f)}}
        return adj
    variants = {
        "a_min_f3_f4": _flex(lambda f: f["total"] - f["specific_length"] - f["binding_tm"]
                             + min(f["specific_length"], f["binding_tm"])),
        "b_drop_f3": _flex(lambda f: f["total"] - f["specific_length"]),
        "c_drop_f4": _flex(lambda f: f["total"] - f["binding_tm"]),
    }
    base_tops = systems["tiered_with_blast"][0]
    v4_top1 = {rec["mirna"]: by_seq[rec["mirna"]][rec["v4"]["top3"][0]] for rec in v4_ok}

    def _summ(t1):
        common = [n for n in t1 if n in v4_top1]
        dv = [abs(t1[n]["tm_binding"] - TM_BINDING_TARGET) for n in common]
        return {"top1_changed_vs_v4_382": sum(t1[n]["sequence"] != v4_top1[n]["sequence"] for n in common),
                "mean_specific_length": round(st.mean(t1[n]["specific_length"] for n in common), 2),
                "specific_length": dict(sorted(Counter(t1[n]["specific_length"] for n in common).items())),
                "abs_binding_tm_dev_from_45": _dist(dv)}
    opts = {"current_f3_plus_f4": _summ({n: t[0]["_m"] for n, t in base_tops.items()})}
    for name, adj in variants.items():
        t1 = {}
        for rec in recs:
            if any(m["in_tiered_pool"] for m in rec["candidates"]):
                t1[rec["mirna"]] = rank(rec, True, adj)[2][0]["_m"]
        opts[name] = {"top1_changed_vs_current_tiered":
                      sum(t1[n]["sequence"] != base_tops[n][0]["_m"]["sequence"] for n in t1),
                      **_summ(t1)}
    opts["v4_382"] = _summ(v4_top1) | {"top1_changed_vs_v4_382": 0}
    opts["note"] = ("Flexible tier max 20 for a/b/c. Measured to support the QD 26 proposal; "
                    "not applied.")
    out["qd26_f3_f4_options_measured_not_applied"] = opts

    # QD 25 — v4_rule_violations of the tiered #1 (with BLAST)
    tops = systems["tiered_with_blast"][0]
    failed = [r["mirna"] for r in recs if r["v4"]["failed"] and r["mirna"] in tops]
    viol_all, viol_failed, viol_veto, n_any = Counter(), Counter(), Counter(), 0
    for name, top in tops.items():
        v = _v4_rules(top[0]["_m"])
        n_any += bool(v)
        viol_all.update(v or ["none"])
        if name in failed:
            viol_failed.update(v or ["none"])
        if top[0]["_r"]["structure_veto"]:
            viol_veto.update(v or ["none"])
    out["qd25_v4_rule_violations_top1_with_blast"] = {
        "designs": len(tops), "top1_breaking_any_v4_rule": n_any,
        "rules_all_designs": dict(viol_all.most_common()),
        "v4_failed_designs_rescued": len(failed),
        "rules_in_v4_failed_designs": dict(viol_failed.most_common()),
        "rules_when_top1_vetoed": dict(viol_veto.most_common()),
    }
    out["top3_with_blast"] = {n: [c["sequence"] for c in t] for n, t in sorted(tops.items())}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({k: v for k, v in out.items() if k != "top3_with_blast"}, indent=1,
                     ensure_ascii=False)[:6000])
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("blast")
    b.add_argument("--workers", type=int, default=14)
    an = sub.add_parser("analyse")
    an.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    return {"blast": blast, "analyse": analyse}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
