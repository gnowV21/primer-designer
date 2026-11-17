"""
scripts/tiered_design_timing.py — SPEC_scoring_tiered_4.0.0 QD 24c / QD 12: time of one
uncached tiered design on this machine.

20 random hsa miRNAs (miRBase 22.1 overhang index, random.Random(2026)), backend
defaults, the design pipeline run in-process one design at a time, BLAST cache off
(BLAST_CACHE_DISABLED=1). One warm-up design first (module data loaded once per
backend process, as on a running server); it is reported but not counted.

    python backend/scripts/tiered_design_timing.py [--n 20] [--system tiered]

Writes benchmark/tiered_design_timing.json (p50, p90, max, per-design BLAST time).
Run with nothing else loading the CPU. Exits 1 if BLAST is unavailable or p50 > 15 s.
"""
import argparse
import json
import os
import platform
import random
import statistics as st
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
OUT = os.path.join(ROOT, "benchmark", "tiered_design_timing.json")
SEED = 2026
WARMUP = "hsa-miR-16-5p"
LIMIT_S = 15.0


def _pct(xs, q):
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 2)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--system", choices=["tiered", "v4"], default="tiered")
    a = ap.parse_args(argv)
    os.environ["BLAST_CACHE_DISABLED"] = "1"
    sys.path.insert(0, BACKEND)
    os.chdir(BACKEND)
    import warnings
    warnings.filterwarnings("ignore")
    from algorithm.design_pipeline import run
    from algorithm.constants import ALGORITHM_VERSION, BLAST_BATCH_PROCESSES
    from algorithm.specificity_check.blast_offtarget import blast_available
    from algorithm.specificity_check.overhang_collision import _load_index

    ok, why = blast_available()
    if not ok:
        print(f"BLAST not available: {why}", file=sys.stderr)
        return 1
    hsa = _load_index()["mature"]["hsa"]
    # Shuffled once with the fixed seed; miRNAs without any forward candidate (the
    # design returns an error in ~0.1 s) are skipped and listed, so the statistics are
    # over a.n real designs.
    order = random.Random(SEED).sample(sorted(n for n in hsa if n != WARMUP), len(hsa) - 1)

    def one(name):
        rna = hsa[name].upper().replace("T", "U")
        t = time.perf_counter()
        r = run(rna, {"scoringSystem": a.system}, name)
        dt = time.perf_counter() - t
        rs = r.get("ranking_summary") or {}
        if rs and not rs.get("blast_available"):
            raise SystemExit(f"BLAST unavailable during the run: {rs.get('blast_unavailable_reason')}")
        return {"mirna": name, "seconds": round(dt, 2),
                "blast_seconds": round(rs["timing_ms"]["blast"] / 1000, 2) if rs else None,
                "candidates": rs.get("candidates_scored"), "blasted": rs.get("blast_candidates"),
                "top3": [s["sequence"] for s in r.get("top3", [])],
                "error": r.get("error")}

    warm = one(WARMUP)
    rows, skipped = [], []
    for n in order:
        if len(rows) == a.n:
            break
        row = one(n)
        if row["error"]:
            skipped.append({"mirna": n, "error": row["error"], "seconds": row["seconds"]})
            print(f"  skip {n:<22} (no design: {row['error'][:60]})", flush=True)
            continue
        rows.append(row)
        print(f"  {len(rows):2}/{a.n} {n:<22} {row['seconds']:6.2f} s "
              f"(BLAST {row['blast_seconds']} s, {row['candidates']} cand.)", flush=True)
    secs = [r["seconds"] for r in rows]
    bl = [r["blast_seconds"] for r in rows if r["blast_seconds"] is not None]
    out = {
        "spec": "docs/SPEC_scoring_tiered_4.0.0.md QD 12, QD 24c",
        "algorithm_version": ALGORITHM_VERSION, "scoring_system": a.system,
        "machine": {"platform": platform.platform(), "python": platform.python_version(),
                    "cpu_count": os.cpu_count(), "blast_batch_processes": BLAST_BATCH_PROCESSES},
        "method": (f"the first {a.n} hsa miRNAs with a design in random.Random({SEED}) order "
                   "of the miRBase 22.1 hsa set; design_pipeline.run in-process, sequential, "
                   "backend defaults, BLAST cache disabled; one warm-up design not counted"),
        "warmup": warm,
        "skipped_no_candidates": skipped,
        "seconds": {"p50": _pct(secs, 0.5), "p90": _pct(secs, 0.9), "min": min(secs),
                    "max": max(secs), "mean": round(st.mean(secs), 2)},
        "blast_seconds": ({"p50": _pct(bl, 0.5), "p90": _pct(bl, 0.9), "max": max(bl)}
                          if bl else None),
        "limit_s": LIMIT_S,
        "passes": _pct(secs, 0.5) <= LIMIT_S,
        "designs": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({k: out[k] for k in ("seconds", "blast_seconds", "passes")}, indent=1))
    return 0 if out["passes"] else 1


if __name__ == "__main__":
    sys.exit(main())
