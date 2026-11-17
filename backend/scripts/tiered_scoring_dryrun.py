"""
scripts/tiered_scoring_dryrun.py — Giai đoạn 1 of docs/SPEC_scoring_tiered_4.0.0.md:
score the forward-primer candidate pools of every hsa miRNA with the proposed tiered
thresholds, without changing the design pipeline.

Steps (repo root):
    python backend/scripts/tiered_scoring_dryrun.py record   [--workers 14]
    python backend/scripts/tiered_scoring_dryrun.py blast    [--workers 14] [--sample 300]
    python backend/scripts/tiered_scoring_dryrun.py analyse  [--out benchmark/tiered_scoring_dryrun.json]

record  — for each of the 2656 hsa miRNAs (miRBase 22.1, backend defaults, overhang 6):
          the tiered pool = generate_forward_candidates(gc_prefilter=False) (SPEC QD 15:
          no GC % / G-C clamp pre-filter), no hard filters (QD 7); plus the V4 top 5 of
          algorithm 3.8.2 (from outputs/freeze_cache/pools_hsa_3.8.2.jsonl.gz, written
          by thesis_freeze_impact.py) so both systems are scored on the same metrics.
          Per candidate: structure (hairpin Tm, RNAcofold dimer ΔG, 3'-end dimer Tm),
          Tm, GC, the V4 sub-scores the detailed score reuses, and the assay screen
          (S2 min ΔCq, S3 Tm margin) per specific length (overhang_collision.assay_screen).
blast   — S1: BLAST (classifier v7, same species, with the RT primer) for every
          candidate of a fixed random sample of miRNAs (seed 2026) plus the SPEC §6
          case miRNAs and the wet-lab candidates. One BLAST call takes ~2.5 s (two
          subprocesses), so the full set (~250,000 calls) is out of reach for a dry run.
analyse — applies algorithm/tiered_scoring.py to the recorded metrics (thresholds
          can be changed and re-analysed without re-recording) and writes the tables
          the SPEC asks for.
"""
import argparse
import gzip
import json
import multiprocessing as mp
import os
import random
import statistics as st
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
CACHE = os.path.join(ROOT, "outputs", "freeze_cache")
POOLS = os.path.join(CACHE, "tiered_pools_hsa.jsonl.gz")
BLASTS = os.path.join(CACHE, "tiered_blast_hsa.jsonl.gz")
V4_POOLS = os.path.join(CACHE, "pools_hsa_3.8.2.jsonl.gz")

CASES = ["hsa-let-7a-5p", "hsa-miR-17-5p", "hsa-miR-20a-5p", "hsa-miR-21-5p",
         "hsa-miR-16-5p", "hsa-miR-103a-3p", "hsa-miR-23a-3p"]
WETLAB = ["hsa-miR-16-5p", "hsa-miR-21-5p", "hsa-let-7a-5p", "hsa-miR-451a",
          "hsa-miR-126-3p", "hsa-miR-223-3p"]
SEED = 2026
OVERHANG = 6


def _setup():
    sys.path.insert(0, BACKEND)
    os.chdir(BACKEND)


# ── V4 (3.8.2) reference: top 5 / top 3 of every design ─────────────
def v4_reference() -> dict:
    sys.path.insert(0, os.path.join(BACKEND, "scripts"))
    import thesis_freeze_impact as T
    from algorithm.constants import SCORING_WEIGHTS_V4, UNSCORED_CRITERIA_V4, ASSAY_LABEL_SCORE
    R = T.Ranker(SCORING_WEIGHTS_V4, frozenset(UNSCORED_CRITERIA_V4), ASSAY_LABEL_SCORE)
    ref, bad = {}, 0
    with gzip.open(V4_POOLS, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if not r["api_top3"]:
                ref[r["mirna"]] = {"top5": [], "top3": [], "fallback": False, "failed": True}
                continue
            ranked, fb = R.rank(r, T.rule_current, False)   # 3.8.2 scores are per candidate
            top3 = [c["sequence"] for c in T.top3(ranked)]
            bad += top3 != r["api_top3"]
            ref[r["mirna"]] = {
                "top5": [{"seq": g["seq"], "L": g["L"]} for _, g in ranked[:5]],
                "top3": r["api_top3"], "top3_scores": r["api_scores"],
                "fallback": r["fallback"], "failed": False}
    if bad:
        raise SystemExit(f"offline V4 top 3 differs from the recorded API top 3 in {bad} designs")
    return ref


# ── record ─────────────────────────────────────────────────────────
def _metrics(c, sc, v4, tm_rev, screen):
    from algorithm.structure_check import full_dimer_dg
    ends = [x for x in (sc["self_dimer"].get("end_tm"), sc["hetero_dimer"].get("end_tm"))
            if x is not None]
    s = screen[c["specific_length"]]
    return {
        "sequence": c["sequence"], "specific_length": c["specific_length"],
        "tail_length": c["tail_length"], "tm_full": c["tm_full"], "tm_binding": c["tm_binding"],
        "gc_percent": c["gc_percent"], "tm_reverse": tm_rev, "ta": 60.0,
        "hairpin_tm": sc["hairpin"].get("tm"), "dimer_dg": full_dimer_dg(sc)[0],
        "end_dimer_tm": max(ends) if ends else None,
        "min_delta_cq": s["min_delta_cq"], "worst": s["worst"],
        "min_delta_cq_other": s["min_delta_cq_other"],
        "tm_margin": s["tm_margin"], "tm_margin_worst": s["tm_margin_worst"],
        "tm_margin_r0": s["tm_margin_r0"],
        "v4_scores": {k: v4["scores"][k] for k in ("tm_accuracy", "tm_binding_accuracy",
                                                   "gc_content", "gc_clamp", "primer_size",
                                                   "amplicon_size")},
    }


def _record_one(item):
    name, rna, v4ref = item
    from algorithm.forward_primer import generate_forward_candidates, _build_candidate
    from algorithm.stemloop_rt import design_stemloop_rt
    from algorithm.universal_reverse import get_universal_reverse
    from algorithm.structure_check import run_all_structure_checks
    from algorithm.structure_check.heterodimer import check_all_heterodimers
    from algorithm.template_structure import check_template_structure
    from algorithm.scoring import score_candidate
    from algorithm.thermodynamics import calculate_tm_nn
    from algorithm.specificity_check.overhang_collision import assay_screen
    from algorithm.sequence_utils import rna_to_dna

    t0 = time.time()
    params = {}
    dna = rna_to_dna(rna).upper()
    stemloop = design_stemloop_rt(rna, params, mirna_name=name)
    reverse = get_universal_reverse(params)
    tm_rev = round(calculate_tm_nn(reverse["sequence"], params), 2)
    cands, log = generate_forward_candidates(rna, params, gc_prefilter=False)
    pool_seqs = {c["sequence"] for c in cands}
    extra = []
    for v in v4ref["top5"]:
        if v["seq"] not in pool_seqs:
            L = v["L"]
            extra.append(_build_candidate(v["seq"], dna[:L], v["seq"][:-L], L, len(dna), params))
    allc = cands + extra
    screen = assay_screen(rna, name, params, OVERHANG, {c["specific_length"] for c in allc}) if allc else {}
    out = []
    for c in allc:
        c["structure_checks"] = run_all_structure_checks(c["sequence"], reverse["sequence"], params)
        c["heterodimer_checks"] = check_all_heterodimers(c["sequence"], stemloop["sequence"],
                                                         reverse["sequence"], params)
        c["template_structure"] = check_template_structure(rna, c, params)
        v4 = score_candidate(c, stemloop, reverse, params, use_v4=True)
        m = _metrics(c, c["structure_checks"], v4, tm_rev, screen)
        m["in_tiered_pool"] = c["sequence"] in pool_seqs
        out.append(m)
    return {"mirna": name, "rna": rna, "rt_primer": stemloop["sequence"], "tm_reverse": tm_rev,
            "n_generated_rejections": dict(Counter(r["reason"] for r in log)),
            "candidates": out, "v4": v4ref, "seconds": round(time.time() - t0, 2)}


def _init():
    _setup()
    import warnings
    warnings.filterwarnings("ignore")


def record(a):
    _setup()
    sys.path.insert(0, ROOT)
    from crossreactivity.model import load_mature
    ref = v4_reference()
    mature = load_mature(os.path.join(BACKEND, "data", "mirbase_overhang_index.json"), "hsa")
    items = [(n, s.replace("T", "U"), ref[n]) for n, s in sorted(mature.items())][: a.limit]
    os.makedirs(CACHE, exist_ok=True)
    t0, n = time.time(), 0
    with gzip.open(POOLS, "wt", encoding="utf-8") as f, mp.Pool(a.workers, initializer=_init) as p:
        for rec in p.imap_unordered(_record_one, items, chunksize=2):
            f.write(json.dumps(rec) + "\n")
            n += 1
            if n % 250 == 0 or n == len(items):
                print(f"  {n}/{len(items)}  {time.time() - t0:.0f}s", flush=True)
    print(f"wrote {POOLS}")
    return 0


# ── blast ──────────────────────────────────────────────────────────
def blast_sample(names: list) -> list:
    rng = random.Random(SEED)
    sample = rng.sample(sorted(names), min(300, len(names)))
    return sorted(set(sample) | set(CASES) | set(WETLAB))


def _blast_one(item):
    name, rna, rt, seqs = item
    from algorithm.specificity_check.blast_offtarget import check_offtarget
    from algorithm.constants import UNIVERSAL_REVERSE
    res = {}
    for s in seqs:
        t = time.time()
        try:
            o = check_offtarget(s, UNIVERSAL_REVERSE, mirna_id=name, target_sequence=rna,
                                species="hsa", rt_primer=rt)
            summ = o["summary"]
            n_med = sum(h.get("risk") == "MEDIUM" for h in o["forward_primer_hits"]) + sum(
                v["risk"] == "MEDIUM" for v in o["identical_sequence_risk"].values())
            worst = next((h.get("subject_id") for h in o["forward_primer_hits"]
                          if h.get("risk") == summ["overall_risk"]), None)
            res[s] = {"risk": summ["overall_risk"], "n_medium": n_med, "worst": worst,
                      "seconds": round(time.time() - t, 3)}
        except Exception as e:   # noqa: BLE001
            res[s] = {"risk": None, "error": str(e), "seconds": round(time.time() - t, 3)}
    return name, res


def blast(a):
    _setup()
    recs = {}
    with gzip.open(POOLS, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            recs[r["mirna"]] = r
    names = blast_sample([n for n, r in recs.items() if r["candidates"]])
    # Incremental: a BLAST result depends only on (miRNA, primer, RT primer), so results
    # of an earlier run are reused and only new candidate sequences are BLASTed.
    done = {}
    if os.path.exists(BLASTS):
        with gzip.open(BLASTS, "rt", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                done[r["mirna"]] = {k: v for k, v in r["results"].items() if v.get("risk")}
    items = [(n, recs[n]["rna"], recs[n]["rt_primer"],
              [c["sequence"] for c in recs[n]["candidates"]
               if c["sequence"] not in done.get(n, {})]) for n in names]
    print(f"BLAST: {len(items)} miRNAs, {sum(len(i[3]) for i in items)} new candidates "
          f"({sum(len(v) for v in done.values())} reused)", flush=True)
    t0, n = time.time(), 0
    merged = {nm: dict(done.get(nm, {})) for nm in names}
    with mp.Pool(a.workers, initializer=_init) as p:
        for name, res in p.imap_unordered(_blast_one, items):
            merged[name].update(res)
            n += 1
            if n % 25 == 0 or n == len(items):
                print(f"  {n}/{len(items)}  {time.time() - t0:.0f}s", flush=True)
    with gzip.open(BLASTS, "wt", encoding="utf-8") as f:
        for name in names:
            f.write(json.dumps({"mirna": name, "results": merged[name]}) + "\n")
    print(f"wrote {BLASTS}")
    return 0


# ── analyse ────────────────────────────────────────────────────────
def _pct(n, d):
    return round(100.0 * n / d, 1) if d else 0.0


def _dist(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return {"n": 0}
    q = lambda p: xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))]   # noqa: E731
    return {"n": len(xs), "min": xs[0], "p05": q(.05), "median": q(.5), "p95": q(.95), "max": xs[-1]}


def _pearson(x, y):
    if len(x) < 2:
        return None
    mx, my = st.mean(x), st.mean(y)
    sx = sum((a - mx) ** 2 for a in x) ** .5
    sy = sum((b - my) ** 2 for b in y) ** .5
    return round(sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy), 3) if sx and sy else None


LEVEL_KEYS = [("S1 blast", lambda r: r["specificity"]["blast"]),
              ("S2 assay_dcq", lambda r: r["specificity"]["assay_dcq"]),
              ("S3 tm_margin", lambda r: r["specificity"]["tm_margin"]),
              ("P1 tm_pair (report only)", lambda r: r["pcr"]["tm_pair_report_only"]),
              ("P2 tm_vs_ta", lambda r: r["pcr"]["tm_vs_ta"]),
              ("F1 gc", lambda r: r["flexible"]["gc"]),
              ("F2 gc_clamp", lambda r: r["flexible"]["gc_clamp"]),
              ("F3 specific_length", lambda r: r["flexible"]["specific_length"]),
              ("F4 binding_tm", lambda r: r["flexible"]["binding_tm"]),
              ("F5 structure", lambda r: r["flexible"]["structure"]),
              ("F5a hairpin_tm", lambda r: r["flexible"]["structure_sub_scores"]["hairpin_tm"]),
              ("F5b dimer_dg", lambda r: r["flexible"]["structure_sub_scores"]["dimer_dg"]),
              ("F5c end_dimer_tm", lambda r: r["flexible"]["structure_sub_scores"]["end_dimer_tm"])]


def _tiers(r):
    return {"S": r["specificity"]["total"], "S_max": r["specificity"]["max"],
            "veto": r["structure_veto"], "P": r["pcr"]["total"], "F": r["flexible"]["total"],
            "detail": r["detailed_score"]}


def analyse(a):
    _setup()
    from algorithm import tiered_scoring as ts
    from algorithm.forward_primer import select_diverse_top
    from algorithm.constants import CANDIDATES_TOP_N, ALGORITHM_VERSION

    recs = []
    with gzip.open(POOLS, "rt", encoding="utf-8") as f:
        recs = sorted((json.loads(x) for x in f), key=lambda r: r["mirna"])
    blast_res = {}
    if os.path.exists(BLASTS):
        with gzip.open(BLASTS, "rt", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                blast_res[r["mirna"]] = r["results"]

    def scored(rec, with_blast, s2_key="min_delta_cq", s3_key="tm_margin"):
        out = []
        b = blast_res.get(rec["mirna"], {}) if with_blast else {}
        for m in rec["candidates"]:
            mm = dict(m)
            bb = b.get(m["sequence"])
            mm["blast_risk"] = bb["risk"] if bb else None
            mm["blast_medium_hits"] = bb.get("n_medium", 0) if bb else 0
            mm["min_delta_cq"] = m[s2_key]
            mm["tm_margin"] = m[s3_key]
            out.append((mm, ts.score(mm)))
        return out

    def run_design(rec, with_blast, **kw):
        sc = scored(rec, with_blast, **kw)
        pool = [c for c in sc if c[0]["in_tiered_pool"]]
        res = ts.rank(pool)
        pseudo = [{"specific_length": m["specific_length"], "sequence": m["sequence"],
                   "_m": m, "_r": r} for m, r in res["ranked"]]
        top = select_diverse_top(pseudo, CANDIDATES_TOP_N)
        return sc, pool, res, top

    def summarise(subset, with_blast, **kw):
        per = {}
        lv_all = defaultdict(Counter)
        lv_v4top5 = defaultdict(Counter)
        varies = Counter()
        sd_sum, sd_n, filter_only = Counter(), Counter(), Counter()
        elim_designs = fb = fewer3 = veto1 = 0
        ties = Counter()
        changed, dS, dL, dTm = [], [], [], []
        n = 0
        p1p2_x, p1p2_y = [], []
        for rec in subset:
            if not rec["candidates"]:
                continue
            sc, pool, res, top = run_design(rec, with_blast, **kw)
            if not pool:
                continue
            n += 1
            by_seq = {m["sequence"]: (m, r) for m, r in sc}
            for m, r in pool:
                for k, fn in LEVEL_KEYS:
                    lv_all[k][fn(r)] += 1
                p1p2_x.append(abs(m["tm_full"] - m["tm_reverse"]))
                p1p2_y.append(abs(m["tm_full"] - m["ta"]))
            for v in rec["v4"]["top5"]:
                if v["seq"] in by_seq:
                    for k, fn in LEVEL_KEYS:
                        lv_v4top5[k][fn(by_seq[v["seq"]][1])] += 1
            for k, fn in LEVEL_KEYS:
                vals = [fn(r) for _, r in pool]
                varies[k] += len(set(vals)) > 1
                if all(v is not None for v in vals) and len(vals) > 1:
                    sd_sum[k] += st.pstdev(vals)
                    sd_n[k] += 1
                    if len(set(vals)) > 1 and 1 in vals and len({v for v in vals if v != 1}) == 1:
                        filter_only[k] += 1
            elim_designs += res["eliminated"] > 0
            fb += res["specificity_fallback"]
            fewer3 += len(top) < CANDIDATES_TOP_N
            veto1 += top[0]["_r"]["structure_veto"]
            rk = res["ranked"]
            if len(rk) > 1:
                a1, a2 = _tiers(rk[0][1]), _tiers(rk[1][1])
                if a1["S"] != a2["S"]:
                    ties["decided_by_S"] += 1
                elif a1["veto"] != a2["veto"]:
                    ties["decided_by_veto"] += 1
                elif a1["P"] != a2["P"]:
                    ties["decided_by_P"] += 1
                elif a1["F"] != a2["F"]:
                    ties["decided_by_F"] += 1
                elif a1["detail"] != a2["detail"]:
                    ties["decided_by_detailed_score"] += 1
                elif abs(rk[0][0]["tm_full"] - 60) != abs(rk[1][0]["tm_full"] - 60):
                    ties["decided_by_tm"] += 1
                else:
                    ties["decided_by_sequence"] += 1
            t1 = top[0]
            v4top = rec["v4"]["top3"]
            entry = {"tiered_top3": [{"sequence": c["sequence"], "L": c["specific_length"],
                                      "selection": c.get("selection"), **_tiers(c["_r"]),
                                      "levels": {k: fn(c["_r"]) for k, fn in LEVEL_KEYS},
                                      "min_delta_cq": c["_m"]["min_delta_cq"],
                                      "worst": c["_m"]["worst"],
                                      "tm_margin": c["_m"]["tm_margin"],
                                      "tm_full": c["_m"]["tm_full"], "gc": c["_m"]["gc_percent"]}
                                     for c in top],
                     "eliminated": res["eliminated"], "pool": len(pool),
                     "specificity_fallback": res["specificity_fallback"]}
            if v4top:
                vm, vr = by_seq[v4top[0]]
                entry["v4_top3"] = [{"sequence": s, "v4_score": sco,
                                     **(_tiers(by_seq[s][1]) if s in by_seq else {}),
                                     "L": by_seq[s][0]["specific_length"] if s in by_seq else None,
                                     "eliminated_in_tiered": by_seq[s][1]["eliminated"] if s in by_seq else None}
                                    for s, sco in zip(v4top, rec["v4"]["top3_scores"])]
                if t1["sequence"] != v4top[0]:
                    changed.append(rec["mirna"])
                    dS.append(t1["_r"]["specificity"]["total"] - vr["specificity"]["total"])
                    dL.append(t1["specific_length"] - vm["specific_length"])
                    dTm.append(round(t1["_m"]["tm_full"] - vm["tm_full"], 1))
            per[rec["mirna"]] = entry
        v4_ok = [r for r in subset if r["v4"]["top3"] and r["mirna"] in per]
        return {
            "designs": n,
            "level_distribution_all_candidates": {k: dict(sorted(v.items(), key=lambda x: (x[0] is None, x[0]))) for k, v in lv_all.items()},
            "level_distribution_v4_top5": {k: dict(sorted(v.items(), key=lambda x: (x[0] is None, x[0]))) for k, v in lv_v4top5.items()},
            "dominant_level_over_90pct": {
                k: {"level": c.most_common(1)[0][0], "pct": _pct(c.most_common(1)[0][1], sum(c.values()))}
                for k, c in lv_all.items() if sum(c.values()) and
                c.most_common(1)[0][1] / sum(c.values()) > 0.9},
            "pools_where_criterion_varies_pct": {k: _pct(varies[k], n) for k, _ in LEVEL_KEYS},
            "within_design_diagnostic": {
                k: {"varies_pct": _pct(varies[k], n),
                    "mean_within_design_sd": round(sd_sum[k] / sd_n[k], 3) if sd_n[k] else None,
                    "designs_where_it_only_separates_level_1": filter_only[k],
                    "role": ("constant: report only" if not varies[k] else
                             "filter: only separates level 1" if filter_only[k] == varies[k] else
                             "ranks candidates")}
                for k, _ in LEVEL_KEYS},
            "designs_with_eliminated_candidates": elim_designs,
            "specificity_fallback": fb,
            "fewer_than_3_sets": fewer3,
            "top1_structure_veto": veto1,
            "top1_vs_top2_decided_by": dict(ties),
            "top1_changed_vs_v4_382": {"n": len(changed), "of": len(v4_ok), "mirnas": changed,
                                        "delta_S_total": dict(Counter(dS)),
                                        "delta_specific_length": dict(sorted(Counter(dL).items())),
                                        "delta_tm_full_c": _dist(dTm)},
            "p1_p2": {"tm_reverse_c": recs[0]["tm_reverse"] if recs else None,
                      "pearson_abs_dTm": _pearson(p1p2_x, p1p2_y),
                      "abs_tm_f_minus_r": _dist(p1p2_x), "abs_tm_f_minus_ta": _dist(p1p2_y)},
            "per_design": per,
        }

    ok = [r for r in recs if r["candidates"]]
    sample = set(blast_res)
    sub_blast = [r for r in ok if r["mirna"] in sample]
    full = summarise(ok, False)
    samp_nb = summarise(sub_blast, False)
    samp_b = summarise(sub_blast, True)
    alt_s2 = summarise(ok, False, s2_key="min_delta_cq_other")
    alt_s3 = summarise(ok, False, s3_key="tm_margin_r0")

    # item 7: timing
    bt = [v["seconds"] for d in blast_res.values() for v in d.values()]
    pool_sizes = [full["per_design"][m]["pool"] for m in full["per_design"]]
    surv = [full["per_design"][m]["pool"] - full["per_design"][m]["eliminated"] for m in full["per_design"]]
    rec_s = [r["seconds"] for r in ok]
    timing = {"blast_seconds_per_candidate": _dist(bt),
              "pool_size": _dist(pool_sizes), "candidates_after_s2_elimination": _dist(surv),
              "record_seconds_per_design_no_blast": _dist(rec_s),
              "note": ("record seconds include V4 sub-scores and extra V4 top-5 candidates, run "
                       "with 14 parallel workers; one BLAST call = blastn + blastdbcmd subprocesses")}
    if bt:
        mb = st.median(bt)
        timing["estimated_design_seconds_p50"] = round(st.median(rec_s) + mb * st.median(surv), 1)
        timing["blast_errors"] = sum(v.get("risk") is None for d in blast_res.values() for v in d.values())

    # item 9: V4 failures
    v4_failed = [r for r in recs if r["v4"]["failed"]]
    rescued = [r for r in v4_failed if r["mirna"] in full["per_design"]]
    import re
    t9 = {"v4_failed": len(v4_failed), "tiered_has_candidates": len(rescued),
          "top1_F1": dict(Counter(full["per_design"][r["mirna"]]["tiered_top3"][0]["levels"]["F1 gc"] for r in rescued)),
          "top1_F2": dict(Counter(full["per_design"][r["mirna"]]["tiered_top3"][0]["levels"]["F2 gc_clamp"] for r in rescued)),
          "top1_S_total_no_blast": dict(Counter(full["per_design"][r["mirna"]]["tiered_top3"][0]["S"] for r in rescued)),
          "top1_structure_veto": sum(full["per_design"][r["mirna"]]["tiered_top3"][0]["veto"] for r in rescued),
          "still_no_candidate": [r["mirna"] for r in v4_failed if r["mirna"] not in full["per_design"]],
          "low_number": []}
    for r in v4_failed:
        mm = re.match(r"hsa-(?:miR|let)-(\d+)", r["mirna"])
        if mm and int(mm.group(1)) < 1000:
            e = full["per_design"].get(r["mirna"])
            t9["low_number"].append({"mirna": r["mirna"],
                                     "top1": e["tiered_top3"][0] if e else None})
    # item 10: V4 hard_filter_fallback designs
    fbk = [r for r in recs if r["v4"]["fallback"]]
    t10 = {"v4_fallback_designs": len(fbk),
           "tiered_top1_structure_veto": sum(full["per_design"][r["mirna"]]["tiered_top3"][0]["veto"] for r in fbk),
           "tiered_top1_F5": dict(Counter(full["per_design"][r["mirna"]]["tiered_top3"][0]["levels"]["F5 structure"] for r in fbk))}

    # checks asked in the Giai đoạn 1 review (2026-11-17)
    chk = {"p_in_specificity_fallback_designs": Counter(), "p_varies_in_specificity_fallback": 0,
           "n_specificity_fallback": 0, "p_in_v4_fallback_designs": Counter(),
           "p_varies_in_v4_fallback": 0, "f5c_level1": [], "designs_all_vetoed": 0,
           "designs_all_vetoed_only_by_f5c": 0, "v4_top1_in_tiered_pool": 0, "v4_designs": 0}
    for rec in ok:
        sc = scored(rec, False)
        pool = [c for c in sc if c[0]["in_tiered_pool"]]
        if not pool:
            continue
        res = ts.rank(pool)
        ps = [r["pcr"]["total"] for _, r in pool]
        if res["specificity_fallback"]:
            chk["n_specificity_fallback"] += 1
            chk["p_varies_in_specificity_fallback"] += len(set(ps)) > 1
            chk["p_in_specificity_fallback_designs"].update(ps)
        if rec["v4"]["fallback"]:
            chk["p_varies_in_v4_fallback"] += len(set(ps)) > 1
            chk["p_in_v4_fallback_designs"].update(ps)
        subs = [r["flexible"]["structure_sub_scores"] for _, r in pool]
        for (m, r), sub in zip(pool, subs):
            if sub["end_dimer_tm"] == 1:
                chk["f5c_level1"].append({"mirna": rec["mirna"], "sequence": m["sequence"],
                                          "end_dimer_tm": m["end_dimer_tm"],
                                          "hairpin_tm": m["hairpin_tm"], "dimer_dg": m["dimer_dg"],
                                          "other_sub_indices": [sub["hairpin_tm"], sub["dimer_dg"]]})
        if all(r["structure_veto"] for _, r in pool):
            chk["designs_all_vetoed"] += 1
            chk["designs_all_vetoed_only_by_f5c"] += all(
                x["hairpin_tm"] > 1 and x["dimer_dg"] > 1 for x in subs)
        if rec["v4"]["top3"]:
            chk["v4_designs"] += 1
            chk["v4_top1_in_tiered_pool"] += any(
                m["sequence"] == rec["v4"]["top3"][0] for m, _ in pool)
    chk["f5c_level1_alone"] = sum(1 for x in chk["f5c_level1"] if min(x["other_sub_indices"]) > 1)
    for k in ("p_in_specificity_fallback_designs", "p_in_v4_fallback_designs"):
        chk[k] = dict(chk[k])

    def strip(s):
        return {k: v for k, v in s.items() if k != "per_design"}

    out = {
        "generated_by": "backend/scripts/tiered_scoring_dryrun.py",
        "run_date": time.strftime("%Y-%m-%d"),
        "algorithm_version": ALGORITHM_VERSION, "species": "hsa", "mirbase_release": "22.1",
        "mirnas": len(recs), "with_tiered_candidates": len(ok),
        "blast_sample": {"seed": SEED, "random": 300, "forced": sorted(set(CASES) | set(WETLAB)),
                         "designs": len(sub_blast)},
        "note": ("Dry run of the proposed tiered thresholds (SPEC §3) — the pipeline is "
                 "unchanged. 'full' ranks without BLAST (S1 = null, S max 10) on all hsa; "
                 "'sample_with_blast' adds S1 on the BLAST sample."),
        "full_no_blast": strip(full),
        "sample_no_blast": strip(samp_nb),
        "sample_with_blast": strip(samp_b),
        "alternative_s2_other_category_only": {k: alt_s2[k] for k in (
            "designs_with_eliminated_candidates", "specificity_fallback", "fewer_than_3_sets",
            "level_distribution_all_candidates")},
        "alternative_s3_register_0_only_not_used": {k: alt_s3[k] for k in ("level_distribution_all_candidates",)},
        "review_checks": chk,
        "timing": timing,
        "v4_failed_designs": t9,
        "v4_hard_filter_fallback": t10,
        "cases": {m: samp_b["per_design"].get(m) or full["per_design"].get(m) for m in CASES + WETLAB},
    }
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    print(f"wrote {a.out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--workers", type=int, default=14)
    r.add_argument("--limit", type=int)
    b = sub.add_parser("blast")
    b.add_argument("--workers", type=int, default=14)
    an = sub.add_parser("analyse")
    an.add_argument("--out", default=os.path.join(ROOT, "benchmark", "tiered_scoring_dryrun.json"))
    a = ap.parse_args(argv)
    return {"record": record, "blast": blast, "analyse": analyse}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
