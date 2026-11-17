"""
scripts/blast_batch_equivalence.py — SPEC_scoring_tiered_4.0.0 QD 24b: the batched
BLAST check (check_offtarget_batch: one blastn multi-FASTA + one blastdbcmd per design)
must give, for every candidate, exactly what check_offtarget gives when called once
per primer — every hit, every field, and S1.

Runs on the Giai đoạn 1 BLAST sample (309 hsa miRNAs, 31,049 candidate calls = every
primer that run BLASTed; the miRNA list, pools and stored results come from
tiered_scoring_dryrun.py's cache). Also checks
the per-primer results against the S1 summaries stored by the Giai đoạn 1 run
(risk, MEDIUM-hit count, worst hit), i.e. that the refactor changed nothing.

    python backend/scripts/blast_batch_equivalence.py [--workers 14] [--limit N]

Writes benchmark/blast_batch_equivalence.json. Exits 1 on any difference, and when
BLAST (binary or DB) is not available.
"""
import argparse
import gzip
import json
import multiprocessing as mp
import os
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
CACHE = os.path.join(ROOT, "outputs", "freeze_cache")
POOLS = os.path.join(CACHE, "tiered_pools_hsa.jsonl.gz")
BLASTS = os.path.join(CACHE, "tiered_blast_hsa.jsonl.gz")
OUT = os.path.join(ROOT, "benchmark", "blast_batch_equivalence.json")


def _init():
    sys.path.insert(0, BACKEND)
    os.chdir(BACKEND)


def _s1_summary(o: dict) -> dict:
    summ = o["summary"]
    n_med = sum(h.get("risk") == "MEDIUM" for h in o["forward_primer_hits"]) + sum(
        v["risk"] == "MEDIUM" for v in o["identical_sequence_risk"].values())
    worst = next((h.get("subject_id") for h in o["forward_primer_hits"]
                  if h.get("risk") == summ["overall_risk"]), None)
    return {"risk": summ["overall_risk"], "n_medium": n_med, "worst": worst}


def _one(item):
    name, rna, rt, seqs, stored = item
    from algorithm.specificity_check.blast_offtarget import check_offtarget, check_offtarget_batch
    from algorithm.constants import UNIVERSAL_REVERSE
    kw = dict(mirna_id=name, target_sequence=rna, species="hsa", rt_primer=rt)
    t = time.perf_counter()
    single = {s: check_offtarget(s, UNIVERSAL_REVERSE, **kw) for s in seqs}
    t_single = time.perf_counter() - t
    t = time.perf_counter()
    batch = check_offtarget_batch(seqs, UNIVERSAL_REVERSE, **kw)
    t_batch = time.perf_counter() - t
    diffs, stored_diffs, hits = [], [], 0
    for s in seqs:
        a = json.dumps(single[s], sort_keys=True)
        b = json.dumps(batch.get(s), sort_keys=True)
        hits += len(single[s]["forward_primer_hits"])
        if a != b:
            diffs.append(s)
        old = stored.get(s)
        if old and {k: old.get(k) for k in ("risk", "n_medium", "worst")} != _s1_summary(single[s]):
            stored_diffs.append({"sequence": s, "stored": {k: old.get(k) for k in ("risk", "n_medium", "worst")},
                                 "now": _s1_summary(single[s])})
    return {"mirna": name, "calls": len(seqs), "non_safe_hits": hits, "diffs": diffs,
            "stored_diffs": stored_diffs, "seconds_single": round(t_single, 2),
            "seconds_batch": round(t_batch, 2)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--limit", type=int, default=0, help="only the first N miRNAs (smoke run)")
    a = ap.parse_args(argv)
    _init()
    from algorithm.specificity_check.blast_offtarget import blast_available
    ok, why = blast_available()
    if not ok:
        print(f"BLAST not available: {why}", file=sys.stderr)
        return 1
    stored = {}
    with gzip.open(BLASTS, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            stored[r["mirna"]] = r["results"]
    recs = {}
    with gzip.open(POOLS, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["mirna"] in stored:
                recs[r["mirna"]] = r
    names = sorted(stored)[: a.limit or None]
    # Every primer the Giai đoạn 1 run BLASTed for this miRNA (31,049): the current pool
    # plus the sequences of the pool before the F1-first fix (QD 22), all still valid
    # forward primers of that miRNA.
    items = [(n, recs[n]["rna"], recs[n]["rt_primer"],
              sorted(set(stored[n]) | {c["sequence"] for c in recs[n]["candidates"]}),
              stored[n]) for n in names]
    print(f"{len(items)} miRNAs, {sum(len(i[3]) for i in items)} candidate calls", flush=True)
    t0, rows = time.time(), []
    with mp.Pool(a.workers, initializer=_init) as p:
        for i, row in enumerate(p.imap_unordered(_one, items), 1):
            rows.append(row)
            if i % 25 == 0 or i == len(items):
                print(f"  {i}/{len(items)}  {time.time() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: r["mirna"])
    n_calls = sum(r["calls"] for r in rows)
    n_diff = sum(len(r["diffs"]) for r in rows)
    n_stored = sum(len(r["stored_diffs"]) for r in rows)
    out = {
        "spec": "docs/SPEC_scoring_tiered_4.0.0.md QD 24b",
        "comparison": "json.dumps(check_offtarget(primer), sort_keys=True) == "
                      "json.dumps(check_offtarget_batch(pool)[primer], sort_keys=True) — "
                      "every hit and every field, incl. S1 (summary.overall_risk)",
        "mirnas": len(rows), "calls": n_calls,
        "non_safe_hits_compared": sum(r["non_safe_hits"] for r in rows),
        "calls_different": n_diff,
        "stored_giai_doan_1_s1_different": n_stored,
        "seconds_single_total": round(sum(r["seconds_single"] for r in rows), 1),
        "seconds_batch_total": round(sum(r["seconds_batch"] for r in rows), 1),
        "note": f"{a.workers} parallel workers; per-design times include both runs' contention",
        "differences": [r for r in rows if r["diffs"] or r["stored_diffs"]],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({k: v for k, v in out.items() if k != "differences"}, indent=1, ensure_ascii=False))
    return 1 if (n_diff or n_stored) else 0


if __name__ == "__main__":
    sys.exit(main())
