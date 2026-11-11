"""
build_matrix.py — the assay-level cross-reactivity matrix R(i, j) for one species.

Rows are the assays from design_all.py (primer set #1 of every miRNA designed);
columns are every mature miRNA of the species in the same miRBase index.

Screen: for every pair the ΔCq is first computed WITHOUT the forward duplex-Tm term.
That value is a lower bound of the exact ΔCq (ΔCq_FWD = max(table, Tm term)), so a
pair whose lower bound already reaches the NONE level (≥ 10 Cq) is NONE for certain
and needs no primer3 call. Only the remaining pairs are scored exactly, with ΔG.

Resumable: each worker writes one JSON-lines file per block of assays to the cache;
blocks already present are skipped. A block file is named after a digest of its
assays (miRNA, primers) and the algorithm version, so a block is never reused after
the designs or the algorithm change. Designs made by another algorithm version are
refused — run design_all again.

Usage (repo root):
    python -m crossreactivity.build_matrix [--workers 14]
Writes outputs/crossreactivity_long.{parquet,csv}, outputs/crossreactivity_metadata.json,
outputs/crossreactivity_row_stats.csv, outputs/crossreactivity_failed_designs.csv,
outputs/crossreactivity_top30_offdiagonal.csv.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time

from crossreactivity.design_all import DEFAULT_CACHE, read_done
from crossreactivity.model import (
    CONFIG_PATH, Assay, AssayScorer, index_metadata, load_config, load_mature,
)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(_ROOT, "outputs")
BLOCK = 32

COLUMNS = ["assay_mirna", "target_mirna", "R", "level", "p_RT", "p_PCR", "rt_shift",
           "rt_mismatches", "rt_3p_class", "pcr_mismatches", "pcr_3p_class", "dG_rt",
           "dG_pcr", "approx_hybrid", "mirbase_version", "tool_version",
           # extra context
           "delta_cq", "pcr_shift", "category"]

_W: dict = {}


def _init_worker(cfg: dict):
    _W["cfg"] = cfg
    _W["mature"] = load_mature(cfg["mirbase_index_path"], cfg["species"])
    _W["release"] = cfg["mirbase_release"]


def block_filename(block_id: int, assays: list[dict], tool_version: str) -> str:
    """Cache file name tied to the block's content and the algorithm version."""
    key = json.dumps([tool_version] + [[a["mirna"], a["sequence"], a["rt_primer"],
                                        a["forward_primer"], a["fwd_specific_len"]]
                                       for a in assays])
    return f"block_{block_id:04d}_{hashlib.sha256(key.encode()).hexdigest()[:12]}.jsonl"


def score_block(job: tuple[int, list[dict], str, str]) -> str:
    """Score a block of assays against every miRNA; write the block's cache file."""
    block_id, assays, cache_dir, tool_version = job
    cfg, mature = _W["cfg"], _W["mature"]
    none_at = cfg["levels"]["low_below_delta_cq"]
    path = os.path.join(cache_dir, block_filename(block_id, assays, tool_version))
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as out:
        for a in assays:
            assay = Assay(a["mirna"], a["sequence"], a["overhang_len"],
                          a["fwd_specific_len"], a["forward_primer"], a["rt_primer"])
            scorer = AssayScorer(assay, cfg, cfg["design_request"].get("qpcr"))
            stats = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "NONE": 0, "screened_out": 0}
            diag_r, max_off = None, 0.0
            for name, seq in mature.items():
                if scorer.lower_bound(seq) >= none_at:
                    stats["NONE"] += 1
                    stats["screened_out"] += 1
                    continue
                rec = scorer.score(name, seq)
                stats[rec["level"]] += 1
                if name == a["mirna"]:
                    diag_r = rec["R"]
                elif rec["R"] > max_off:
                    max_off = rec["R"]
                if rec["level"] != "NONE":
                    rec["mirbase_version"] = _W["release"]
                    rec["tool_version"] = tool_version
                    out.write(json.dumps({"kind": "pair", **rec}) + "\n")
            out.write(json.dumps({"kind": "row", "assay_mirna": a["mirna"], **stats,
                                  "diag_R": diag_r, "max_offdiag_R": max_off,
                                  "diag_is_max": diag_r is not None and diag_r >= max_off})
                      + "\n")
    os.replace(tmp, path)
    return path


def _git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=_ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=CONFIG_PATH)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args(argv)

    import pandas as pd

    sys.path.insert(0, os.path.join(_ROOT, "backend"))
    from algorithm.constants import ALGORITHM_VERSION

    cfg = load_config(args.config)
    species = cfg["species"]
    workers = args.workers or cfg.get("workers") or max(1, (os.cpu_count() or 2) - 2)
    designs = read_done(os.path.join(args.cache, f"designs_{species}.jsonl"))
    mature = load_mature(cfg["mirbase_index_path"], species)
    if not designs:
        print("no designs — run python -m crossreactivity.design_all first")
        return 1
    missing = sorted(set(mature) - set(designs))
    if missing:
        print(f"{len(missing)} miRNAs not designed yet — run design_all again first")
        return 1
    stale = sorted(n for n, d in designs.items() if d.get("algorithm_version") != ALGORITHM_VERSION)
    if stale:
        print(f"{len(stale)} designs were made by another algorithm version than "
              f"{ALGORITHM_VERSION} — run python -m crossreactivity.design_all again first")
        return 1
    ok = [d for _, d in sorted(designs.items()) if d["status"] == "ok"]
    failed = [d for _, d in sorted(designs.items()) if d["status"] != "ok"]

    block_dir = os.path.join(args.cache, f"matrix_{species}")
    os.makedirs(block_dir, exist_ok=True)
    blocks = [ok[i:i + BLOCK] for i in range(0, len(ok), BLOCK)]
    block_paths = [os.path.join(block_dir, block_filename(b, blk, ALGORITHM_VERSION))
                   for b, blk in enumerate(blocks)]
    jobs = [(b, blk, block_dir, ALGORITHM_VERSION) for b, blk in enumerate(blocks)
            if not os.path.exists(block_paths[b])]
    print(f"{len(ok)} assays × {len(mature)} miRNAs; {len(blocks) - len(jobs)} blocks cached, "
          f"{len(jobs)} to score ({workers} workers)", flush=True)
    t0 = time.time()
    if jobs:
        with mp.Pool(workers, initializer=_init_worker, initargs=(cfg,)) as pool:
            for i, _ in enumerate(pool.imap_unordered(score_block, jobs), 1):
                if i % 10 == 0 or i == len(jobs):
                    print(f"  {i}/{len(jobs)} blocks  {time.time() - t0:.0f}s", flush=True)

    pairs, rows = [], []
    for path in block_paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                (pairs if rec.pop("kind") == "pair" else rows).append(rec)
    long = pd.DataFrame(pairs)[COLUMNS].sort_values(["assay_mirna", "R"], ascending=[True, False])
    row_stats = pd.DataFrame(rows).sort_values("assay_mirna")
    bad_diag = row_stats[~row_stats["diag_is_max"]]
    if len(bad_diag):
        print(f"MODEL CHECK FAILED: R(i,i) is not the row maximum for {len(bad_diag)} assays")

    os.makedirs(args.out, exist_ok=True)
    long.to_parquet(os.path.join(args.out, "crossreactivity_long.parquet"), index=False)
    long.to_csv(os.path.join(args.out, "crossreactivity_long.csv"), index=False)
    row_stats.to_csv(os.path.join(args.out, "crossreactivity_row_stats.csv"), index=False)
    # Highest-risk pairs between DIFFERENT molecules: same_sequence entries are the
    # target under another miRBase name (R = 1 by construction), not off-targets.
    distinct = long[(long["assay_mirna"] != long["target_mirna"])
                    & (long["category"] != "same_sequence")]
    distinct.sort_values(["R", "assay_mirna", "target_mirna"], ascending=[False, True, True]) \
        .head(30).to_csv(os.path.join(args.out, "crossreactivity_top30_offdiagonal.csv"),
                         index=False)
    pd.DataFrame(failed)[["mirna", "sequence", "reason"]].to_csv(
        os.path.join(args.out, "crossreactivity_failed_designs.csv"), index=False)

    n_pairs = len(ok) * len(mature)
    level_counts = long["level"].value_counts().to_dict()
    level_counts["NONE"] = n_pairs - len(long)
    meta = {
        "run_date": dt.datetime.now().isoformat(timespec="seconds"),
        "tool_version": ALGORITHM_VERSION,
        "git_commit": _git_commit(),
        "species": species,
        "mirbase": index_metadata(cfg["mirbase_index_path"]),
        "config": cfg,
        "n_mirnas": len(mature),
        "n_assays": len(ok),
        "n_failed_designs": len(failed),
        "n_pairs": n_pairs,
        "n_pairs_stored": len(long),
        "pairs_by_level": level_counts,
        "n_pairs_screened_out": int(row_stats["screened_out"].sum()),
        "diagonal_check": {"passed": bool(len(bad_diag) == 0),
                           "failing_assays": bad_diag["assay_mirna"].tolist()},
        "model": ("R = 2^-ΔCq_assay = p_RT × p_PCR, ΔCq from the webtool's assay model "
                  "(backend/algorithm/specificity_check/assay_model.py), not wet-lab calibrated"),
        "files": ["crossreactivity_long.parquet", "crossreactivity_long.csv",
                  "crossreactivity_row_stats.csv", "crossreactivity_failed_designs.csv",
                  "crossreactivity_top30_offdiagonal.csv"],
        "seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(args.out, "crossreactivity_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    print(json.dumps({k: meta[k] for k in ("n_assays", "n_failed_designs", "n_pairs",
                                          "n_pairs_stored", "pairs_by_level",
                                          "diagonal_check")}, indent=1))
    return 0 if len(bad_diag) == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
