"""
scripts/tiered_stage3_checks.py — Giai đoạn 3 step C of docs/SPEC_scoring_tiered_4.0.0.md:
after the hsa matrix run has filled the BLAST sqlite cache (QD 37), check that the S1
of every candidate the pipeline BLASTed equals the Giai đoạn 2 offline BLAST
(outputs/freeze_cache/tiered_blast_full_hsa.jsonl.gz), on every hsa design.

    python backend/scripts/tiered_stage3_checks.py cache-s1 [--out benchmark/tiered_stage3_cache_s1.json]

The cache key is built with tiered_pipeline.cache_context and the same inputs the
pipeline uses for a default hsa design (target, species hsa, RT primer, default salt,
universal reverse, BLAST DB build date, miRNA name). Candidates the pipeline does not
BLAST (eliminated by S2 outside a fallback) are counted as not in the cache.
"""
import argparse
import gzip
import json
import os
import sqlite3
import sys
from collections import Counter

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "scripts"))


def cache_s1(a):
    os.chdir(BACKEND)
    import warnings
    warnings.filterwarnings("ignore")
    import tiered_stage2_report as S2
    from algorithm import tiered_scoring as ts
    from algorithm import tiered_pipeline as tp
    from algorithm.constants import UNIVERSAL_REVERSE
    from algorithm.thermodynamics import _get_p3_params
    from algorithm.specificity_check.blast_cache import BlastCache

    p3 = {k: _get_p3_params({})[k] for k in ("mv_conc", "dv_conc", "dntp_conc", "dna_conc")}
    db_version = tp._blast_db_version()
    cache = BlastCache()
    rows = sqlite3.connect(cache.db_path).execute("select count(*) from blast_cache").fetchone()[0]
    stored = {}
    with gzip.open(S2.BLAST_FULL, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            stored[r["mirna"]] = r["results"]
    n_designs = n_cand = found = 0
    diff_level, diff_risk = [], []
    per_design_found = Counter()
    for rec in S2._load_pools():
        seqs = [c["sequence"] for c in rec["candidates"] if c["in_tiered_pool"]]
        if not seqs:
            continue
        n_designs += 1
        n_cand += len(seqs)
        ctx = tp.cache_context(rec["rna"], "hsa", rec["rt_primer"], p3)
        got = cache.get_results(seqs, UNIVERSAL_REVERSE, db_version, rec["mirna"], ctx)
        found += len(got)
        per_design_found["all" if len(got) == len(seqs) else "some" if got else "none"] += 1
        for s, res in got.items():
            risk, n_med, _ = ts.blast_s1_inputs(res)
            old = stored[rec["mirna"]][s]
            if ts.s1_blast(risk, n_med) != ts.s1_blast(old["risk"], old["n_medium"]):
                diff_level.append({"mirna": rec["mirna"], "sequence": s, "cache": [risk, n_med],
                                   "offline": [old["risk"], old["n_medium"]]})
            elif risk != old["risk"] or n_med != old["n_medium"]:
                diff_risk.append({"mirna": rec["mirna"], "sequence": s})
    out = {"spec": "docs/SPEC_scoring_tiered_4.0.0.md Giai đoạn 3 C (QD 37)",
           "cache_rows": rows, "designs": n_designs, "pool_candidates": n_cand,
           "candidates_in_cache": found,
           "designs_with_all_some_none_candidates_in_cache": dict(per_design_found),
           "s1_level_different": len(diff_level), "risk_or_medium_count_different": len(diff_risk),
           "examples": diff_level[:20],
           "note": ("Candidates not in the cache were not BLASTed by the pipeline (S2 "
                    "eliminated them outside a fallback design) or the design failed."),
           "pass": not diff_level and not diff_risk}
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({k: v for k, v in out.items() if k != "examples"}, indent=1, ensure_ascii=False))
    return 0 if out["pass"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cache-s1")
    c.add_argument("--out", default=os.path.join(ROOT, "benchmark", "tiered_stage3_cache_s1.json"))
    a = ap.parse_args(argv)
    return {"cache-s1": cache_s1}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
