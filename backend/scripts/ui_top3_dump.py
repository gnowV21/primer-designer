"""ui_top3_dump.py — the API's top 3 for every hsa miRNA, for the frontend key check.

docs/SPEC_ui_tiered_4.0.0.md §3: the frontend's tier comparator must give the same order
as the backend on the 2472 hsa designs. This script calls POST /api/design (Flask test
client, the crossreactivity matrix request, so the BLAST cache built by the matrix run
answers every candidate) and keeps, per design, the fields the comparator reads:
ranking, v4_rule_violations, sequence, rank, grade. frontend/scripts/check_tier_order.mjs
then applies the frontend comparator.

Output: outputs/freeze_cache/ui_top3_hsa.jsonl.gz (one design per line; ignored by git
like the other freeze caches) and a summary on stdout.

Usage (repo root):
    python backend/scripts/ui_top3_dump.py [--workers 8] [--limit N]
"""
from __future__ import annotations

import argparse
import gzip
import json
import multiprocessing as mp
import os
import sys
import time

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, _ROOT)

from crossreactivity import design_all as da  # noqa: E402
from crossreactivity.model import load_config, load_mature  # noqa: E402

OUT = os.path.join(_ROOT, "outputs", "freeze_cache", "ui_top3_hsa.jsonl.gz")
KEEP = ("rank", "sequence", "grade", "ranking", "v4_rule_violations", "selection")


def dump_one(item: tuple[str, str]) -> dict:
    name, seq_dna = item
    body = {**da._request, "sequence": {"matureSequence": seq_dna.replace("T", "U"),
                                        "mirnaId": name}}
    r = da._client.post("/api/design", json=body)
    data = r.get_json(silent=True) or {}
    top3 = data.get("top3") or []
    rs = data.get("ranking_summary") or {}
    return {"mirna": name, "status": r.status_code,
            "blast_available": rs.get("blast_available"),
            "blast_candidates": rs.get("blast_candidates"),
            "blast_cache_hits": rs.get("blast_cache_hits"),
            "top3": [{k: s.get(k) for k in KEEP} for s in top3]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    cfg = load_config(da.CONFIG_PATH)
    mature = load_mature(cfg["mirbase_index_path"], cfg["species"])
    todo = sorted(mature.items())[: args.limit]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    t0, n, ok, hits, blasted = time.time(), 0, 0, 0, 0
    with gzip.open(OUT, "wt", encoding="utf-8") as out, \
            mp.Pool(args.workers, initializer=da._init_worker,
                    initargs=(cfg["design_request"],)) as pool:
        for rec in pool.imap(dump_one, todo, chunksize=4):
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
            ok += rec["status"] == 200 and bool(rec["top3"])
            hits += rec["blast_cache_hits"] or 0
            blasted += rec["blast_candidates"] or 0
            if n % 200 == 0 or n == len(todo):
                print(f"  {n}/{len(todo)}  {time.time() - t0:.0f}s  designed {ok}  "
                      f"cache hit {hits}/{blasted}", flush=True)
    print(f"done: {ok} designs with a top 3 of {n} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
