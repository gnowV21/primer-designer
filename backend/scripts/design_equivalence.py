"""design_equivalence.py — full design records of a fixed random set of hsa miRNAs, to
check that a performance change leaves every design byte-identical
(docs/REVIEW_panel_4.0.0.md §8, perf/design-speed).

  run:      python backend/scripts/design_equivalence.py run --out A.jsonl
            [--n 200] [--seed 2026] [--list benchmark/logs/design_equivalence_hsa200.txt]
  compare:  python backend/scripts/design_equivalence.py compare A.jsonl B.jsonl
            [--freeze outputs/freeze_matrix/cache/designs_hsa.jsonl]
  fields:   python backend/scripts/design_equivalence.py fields A.jsonl B.jsonl
            [--allow stemloop_rt.three_prime_isomir ...] [--show-pairs] [--out report.json]

`run` designs each miRNA through /api/design (Flask test client, the same request as
crossreactivity/design_all.py: backend defaults) in one process, sequentially. The
miRNA list is drawn once with the seed and written to --list; later runs read it.
Set BLAST_CACHE_PATH to a new empty file to make every design BLAST again.

Each record is the whole API response minus run-dependent fields (elapsed time,
BLAST timing and cache counters). `compare` reports every record that differs, and
with --freeze also compares #1 against the freeze design records.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
DEFAULT_LIST = os.path.join(ROOT, "benchmark", "logs", "design_equivalence_hsa200.txt")

# run-dependent, not part of the design
_DROP = {"elapsed_seconds", "timing_ms", "blast_cache_hits", "blast_cache_write_error"}


def _clean(x):
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items() if k not in _DROP}
    if isinstance(x, list):
        return [_clean(v) for v in x]
    return x


def _mirnas(n: int, seed: int, path: str) -> list[str]:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    sys.path.insert(0, BACKEND)
    from algorithm.specificity_check.overhang_collision import _load_index
    names = random.Random(seed).sample(sorted(_load_index()["mature"]["hsa"]), n)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {n} hsa miRNAs, random.Random({seed}).sample of the miRBase 22.1 hsa set "
                "(backend/scripts/design_equivalence.py)\n")
        f.write("\n".join(names) + "\n")
    return names


def run(a) -> int:
    names = _mirnas(a.n, a.seed, a.list)
    sys.path.insert(0, BACKEND)
    os.chdir(BACKEND)
    import warnings
    warnings.filterwarnings("ignore")
    from app import app
    from algorithm.specificity_check.overhang_collision import _load_index
    hsa = _load_index()["mature"]["hsa"]
    app.config["TESTING"] = True
    client = app.test_client()
    t_all = time.time()
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        for i, name in enumerate(names, 1):
            rna = hsa[name].upper().replace("T", "U")
            t0 = time.time()
            r = client.post("/api/design", json={
                "thermodynamic": {}, "primerConstraints": {}, "qpcr": {}, "detectionMethod": {},
                "experimentalContext": {}, "sequence": {"matureSequence": rna, "mirnaId": name}})
            rec = {"mirna": name, "status": r.status_code, "response": _clean(r.get_json(silent=True))}
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            print(f"{i:4}/{len(names)} {name:<22} {time.time() - t0:6.2f} s", flush=True)
    print(f"done in {time.time() - t_all:.0f} s -> {a.out}")
    return 0


def _load(path):
    with open(path, encoding="utf-8") as f:
        return {r["mirna"]: r for r in map(json.loads, f)}


def compare(a) -> int:
    x, y = _load(a.a), _load(a.b)
    diff = sorted(n for n in set(x) | set(y) if x.get(n) != y.get(n))
    out = {"records": [len(x), len(y)], "differ": len(diff), "differing": diff[:20]}
    if a.freeze:
        frz = _load(a.freeze)
        bad = []
        for n, r in y.items():
            top = ((r["response"] or {}).get("top3") or [None])[0]
            f = frz.get(n)
            if f is None:
                continue
            ok = (f["status"] == "ok") == bool(top)
            if ok and top:
                ok = (top["sequence"] == f["forward_primer"]
                      and r["response"]["stemloop_rt"]["sequence"] == f["rt_primer"]
                      and top["total_score"] == f["total_score"] and top["grade"] == f["grade"])
            if not ok:
                bad.append(n)
        out["vs_freeze_top1"] = {"compared": sum(n in frz for n in y), "differ": len(bad),
                                 "differing": bad[:20]}
    print(json.dumps(out, indent=1))
    return 1 if diff or out.get("vs_freeze_top1", {}).get("differ") else 0


def _walk(a, b, path, out):
    """Collect every difference between a and b as (path, kind, old, new). Lists of
    warning-like dicts (all carry "field") are matched by field, not by position, so
    a new warning does not shift the others; their path reads [field=<name>]."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            p = f"{path}.{k}" if path else k
            if k not in a:
                out.append((p, "added", None, b[k]))
            elif k not in b:
                out.append((p, "removed", a[k], None))
            else:
                _walk(a[k], b[k], p, out)
        return
    if isinstance(a, list) and isinstance(b, list):
        keyed = all(isinstance(x, dict) and "field" in x for x in a + b) and (a or b)
        if keyed:
            ga, gb = {}, {}
            for x in a:
                ga.setdefault(x["field"], []).append(x)
            for x in b:
                gb.setdefault(x["field"], []).append(x)
            for f in sorted(set(ga) | set(gb)):
                xa, xb = ga.get(f, []), gb.get(f, [])
                for i in range(max(len(xa), len(xb))):
                    p = f"{path}[field={f}]"
                    if i >= len(xa):
                        out.append((p, "added", None, xb[i]))
                    elif i >= len(xb):
                        out.append((p, "removed", xa[i], None))
                    else:
                        _walk(xa[i], xb[i], p, out)
            return
        if len(a) != len(b):
            out.append((f"{path}[]", "length", len(a), len(b)))
            return
        for x, y in zip(a, b):
            _walk(x, y, f"{path}[]", out)
        return
    if a != b:
        out.append((path, "changed", a, b))


def fields(a) -> int:
    """Field-by-field diff of two run outputs. Exit 1 if any differing path is outside
    the --allow prefixes."""
    x, y = _load(a.a), _load(a.b)
    by_path: dict = {}
    for n in sorted(set(x) | set(y)):
        out = []
        _walk(x.get(n), y.get(n), "", out)
        for p, kind, old, new in out:
            e = by_path.setdefault(p, {"records": set(), "kinds": set(), "pairs": {}})
            e["records"].add(n)
            e["kinds"].add(kind)
            if kind == "changed" and isinstance(old, str) and isinstance(new, str):
                e["pairs"][(old, new)] = e["pairs"].get((old, new), 0) + 1
            elif kind == "changed":
                e["pairs"].setdefault(("<non-string>", "<non-string>"), 0)
                e["pairs"][("<non-string>", "<non-string>")] += 1
    allowed = tuple(a.allow or ())
    report, outside = [], []
    for p, e in sorted(by_path.items()):
        ok = bool(allowed) and p.startswith(allowed)
        row = {"path": p, "records": len(e["records"]), "kinds": sorted(e["kinds"]),
               "string_pairs": len([k for k in e["pairs"] if k[0] != "<non-string>"]),
               "non_string_changes": e["pairs"].get(("<non-string>", "<non-string>"), 0),
               "allowed": ok}
        if a.show_pairs:
            row["pairs"] = [{"old": o, "new": nw, "records": c}
                            for (o, nw), c in e["pairs"].items() if o != "<non-string>"]
        report.append(row)
        if not ok:
            outside.append(p)
    res = {"records": [len(x), len(y)],
           "records_differing": len({r for e in by_path.values() for r in e["records"]}),
           "paths": report, "outside_allowed": outside}
    text = json.dumps(res, indent=1, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
    print(text if not a.out else json.dumps({k: res[k] for k in
                                             ("records", "records_differing", "outside_allowed")},
                                            indent=1))
    return 1 if outside else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", required=True)
    r.add_argument("--n", type=int, default=200)
    r.add_argument("--seed", type=int, default=2026)
    r.add_argument("--list", default=DEFAULT_LIST)
    c = sub.add_parser("compare")
    c.add_argument("a")
    c.add_argument("b")
    c.add_argument("--freeze", default=None)
    fl = sub.add_parser("fields", help="field-by-field diff (warnings matched by field)")
    fl.add_argument("a")
    fl.add_argument("b")
    fl.add_argument("--allow", action="append",
                    help="path prefix where differences are expected (repeatable)")
    fl.add_argument("--show-pairs", action="store_true", help="list every old -> new pair")
    fl.add_argument("--out", default=None, help="write the full report here")
    a = ap.parse_args(argv)
    return {"run": run, "compare": compare, "fields": fields}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
