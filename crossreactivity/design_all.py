"""
design_all.py — design primer set #1 for every mature miRNA of one species.

Each worker process imports the Flask app and calls POST /api/design through the
test client, so the request is exactly what a user (or validation/validate_primers.py)
sends — same parsing, same defaults. Every process has its own primer3 state: the
process-wide lock in primer3_safe.py only serializes threads inside one process.

Resumable: one JSON line per miRNA in <cache>/designs_<species>.jsonl; names already
there are skipped on the next run, unless the record was made by a different
algorithm version (ALGORITHM_VERSION) — those are designed again. Failures are kept
with their reason. The file is compacted to one line per miRNA at the end.

Usage (repo root):
    python -m crossreactivity.design_all [--species hsa] [--workers 14] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time

from crossreactivity.model import CONFIG_PATH, load_config, load_mature

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_CACHE = os.path.join(_ROOT, "outputs", "crossreactivity_cache")
STEMLOOP_BODY_LEN = 44

_client = None
_request = None
_version = None


def current_algorithm_version() -> str:
    backend = os.path.join(_ROOT, "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from algorithm.constants import ALGORITHM_VERSION
    return ALGORITHM_VERSION


def _init_worker(design_request: dict):
    global _client, _request, _version
    backend = os.path.join(_ROOT, "backend")
    sys.path.insert(0, backend)
    os.chdir(backend)                         # the app resolves data paths from here
    from app import app
    app.config["TESTING"] = True
    _client = app.test_client()
    _request = {k: v for k, v in design_request.items() if not k.startswith("_")}
    _version = current_algorithm_version()


def design_one(item: tuple[str, str]) -> dict:
    name, seq_dna = item
    rna = seq_dna.replace("T", "U")
    body = {**_request, "sequence": {"matureSequence": rna, "mirnaId": name}}
    t0 = time.time()
    try:
        r = _client.post("/api/design", json=body)
        data = r.get_json(silent=True) or {}
    except Exception as e:                     # a crash must not stop the batch
        return {"mirna": name, "sequence": seq_dna, "status": "failed",
                "reason": f"exception: {e!r}", "seconds": round(time.time() - t0, 2),
                "algorithm_version": _version}
    rec = {"mirna": name, "sequence": seq_dna, "seconds": round(time.time() - t0, 2),
           "algorithm_version": _version}
    top = (data.get("top3") or [None])[0]
    if r.status_code != 200 or not top:
        reason = data.get("error") or f"HTTP {r.status_code}"
        if data.get("rejection_summary"):
            reason += f" — rejections: {data['rejection_summary']}"
        return {**rec, "status": "failed", "reason": reason}
    rt = (data.get("stemloop_rt") or {}).get("sequence", "")
    meta = data.get("metadata") or {}
    return {
        **rec,
        "status": "ok",
        "rt_primer": rt,
        "overhang_len": len(rt) - STEMLOOP_BODY_LEN,
        "forward_primer": top["sequence"],
        "fwd_specific_len": top["specific_length"],
        "tail_length": top.get("tail_length"),
        "total_score": top.get("total_score"),
        "grade": top.get("grade"),
        "algorithm_version": meta.get("algorithm_version") or _version,
    }


def read_done(path: str) -> dict[str, dict]:
    done = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    done[rec["mirna"]] = rec
    return done


def select_todo(mature: dict[str, str], done: dict[str, dict], version: str) -> list:
    """miRNAs to design: not cached, or cached by another algorithm version."""
    return [(n, s) for n, s in sorted(mature.items())
            if n not in done or done[n].get("algorithm_version") != version]


def compact(path: str) -> None:
    """Rewrite the cache with the latest record per miRNA (later lines win)."""
    latest = read_done(path)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        for name in sorted(latest):
            f.write(json.dumps(latest[name], ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=CONFIG_PATH)
    ap.add_argument("--species", default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--limit", type=int, default=None, help="first N miRNAs (testing)")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    species = args.species or cfg["species"]
    workers = args.workers or cfg.get("workers") or max(1, (os.cpu_count() or 2) - 2)
    mature = load_mature(cfg["mirbase_index_path"], species)
    os.makedirs(args.cache, exist_ok=True)
    out_path = os.path.join(args.cache, f"designs_{species}.jsonl")

    version = current_algorithm_version()
    done = read_done(out_path)
    todo = select_todo(mature, done, version)
    n_stale = sum(1 for n, _ in todo if n in done)
    if args.limit is not None:
        todo = todo[: max(0, args.limit - (len(mature) - len(todo)))]
    print(f"{species}: {len(mature)} miRNAs, {len(done) - n_stale} cached at {version}, "
          f"{n_stale} cached by another version, {len(todo)} to design "
          f"({workers} workers)", flush=True)

    t0 = time.time()
    with open(out_path, "a", encoding="utf-8") as out, \
            mp.Pool(workers, initializer=_init_worker, initargs=(cfg["design_request"],)) as pool:
        for i, rec in enumerate(pool.imap_unordered(design_one, todo, chunksize=4), 1):
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            if i % 100 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  {time.time() - t0:.0f}s", flush=True)

    compact(out_path)
    done = read_done(out_path)
    n_ok = sum(r["status"] == "ok" for r in done.values())
    print(f"done: {n_ok} designed, {len(done) - n_ok} failed -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
