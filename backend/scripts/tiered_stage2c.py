"""
scripts/tiered_stage2c.py — Giai đoạn 2c of docs/SPEC_scoring_tiered_4.0.0.md (QD 33–35).

    python backend/scripts/tiered_stage2c.py offline [--out benchmark/tiered_stage2c_offline.json]
    python backend/scripts/tiered_stage2c.py trial   [--log benchmark/logs/stage2c_trial.log]

offline — acceptance of QD 33 and QD 34 and the 4-column comparison (V4 3.8.2 |
          tiered Giai đoạn 2 | QD 29 | final = QD 29 + 33 + 34), ranking the recorded
          pools with algorithm/tiered_scoring.py and the S1 of every candidate from the
          Giai đoạn 2 BLAST run (outputs/freeze_cache/tiered_blast_full_hsa.jsonl.gz).
          The pipeline reproduces this offline ranking (20/20 designs, SPEC §10).
trial   — step A5: the 20 miRNAs of tiered_design_timing.json through the real
          pipeline WITH the BLAST sqlite cache: cache hit rate (≥ 90 % required) and
          S1 of every BLASTed candidate vs the Giai đoạn 2 run. Writes provenance first.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from collections import Counter

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "scripts"))
CACHE_DB = os.path.join(BACKEND, "data", "blast_cache.sqlite")
LOGS = os.path.join(ROOT, "benchmark", "logs")

# system → (F4 floor, detailed binding-Tm anchors, V4-compliant-first, normalised
# weight of tm_binding_accuracy or None = constants)
_A25 = ((25.0, 0.0), (45.0, 100.0))
SYSTEMS = {
    "tiered_g2": (False, None, False, None),
    "qd29": (True, ((35.0, 0.0), (45.0, 100.0)), False, None),
    "final_without_qd34": (True, _A25, False, None),
    "final": (True, _A25, True, None),
    "final_w015_without_qd34": (True, _A25, False, 0.15),
    "final_w015": (True, _A25, True, 0.15),
}


def _setup():
    os.chdir(BACKEND)
    import warnings
    warnings.filterwarnings("ignore")


def provenance() -> dict:
    from algorithm import constants as K
    from algorithm.specificity_check import blast_offtarget as bo
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT).stdout.strip())
    blastn = subprocess.run(["blastn", "-version"], capture_output=True, text=True).stdout.splitlines()[:1]
    meta = json.load(open(bo._METADATA, encoding="utf-8"))
    h = hashlib.sha256()
    for ext in sorted(e for e in os.listdir(os.path.dirname(bo._MIRBASE_DB))
                      if e.startswith(os.path.basename(bo._MIRBASE_DB) + ".")):
        with open(os.path.join(os.path.dirname(bo._MIRBASE_DB), ext), "rb") as f:
            h.update(ext.encode()); h.update(f.read())
    rows = sqlite3.connect(CACHE_DB).execute("select count(*) from blast_cache").fetchone()[0] \
        if os.path.exists(CACHE_DB) else 0
    return {"git_sha": sha, "working_tree_dirty": dirty, "algorithm_version": K.ALGORITHM_VERSION,
            "flags": {f: getattr(K, f) for f in ("SCORING_SYSTEM_DEFAULT", "TIERED_F4_FLOOR",
                                                 "TIERED_GRADE_BY_TIERS", "TIERED_V4_COMPLIANT_FIRST",
                                                 "BLAST_BATCH_PROCESSES")},
            "detail_tm_binding_anchors": K.TIERED_DETAIL_TM_BINDING_FLOOR,
            "env_BLAST_CACHE_DISABLED": os.environ.get("BLAST_CACHE_DISABLED"),
            "blastn": blastn[0] if blastn else None, "blast_db_metadata": meta,
            "blast_db_files_sha256": h.hexdigest(), "blast_cache_rows": rows,
            "started": dt.datetime.now().isoformat(timespec="seconds")}


# ── offline ───────────────────────────────────────────────────────
def offline(a):
    _setup()
    import tiered_stage2_report as S2
    from algorithm import tiered_scoring as ts
    from algorithm.forward_primer import select_diverse_top
    from algorithm.constants import CANDIDATES_TOP_N, TM_BINDING_TARGET
    bl = {}
    with gzip.open(S2.BLAST_FULL, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["error"]:
                raise SystemExit(f"BLAST failed for {r['mirna']} (QD 24e)")
            bl[r["mirna"]] = r["results"]
    recs = [r for r in S2._load_pools() if any(m["in_tiered_pool"] for m in r["candidates"])]
    v4rules = S2._v4_rules
    pools = {}
    for rec in recs:
        ms = []
        for m in rec["candidates"]:
            if not m["in_tiered_pool"]:
                continue
            mm = dict(m)
            x = bl[rec["mirna"]][m["sequence"]]
            mm.update(blast_risk=x["risk"], blast_medium_hits=x["n_medium"], blast_worst=x["worst"],
                      v4_violation=bool(v4rules(m)))
            ms.append(mm)
        pools[rec["mirna"]] = ms
    v4_top1 = {r["mirna"]: next(c for c in r["candidates"] if c["sequence"] == r["v4"]["top3"][0])
               for r in recs if r["v4"]["top3"]}

    real_anchor, real_w = ts.TIERED_DETAIL_TM_BINDING_FLOOR, dict(ts.TIERED_DETAIL_WEIGHTS)
    out = {"designs": len(recs), "designs_with_v4": len(v4_top1)}
    tops, why = {}, {}
    for name, (floor, anchor, v4first, wnorm) in SYSTEMS.items():
        ts.TIERED_DETAIL_TM_BINDING_FLOOR = anchor or real_anchor
        w = dict(real_w)
        if wnorm:
            # raw weight x with x / (rest + x) = wnorm, rest = the other floor weights
            rest = sum(v for k, v in w.items() if k not in ("tm_binding_accuracy", "primer_size"))
            w["tm_binding_accuracy"] = wnorm * rest / (1 - wnorm)
        ts.TIERED_DETAIL_WEIGHTS = w
        lost = Counter()
        t = {}
        for n, ms in pools.items():
            sc = [(m, ts.score(m, floor)) for m in ms]
            res = ts.rank(sc, v4_compliant_first=v4first)
            pseudo = [{"specific_length": m["specific_length"], "sequence": m["sequence"], "_m": m, "_r": r}
                      for m, r in res["ranked"]]
            t[n] = (select_diverse_top(pseudo, CANDIDATES_TOP_N)[0], res)
            # diagnosis: #1 at F4 floor level 1 although a candidate of the same S, veto
            # (and V4 step) has a higher F4 — which tier made it lose?
            m1, r1 = res["ranked"][0]
            if floor and ts.f4_binding_tm_floor(m1["tm_binding"]) == 1:
                g = lambda m, r: (r["specificity"]["total"], r["structure_veto"],   # noqa: E731
                                  bool(m["v4_violation"]) and v4first)
                alt = [(m, r) for m, r in res["ranked"]
                       if g(m, r) == g(m1, r1) and ts.f4_binding_tm_floor(m["tm_binding"]) > 1]
                if not alt:
                    lost["no_higher_f4_candidate_in_group"] += 1
                else:
                    m2, r2 = alt[0]
                    if r1["pcr"]["total"] != r2["pcr"]["total"]:
                        lost["P"] += 1
                    elif r1["flexible"]["total"] != r2["flexible"]["total"]:
                        lost["F (F1/F2/F5 outweigh F4)"] += 1
                    else:
                        lost["detailed_or_later"] += 1
        tops[name] = t
        if floor:
            why[name] = dict(lost.most_common())
    ts.TIERED_DETAIL_TM_BINDING_FLOOR = real_anchor
    ts.TIERED_DETAIL_WEIGHTS = real_w
    out["diagnosis_top1_f4_level_1"] = why

    def tm_stats(names, get):
        tb = [get(n)["tm_binding"] for n in names]
        lv = Counter(ts.f4_binding_tm_floor(x) for x in tb)
        return {"f4_floor_level_1": lv[1], "f4_floor_levels": dict(sorted(lv.items())),
                "pct_binding_tm_below_45": round(100 * sum(x < TM_BINDING_TARGET for x in tb) / len(tb), 2)}

    acc = {}
    for name in SYSTEMS:
        acc[name] = {"all_2472": tm_stats(pools, lambda n: tops[name][n][0]["_m"]),
                     "v4_2253": tm_stats(v4_top1, lambda n: tops[name][n][0]["_m"])}
    acc["v4_382"] = {"v4_2253": tm_stats(v4_top1, lambda n: v4_top1[n])}
    f = acc["final"]["all_2472"]
    f15 = acc["final_w015"]["all_2472"]
    out["qd33_acceptance"] = {
        "criteria": "top1 over 2472 designs: F4 = 1 count ≤ 179 and % binding Tm < 45 °C ≤ 39.0",
        "final_all_2472": f, "pass": f["f4_floor_level_1"] <= 179 and f["pct_binding_tm_below_45"] <= 39.0,
        "final_w015_all_2472": f15,
        "pass_w015": f15["f4_floor_level_1"] <= 179 and f15["pct_binding_tm_below_45"] <= 39.0,
        "by_system": acc,
        "note": ("179 and 38.4 % were read on the 2253 designs V4 designs (SPEC §11); on all "
                 "2472 the Giai đoạn 2 tiered #1 has F4 = 1 in "
                 f"{acc['tiered_g2']['all_2472']['f4_floor_level_1']} designs — the criterion "
                 "is applied on 2472 as written (stricter)."),
    }
    diff = Counter()
    for n in pools:
        a_ = tops["final_without_qd34"][n][0]["_r"]["specificity"]
        b_ = tops["final"][n][0]["_r"]["specificity"]
        for k in ("blast", "assay_dcq", "tm_margin"):
            diff[k] += a_[k] != b_[k]
    changed = sum(tops["final_without_qd34"][n][0]["_m"]["sequence"] != tops["final"][n][0]["_m"]["sequence"]
                  for n in pools)
    out["qd34_acceptance"] = {
        "criteria": "S1, S2, S3 of #1 unchanged vs the configuration without QD 34, every design",
        "top1_changed_by_qd34": changed,
        "designs_where_component_changed": dict(diff),
        "pass": not any(diff.values()),
    }
    out["top1_changed"] = {
        name: {"vs_v4": sum(tops[name][n][0]["_m"]["sequence"] != v4_top1[n]["sequence"] for n in v4_top1),
               "vs_tiered_g2": sum(tops[name][n][0]["_m"]["sequence"] != tops["tiered_g2"][n][0]["_m"]["sequence"]
                                   for n in pools),
               "top1_breaks_v4_rule": sum(bool(v4rules(tops[name][n][0]["_m"])) for n in pools)}
        for name in SYSTEMS}
    out["top3_final"] = {n: tops["final"][n][0]["_m"]["sequence"] for n in sorted(pools)}
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(json.dumps({k: v for k, v in out.items() if k != "top3_final"}, indent=1, ensure_ascii=False))
    return 0 if out["qd33_acceptance"]["pass"] and out["qd34_acceptance"]["pass"] else 1


# ── trial (step A5) ───────────────────────────────────────────────
def trial(a):
    _setup()
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    log = open(a.log, "a", encoding="utf-8")

    def say(x):
        print(x, flush=True)
        log.write(x + "\n"); log.flush()
    prov = provenance()
    say("PROVENANCE " + json.dumps(prov, ensure_ascii=False))
    if os.environ.get("BLAST_CACHE_DISABLED"):
        raise SystemExit("BLAST_CACHE_DISABLED is set — not allowed in Giai đoạn 2c")
    import tiered_stage2_report as S2
    from algorithm.design_pipeline import run
    from algorithm import tiered_pipeline as tp
    from algorithm import tiered_scoring as ts
    from algorithm.specificity_check.blast_cache import BlastCache
    from algorithm.specificity_check.overhang_collision import _load_index
    timing = json.load(open(os.path.join(ROOT, "benchmark", "tiered_design_timing.json"), encoding="utf-8"))
    names = [r["mirna"] for r in timing["designs"]]
    stored = {}
    with gzip.open(S2.BLAST_FULL, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["mirna"] in names:
                stored[r["mirna"]] = r["results"]
    hsa = _load_index()["mature"]["hsa"]
    # capture the cache key context of each design
    seen = {}
    real = tp.blast_candidates

    def spy(seqs, target_rna, mirna_name, reverse_seq, rt_seq, p3, species):
        out = real(seqs, target_rna, mirna_name, reverse_seq, rt_seq, p3, species)
        seen.setdefault(mirna_name, []).append((list(seqs), out, (target_rna, reverse_seq, rt_seq, p3, species)))
        return out
    tp.blast_candidates = spy
    hits = blasted = 0
    s1_diff, s1_n = [], 0
    for n in names:
        run(hsa[n].upper().replace("T", "U"), {}, n)
        for seqs, out, ctx in seen.get(n, []):
            hits += out["cache_hits"]
            blasted += len(seqs)
            for s, res in out["results"].items():
                risk, n_med, _ = ts.blast_s1_inputs(res)
                old = stored.get(n, {}).get(s)
                if old is None:
                    continue
                s1_n += 1
                if ts.s1_blast(risk, n_med) != ts.s1_blast(old["risk"], old["n_medium"]):
                    s1_diff.append((n, s, risk, old["risk"]))
    rate = hits / blasted if blasted else 0.0
    rows = sqlite3.connect(CACHE_DB).execute("select count(*) from blast_cache").fetchone()[0]
    res = {"designs": len(names), "candidates_blasted": blasted, "cache_hits": hits,
           "cache_hit_rate": round(rate, 4), "s1_compared": s1_n, "s1_different": len(s1_diff),
           "s1_differences": s1_diff[:20], "cache_rows_after": rows,
           "pass": rate >= 0.90 and not s1_diff}
    say("TRIAL " + json.dumps(res, ensure_ascii=False))
    return 0 if res["pass"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("offline")
    o.add_argument("--out", default=os.path.join(ROOT, "benchmark", "tiered_stage2c_offline.json"))
    t = sub.add_parser("trial")
    t.add_argument("--log", default=os.path.join(LOGS, "stage2c_trial.log"))
    a = ap.parse_args(argv)
    return {"offline": offline, "trial": trial}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
