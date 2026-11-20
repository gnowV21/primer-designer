"""freeze_pipeline.py — the one full pipeline run of the thesis freeze (PROMPT Phần 4.1).

Runs, at one commit and with a clean working tree, every data step of HANDOFF §7 and the
hsa cross-reactivity matrix, and records the provenance:

  1. Flask without the auto-reloader (HANDOFF §7), started and stopped by this script;
  2. validation (tiered) -> VALIDATION_REPORT.md -> benchmark validation block;
  3. validation --scoring-system v4 into benchmark/logs/freeze_v4/ (V4 regression);
  4. benchmark/run_benchmark.py (50 miRNAs, compare_tools.md);
  5. backend/scripts/export_benchmark_primers.py (224 published assays);
  6. backend/scripts/blast_tm_gate_sensitivity.py (BLAST directly, no Flask);
  7. crossreactivity design_all + build_matrix from scratch into outputs/freeze_matrix/
     (a fresh design cache, so every hsa design is made again by this commit);
     then plots + validate on the committed matrix.

Afterwards the regenerated files are compared with the committed ones (`git diff`), and
the fresh matrix with the committed matrix, by the caller. Provenance and step timings ->
benchmark/logs/freeze_run.json; step output -> benchmark/logs/freeze_<step>.log.

Usage (repo root):  python backend/scripts/freeze_pipeline.py [--skip matrix ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
LOGS = os.path.join(ROOT, "benchmark", "logs")
PY = sys.executable


def sh(cmd: list[str], **kw) -> str:
    return subprocess.check_output(cmd, cwd=ROOT, text=True, **kw).strip()


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def provenance() -> dict:
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    import primer3
    import RNA
    from algorithm import constants as K
    from algorithm.design_pipeline import _provenance
    db = os.path.join(ROOT, "backend", "data", "blast_db")
    db_files = sorted(f for f in os.listdir(db) if f.startswith("mirbase_multi"))
    h = hashlib.sha256()
    for f in db_files:
        h.update(f.encode())
        h.update(sha256(os.path.join(db, f)).encode())
    with open(os.path.join(db, "metadata.json"), encoding="utf-8") as f:
        db_meta = json.load(f)
    return {
        "started": datetime.now().isoformat(timespec="seconds"),
        "git_sha": sh(["git", "rev-parse", "HEAD"]),
        "git_branch": sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "working_tree_clean": sh(["git", "status", "--porcelain"]) == "",
        "algorithm_version": K.ALGORITHM_VERSION,
        "scoring_system_default": K.SCORING_SYSTEM_DEFAULT,
        "tiered_flags": {k: getattr(K, k) for k in ("TIERED_F4_FLOOR", "TIERED_GRADE_BY_TIERS",
                                                    "TIERED_V4_COMPLIANT_FIRST",
                                                    "TIERED_BINDING_FLOOR_VETO")},
        # engines, V4 weights / tiered thresholds fingerprints, miRBase release + mature.fa
        # sha256 — the same block every design carries in metadata.provenance
        "design_provenance": _provenance(),
        "python": sys.version.split()[0],
        "primer3_py": primer3.__version__,
        "viennarna": RNA.__version__,
        "blastn": sh(["blastn", "-version"]).splitlines()[0],
        "blast_db_metadata": db_meta,
        "blast_db_files_sha256": h.hexdigest(),
        "env_BLAST_CACHE_DISABLED": os.environ.get("BLAST_CACHE_DISABLED"),
        "env_SCORING_SYSTEM": os.environ.get("SCORING_SYSTEM"),
    }


def health() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:5000/api/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", nargs="*", default=[],
                    choices=["validation", "v4", "benchmark", "export", "sensitivity", "matrix"])
    ap.add_argument("--blast-cache", default=None,
                    help="BLAST cache file for this run (BLAST_CACHE_PATH), e.g. a new empty "
                         "file so every design BLASTs again; default: backend/data/blast_cache.sqlite")
    ap.add_argument("--log-prefix", default="freeze",
                    help="name of the run log and step logs (<prefix>_run.json, <prefix>_<step>.log); "
                         "a verification run uses another prefix so benchmark/logs/freeze_run.json "
                         "(the freeze record) is not overwritten")
    args = ap.parse_args(argv)
    os.makedirs(LOGS, exist_ok=True)
    if args.blast_cache:
        # Inherited by Flask and every step (step() passes os.environ).
        os.environ["BLAST_CACHE_PATH"] = os.path.abspath(args.blast_cache)
    prov = provenance()
    prov["blast_cache_path"] = os.environ.get("BLAST_CACHE_PATH") or "backend/data/blast_cache.sqlite"
    if not prov["working_tree_clean"]:
        print("STOP: the working tree is not clean; the freeze run must be at one commit.")
        return 2
    run = {"provenance": prov, "steps": []}
    out_path = os.path.join(LOGS, f"{args.log_prefix}_run.json")

    def save():
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(run, f, indent=1, ensure_ascii=False)
            f.write("\n")

    def step(name: str, cmd: list[str], cwd: str = ROOT) -> None:
        t0 = time.time()
        log = os.path.join(LOGS, f"{args.log_prefix}_{name}.log")
        with open(log, "w", encoding="utf-8") as f:
            rc = subprocess.call(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT,
                                 env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"})
        run["steps"].append({"step": name, "cmd": " ".join(cmd), "exit_code": rc,
                             "seconds": round(time.time() - t0, 1),
                             "log": os.path.relpath(log, ROOT).replace("\\", "/")})
        save()
        print(f"{name}: exit {rc} in {time.time() - t0:.0f}s", flush=True)

    flask = None
    needs_flask = {"validation", "v4", "benchmark", "export"} - set(args.skip)
    if needs_flask:
        if health():
            print("STOP: something already serves :5000; stop it first.")
            return 2
        flask_log = open(os.path.join(LOGS, f"{args.log_prefix}_flask.log"), "w", encoding="utf-8")
        flask = subprocess.Popen(
            [PY, "-c", "from app import app; app.run(host='127.0.0.1', port=5000, debug=False, "
                       "use_reloader=False, threaded=True)"],
            cwd=os.path.join(ROOT, "backend"), stdout=flask_log, stderr=subprocess.STDOUT)
        for _ in range(120):
            if health():
                break
            time.sleep(1)
        else:
            flask.terminate()
            print("STOP: Flask did not start")
            return 2
    try:
        if "validation" not in args.skip:
            step("validation", [PY, "validation/validate_primers.py"])
            step("validation_report", [PY, "backend/scripts/build_validation_report.py"])
            step("benchmark_validation_block", [PY, "validation/build_benchmark_validation.py", "--in-place"])
        if "v4" not in args.skip:
            v4 = os.path.join(LOGS, "freeze_v4")
            os.makedirs(v4, exist_ok=True)
            # validate_primers.py rewrites benchmark/logs/validation_blast_stats.json; the V4
            # run has no BLAST, so keep the tiered run's file.
            stats = os.path.join(LOGS, "validation_blast_stats.json")
            kept = open(stats, "rb").read() if os.path.exists(stats) else None
            step("validation_v4", [PY, "validation/validate_primers.py", "--scoring-system", "v4",
                                   "--out", os.path.join(v4, "results.csv"),
                                   "--json-out", os.path.join(v4, "results.json")])
            if kept is not None:
                with open(stats, "wb") as f:
                    f.write(kept)
        if "benchmark" not in args.skip:
            step("benchmark50", [PY, "run_benchmark.py"], cwd=os.path.join(ROOT, "benchmark"))
        if "export" not in args.skip:
            step("benchmark_export", [PY, "backend/scripts/export_benchmark_primers.py"])
    finally:
        if flask:
            flask.terminate()
            flask.wait(timeout=30)
    if "sensitivity" not in args.skip:
        step("blast_sensitivity", [PY, "backend/scripts/blast_tm_gate_sensitivity.py"])
    if "matrix" not in args.skip:
        fresh = os.path.join(ROOT, "outputs", "freeze_matrix")
        step("matrix_design_all", [PY, "-m", "crossreactivity.design_all", "--cache",
                                   os.path.join(fresh, "cache"), "--workers", "8"])
        step("matrix_build", [PY, "-m", "crossreactivity.build_matrix", "--cache",
                              os.path.join(fresh, "cache"), "--out", fresh, "--workers", "14"])
        step("matrix_plots", [PY, "-m", "crossreactivity.plots"])
        step("matrix_validate", [PY, "-m", "crossreactivity.validate"])
    run["finished"] = datetime.now().isoformat(timespec="seconds")
    save()
    bad = [s["step"] for s in run["steps"] if s["exit_code"] != 0]
    print(f"done; non-zero exits: {bad or 'none'} -> {out_path}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
