"""deploy_check.py — the deploy/vercel container, measured and checked against the
local 4.0.0 freeze (steps 5–6). Not copied into the image.

  reference  python backend/scripts/deploy_check.py reference --out REF.json
             Designs the 20 hsa miRNAs of benchmark/tiered_design_timing.json on this
             machine (Flask test client, backend defaults, empty BLAST cache) and checks
             top 3 against that file and #1 against the freeze design records
             (outputs/freeze_matrix_4.0.0/cache/designs_hsa.jsonl when present).

  measure    python backend/scripts/deploy_check.py measure --image IMG [--ref REF.json]
             Docker, Vercel Hobby-like limits (--cpus=1 --memory=2g -e PORT=8080):
             (a) cold start: `docker start` → /api/health 200, on fresh containers;
             (b) /api/design for hsa-miR-21-5p, -16-5p, -221-3p on a fresh container
                 (empty BLAST cache); (c) peak RAM (cgroup memory.peak + docker stats);
             then the 20 reference designs on the same container, compared with REF
             (top 3 forward + grade + tiers + RT primer); then SIGTERM (docker stop) —
             time to exit, exit code, processes left.
             Writes benchmark/deploy_timing_vercel.json and benchmark/deploy_equivalence.json.

  compare    python backend/scripts/deploy_check.py compare REF.json OTHER.json
             The same comparison for two saved runs (e.g. a container run with --url).

  run-url    python backend/scripts/deploy_check.py run-url --url http://localhost:8080 --out X.json
             The 20 reference designs through HTTP against a running server.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
TIMING_REF = os.path.join(ROOT, "benchmark", "tiered_design_timing.json")
FREEZE_DESIGNS = os.path.join(ROOT, "outputs", "freeze_matrix_4.0.0", "cache", "designs_hsa.jsonl")
# top 3 of every hsa design at the freeze (backend/scripts/ui_top3_dump.py, 2026-11-18)
FREEZE_TOP3 = os.path.join(ROOT, "outputs", "freeze_cache", "ui_top3_hsa.jsonl.gz")
OUT_TIMING = os.path.join(ROOT, "benchmark", "deploy_timing_vercel.json")
OUT_EQUIV = os.path.join(ROOT, "benchmark", "deploy_equivalence.json")
TIMING_MIRNAS = ["hsa-miR-21-5p", "hsa-miR-16-5p", "hsa-miR-221-3p"]
DESIGN_LIMIT_S = 50.0          # the frontend waits 60 s (utils/designRequest.js)
RAM_LIMIT_MB = 1600.0


# ── shared ───────────────────────────────────────────────────────

def _mature_hsa() -> dict:
    sys.path.insert(0, BACKEND)
    from algorithm.specificity_check.overhang_collision import _load_index
    return {k: v.upper().replace("T", "U") for k, v in _load_index()["mature"]["hsa"].items()}


def _body(name: str, rna: str) -> dict:
    """The request of crossreactivity/design_all.py and design_equivalence.py:
    backend defaults (the API's, not the UI's)."""
    return {"thermodynamic": {}, "primerConstraints": {}, "qpcr": {}, "detectionMethod": {},
            "experimentalContext": {}, "sequence": {"matureSequence": rna, "mirnaId": name}}


def _reference_mirnas() -> list[str]:
    with open(TIMING_REF, encoding="utf-8") as f:
        return [d["mirna"] for d in json.load(f)["designs"]]


def _summary(status: int, resp: dict | None) -> dict:
    """What deploy_equivalence compares: per set forward, grade, tier totals, flags,
    detailed score; the RT primer; the ranking summary that decides the order."""
    resp = resp or {}
    sets = []
    for s in resp.get("top3") or []:
        r = s.get("ranking") or {}
        sets.append({
            "forward": s.get("sequence"),
            "grade": s.get("grade"),
            "specificity": (r.get("specificity") or {}).get("total"),
            "pcr": (r.get("pcr") or {}).get("total"),
            "flexible": (r.get("flexible") or {}).get("total"),
            "eliminated": r.get("eliminated"),
            "structure_veto": r.get("structure_veto"),
            "binding_floor_fail": r.get("binding_floor_fail"),
            "total_score": s.get("total_score"),
        })
    rs = resp.get("ranking_summary") or {}
    return {
        "status": status,
        "rt_primer": (resp.get("stemloop_rt") or {}).get("sequence"),
        "top3": sets,
        "ranking": {k: rs.get(k) for k in ("system", "blast_available", "specificity_fallback",
                                           "returned_sets", "candidates_scored",
                                           "eliminated_specificity", "screen_species")},
        "error": resp.get("error") if status != 200 else None,
    }


def _http(url: str, body: dict | None = None, timeout: float = 300) -> tuple[int, dict | None, float]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET",
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    dt = time.perf_counter() - t0
    try:
        return status, json.loads(raw), dt
    except ValueError:
        return status, None, dt


def _write(path: str, obj: dict) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"-> {os.path.relpath(path, ROOT)}")


# ── reference (this machine) ─────────────────────────────────────

def _freeze_top3_rows(names) -> dict:
    import gzip
    out = {}
    with gzip.open(FREEZE_TOP3, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["mirna"] in names:
                out[r["mirna"]] = [{
                    "forward": s["sequence"], "grade": s["grade"],
                    "specificity": s["ranking"]["specificity"]["total"],
                    "pcr": s["ranking"]["pcr"]["total"], "flexible": s["ranking"]["flexible"]["total"],
                    "eliminated": s["ranking"]["eliminated"],
                    "structure_veto": s["ranking"]["structure_veto"],
                    "binding_floor_fail": s["ranking"]["binding_floor_fail"]} for s in r["top3"]]
    return out


def reference(a) -> int:
    import tempfile
    a.out = os.path.abspath(a.out)
    tmp = tempfile.mkdtemp(prefix="deploy_ref_")
    os.environ["BLAST_CACHE_PATH"] = os.path.join(tmp, "blast_cache.sqlite")   # empty
    names = _reference_mirnas()
    hsa = _mature_hsa()
    os.chdir(BACKEND)
    import warnings
    warnings.filterwarnings("ignore")
    from app import app
    from algorithm.constants import ALGORITHM_VERSION
    client = app.test_client()
    designs = {}
    for i, n in enumerate(names, 1):
        t0 = time.time()
        r = client.post("/api/design", json=_body(n, hsa[n]))
        designs[n] = _summary(r.status_code, r.get_json(silent=True))
        print(f"{i:3}/{len(names)} {n:<20} {time.time() - t0:5.2f} s", flush=True)

    with open(TIMING_REF, encoding="utf-8") as f:
        timing = {d["mirna"]: d["top3"] for d in json.load(f)["designs"]}
    vs_timing = [n for n in names if [s["forward"] for s in designs[n]["top3"]] != timing[n]]
    vs_freeze, compared = [], 0
    if os.path.exists(FREEZE_DESIGNS):
        with open(FREEZE_DESIGNS, encoding="utf-8") as f:
            frz = {r["mirna"]: r for r in map(json.loads, f) if r["mirna"] in designs}
        for n, f_ in frz.items():
            compared += 1
            top = (designs[n]["top3"] or [{}])[0]
            if not (top.get("forward") == f_["forward_primer"] and top.get("grade") == f_["grade"]
                    and top.get("total_score") == f_["total_score"]
                    and designs[n]["rt_primer"] == f_["rt_primer"]):
                vs_freeze.append(n)
    vs_top3, compared3 = [], 0
    if os.path.exists(FREEZE_TOP3):
        frz3 = _freeze_top3_rows(set(names))
        for n, rows in frz3.items():
            compared3 += 1
            mine = [{k: v for k, v in s_.items() if k != "total_score"} for s_ in designs[n]["top3"]]
            if mine != rows:
                vs_top3.append(n)
    rel = lambda p: os.path.relpath(p, ROOT).replace(os.sep, "/")  # noqa: E731
    out = {
        "what": "local reference for deploy_equivalence: 20 hsa miRNAs of "
                "benchmark/tiered_design_timing.json, designed on this machine",
        "algorithm_version": ALGORITHM_VERSION,
        "machine": {"platform": platform.platform(), "python": platform.python_version()},
        "method": "POST /api/design through the Flask test client, backend defaults, "
                  "empty BLAST cache, sequential",
        "checks": {
            "top3_vs_freeze_ui_top3_dump": {
                "compared": compared3, "differ": vs_top3, "file": rel(FREEZE_TOP3) if compared3 else None,
                "fields": "forward, grade, specificity/pcr/flexible totals, eliminated, "
                          "structure_veto, binding_floor_fail of sets #1-#3"},
            "top1_vs_freeze_designs": {"compared": compared, "differ": vs_freeze,
                                       "file": rel(FREEZE_DESIGNS) if compared else None,
                                       "fields": "forward, grade, total_score, RT primer of #1"},
            "top3_vs_tiered_design_timing": {
                "compared": len(names), "differ": vs_timing,
                "note": "informational only: the top3 of benchmark/tiered_design_timing.json were "
                        "recorded at Giai đoạn 2 (commit af546b8), before QĐ 29–37 (Giai đoạn "
                        "2b/2c) changed the ranking; the freeze cites only its timing. The two "
                        "freeze checks above are the reference."},
        },
        "designs": designs,
    }
    _write(a.out, out)
    bad = bool(vs_freeze or vs_top3)
    print(json.dumps(out["checks"], indent=1))
    return 1 if bad else 0


# ── comparison ───────────────────────────────────────────────────

def _compare(ref: dict, other: dict) -> dict:
    rows, differ = [], []
    for n, r in ref["designs"].items():
        o = other["designs"].get(n)
        same = o is not None and o["status"] == r["status"] and o["rt_primer"] == r["rt_primer"] \
            and o["top3"] == r["top3"] and o["ranking"] == r["ranking"]
        if not same:
            diffs = []
            if o is None:
                diffs.append("missing")
            else:
                for k in ("status", "rt_primer", "ranking"):
                    if o[k] != r[k]:
                        diffs.append({"field": k, "local": r[k], "container": o[k]})
                for i in range(max(len(r["top3"]), len(o["top3"]))):
                    a_ = r["top3"][i] if i < len(r["top3"]) else None
                    b_ = o["top3"][i] if i < len(o["top3"]) else None
                    if a_ != b_:
                        diffs.append({"field": f"top3[{i}]", "local": a_, "container": b_})
            differ.append({"mirna": n, "diffs": diffs})
        rows.append({"mirna": n, "identical": same,
                     "forward_top3": [s["forward"] for s in r["top3"]],
                     "grades": [s["grade"] for s in r["top3"]],
                     "tiers": [[s["specificity"], s["pcr"], s["flexible"]] for s in r["top3"]]})
    return {"compared": len(ref["designs"]), "identical": len(ref["designs"]) - len(differ),
            "differ": differ, "rows": rows}


def compare(a) -> int:
    with open(a.ref, encoding="utf-8") as f:
        ref = json.load(f)
    with open(a.other, encoding="utf-8") as f:
        other = json.load(f)
    res = _compare(ref, other)
    print(json.dumps({k: res[k] for k in ("compared", "identical")}, indent=1))
    for d in res["differ"]:
        print(json.dumps(d, ensure_ascii=False))
    return 1 if res["differ"] else 0


def _run_url(url: str, names: list[str], hsa: dict) -> dict:
    designs, secs = {}, {}
    for i, n in enumerate(names, 1):
        status, body, dt = _http(f"{url}/api/design", _body(n, hsa[n]))
        designs[n] = _summary(status, body)
        secs[n] = round(dt, 2)
        print(f"{i:3}/{len(names)} {n:<20} HTTP {status} {dt:5.2f} s", flush=True)
    return {"designs": designs, "seconds": secs}


def run_url(a) -> int:
    out = _run_url(a.url.rstrip("/"), _reference_mirnas(), _mature_hsa())
    out["url"] = a.url
    _write(a.out, out)
    return 0


# ── measure (docker) ─────────────────────────────────────────────

def _docker(*args, check=True, capture=True) -> str:
    p = subprocess.run(["docker", *args], text=True, capture_output=capture)
    if check and p.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args)}: {p.stderr.strip()}")
    return (p.stdout or "").strip()


def _create(image: str, name: str, port: int) -> str:
    _docker("rm", "-f", name, check=False)
    return _docker("create", "--name", name, "--cpus=1", "--memory=2g", "-e", "PORT=8080",
                   "-p", f"{port}:8080", image)


def _wait_health(url: str, t0: float, limit: float = 120) -> float:
    while time.perf_counter() - t0 < limit:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=2) as r:
                if r.status == 200:
                    return time.perf_counter() - t0
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.05)
    raise RuntimeError("container did not become healthy")


def _mem_peak_mb(name: str) -> float | None:
    for path in ("/sys/fs/cgroup/memory.peak", "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"):
        out = _docker("exec", name, "cat", path, check=False)
        if out.strip().isdigit():
            return round(int(out) / 2**20, 1)
    return None


class _StatsSampler(threading.Thread):
    """docker stats every ~1 s; the maximum memory usage seen (MiB)."""

    def __init__(self, name: str):
        super().__init__(daemon=True)
        self.name_, self.max_mb, self.stop = name, 0.0, threading.Event()

    def run(self):
        units = {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024}
        while not self.stop.is_set():
            out = _docker("stats", "--no-stream", "--format", "{{.MemUsage}}", self.name_,
                          check=False)
            used = out.split("/")[0].strip() if out else ""
            for u, f in sorted(units.items(), key=lambda x: -len(x[0])):
                if used.endswith(u):
                    try:
                        self.max_mb = max(self.max_mb, float(used[:-len(u)]) * f)
                    except ValueError:
                        pass
                    break
            self.stop.wait(0.5)


def measure(a) -> int:
    url = f"http://127.0.0.1:{a.port}"
    hsa = _mature_hsa()
    info = {
        "image": a.image,
        "image_size_bytes": int(_docker("image", "inspect", "-f", "{{.Size}}", a.image)),
        "docker_version": _docker("version", "-f", "{{.Server.Version}}"),
        "host": {"platform": platform.platform(), "cpu_count": os.cpu_count()},
        "limits": {"cpus": 1, "memory": "2g", "env": {"PORT": "8080"}},
    }
    info["image_size_mb"] = round(info["image_size_bytes"] / 2**20, 1)

    # (a) cold start on fresh containers
    cold = []
    for i in range(a.cold_runs):
        name = f"pd-cold-{i}"
        _create(a.image, name, a.port)
        t0 = time.perf_counter()
        _docker("start", name)
        cold.append(round(_wait_health(url, t0), 2))
        _docker("rm", "-f", name)
        print(f"cold start {i + 1}: {cold[-1]} s", flush=True)

    # (b) designs on a fresh container, empty cache; (c) RAM
    name = "pd-measure"
    _create(a.image, name, a.port)
    t0 = time.perf_counter()
    _docker("start", name)
    start_s = round(_wait_health(url, t0), 2)
    sampler = _StatsSampler(name)
    sampler.start()
    designs = []
    for n in TIMING_MIRNAS:
        status, body, dt = _http(f"{url}/api/design", _body(n, hsa[n]))
        rs = (body or {}).get("ranking_summary") or {}
        tm = (body or {}).get("metadata", {}).get("timing_ms") if body else None
        designs.append({"mirna": n, "http": status, "seconds": round(dt, 2),
                        "blast_candidates": rs.get("blast_candidates"),
                        "blast_cache_hits": rs.get("blast_cache_hits"),
                        "top1": ((body or {}).get("top3") or [{}])[0].get("sequence"),
                        "server_timing_ms": tm})
        print(f"design {n}: HTTP {status} {dt:.2f} s", flush=True)
    processes_during = _docker("top", name, "-eo", "pid,ppid,args", check=False)

    # step 6 on the same container
    eq_run = None
    if a.ref:
        eq_run = _run_url(url, _reference_mirnas(), hsa)
    mem_peak = _mem_peak_mb(name)
    sampler.stop.set()
    sampler.join(timeout=5)

    # SIGTERM: graceful stop
    t0 = time.perf_counter()
    _docker("stop", "-t", "30", name)
    stop_s = round(time.perf_counter() - t0, 2)
    state = json.loads(_docker("inspect", "-f", "{{json .State}}", name))
    lp = subprocess.run(["docker", "logs", "--tail", "40", name], text=True, capture_output=True)
    logs = (lp.stdout or "") + (lp.stderr or "")
    _docker("rm", "-f", name, check=False)

    secs = [d["seconds"] for d in designs]
    timing = {
        **info,
        "what": "deploy/vercel container on Vercel Hobby-like limits (docs/… README Deploy)",
        "date": time.strftime("%Y-%m-%d"),
        "cold_start_seconds": {"runs": cold, "max": max(cold) if cold else None,
                               "definition": "docker start -> first HTTP 200 of /api/health"},
        "start_before_designs_seconds": start_s,
        "designs_empty_cache": designs,
        "design_seconds_max": max(secs),
        "design_limit_seconds": DESIGN_LIMIT_S,
        "design_within_limit": max(secs) <= DESIGN_LIMIT_S,
        "ram_peak_mb": {"cgroup_memory_peak": mem_peak, "docker_stats_max": round(sampler.max_mb, 1),
                        "limit_mb": RAM_LIMIT_MB,
                        "within_limit": (mem_peak or sampler.max_mb) <= RAM_LIMIT_MB,
                        "covers": "start + 3 timing designs" + (" + 20 equivalence designs"
                                                                 if eq_run else "")},
        "sigterm": {"docker_stop_seconds": stop_s, "exit_code": state.get("ExitCode"),
                    "oom_killed": state.get("OOMKilled"), "within_30s": stop_s < 30},
        "processes_during_run": processes_during.splitlines(),
        "log_tail": logs.splitlines()[-15:],
    }
    _write(OUT_TIMING, timing)

    rc = 0
    if eq_run:
        with open(a.ref, encoding="utf-8") as f:
            ref = json.load(f)
        res = _compare(ref, eq_run)
        equiv = {
            "what": "top 3 forward primers + grade + tiers + RT primer of the 20 hsa miRNAs of "
                    "benchmark/tiered_design_timing.json: container vs this machine",
            "date": time.strftime("%Y-%m-%d"),
            "image": a.image,
            "reference": {"file": os.path.relpath(a.ref, ROOT).replace(os.sep, "/"),
                          "machine": ref.get("machine"), "checks": ref.get("checks")},
            "container_seconds": eq_run["seconds"],
            "result": "identical" if not res["differ"] else "DIFFERENT",
            **res,
        }
        _write(OUT_EQUIV, equiv)
        rc = 1 if res["differ"] else 0
        print(f"equivalence: {res['identical']}/{res['compared']} identical")
    if not timing["design_within_limit"] or not timing["ram_peak_mb"]["within_limit"]:
        print("WARNING: a limit is exceeded — see the JSON", flush=True)
    return rc


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reference")
    r.add_argument("--out", required=True)
    m = sub.add_parser("measure")
    m.add_argument("--image", required=True)
    m.add_argument("--ref")
    m.add_argument("--port", type=int, default=8080)
    m.add_argument("--cold-runs", type=int, default=3)
    c = sub.add_parser("compare")
    c.add_argument("ref")
    c.add_argument("other")
    u = sub.add_parser("run-url")
    u.add_argument("--url", required=True)
    u.add_argument("--out", required=True)
    a = p.parse_args()
    return {"reference": reference, "measure": measure, "compare": compare, "run-url": run_url}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
