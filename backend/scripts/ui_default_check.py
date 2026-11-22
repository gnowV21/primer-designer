"""ui_default_check.py — does the web UI at its defaults return the frozen 4.0.0 primers?

The UI body comes from the frontend itself (node frontend/scripts/ui_default_body.mjs,
i.e. DEFAULTS + buildDesignBody), so this checks what the form really sends. The same
20 hsa miRNAs as tiered_design_timing.py (random.Random(2026) order of the miRBase 22.1
hsa set, first 20 with a design under the API defaults) plus hsa-miR-210-5p are designed
through the Flask test client with the BLAST cache disabled (nothing is written), and the
#1 set and the top 3 are compared with the frozen API-default designs
(outputs/freeze_cache/ui_top3_hsa.jsonl.gz).

Writes the "after" block of benchmark/ui_default_vs_api_hsa20.json; the "designs" block
written by the Step 0 check (2026-11-22, UI defaults Na+ 50 + K+ 50 mM + pH 8.4) is kept as
the "before" record.

Usage (repo root):  python backend/scripts/ui_default_check.py
Exit code 1 unless every #1 and top 3 matches and hsa-miR-210-5p is designed.
"""
from __future__ import annotations

import gzip
import json
import os
import random
import subprocess
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
FREEZE = os.path.join(ROOT, "outputs", "freeze_cache", "ui_top3_hsa.jsonl.gz")
OUT = os.path.join(ROOT, "benchmark", "ui_default_vs_api_hsa20.json")
SEED, N, WARMUP, EXTRA = 2026, 20, "hsa-miR-16-5p", "hsa-miR-210-5p"


def ui_body() -> dict:
    out = subprocess.run(["node", os.path.join(ROOT, "frontend", "scripts", "ui_default_body.mjs")],
                         capture_output=True, text=True, check=True, cwd=ROOT)
    return json.loads(out.stdout)


def main() -> int:
    os.environ["BLAST_CACHE_DISABLED"] = "1"
    body = ui_body()
    sys.path.insert(0, BACKEND)
    os.chdir(BACKEND)
    import warnings
    warnings.filterwarnings("ignore")
    from app import app
    from algorithm.constants import ALGORITHM_VERSION
    from algorithm.specificity_check.overhang_collision import _load_index
    app.config["TESTING"] = True
    client = app.test_client()
    hsa = _load_index()["mature"]["hsa"]
    frozen = {}
    with gzip.open(FREEZE, "rt", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            frozen[rec["mirna"]] = [s["sequence"] for s in rec["top3"]]
    order = random.Random(SEED).sample(sorted(n for n in hsa if n != WARMUP), len(hsa) - 1)
    # Same 20 as the timing protocol: the first with a design under the API defaults.
    names = [n for n in order if frozen.get(n)][:N]
    if EXTRA not in names:
        names.append(EXTRA)

    rows = []
    for name in names:
        req = {**body, "sequence": {**body["sequence"], "mirnaName": name,
                                    "matureSequence": hsa[name].upper().replace("T", "U")}}
        r = client.post("/api/design", json=req)
        d = r.get_json(silent=True) or {}
        top = [s["sequence"] for s in d.get("top3") or []]
        pcr = (d.get("top3") or [{}])[0].get("ranking", {}).get("pcr", {})
        rows.append({
            "mirna": name, "status": r.status_code,
            "ui_1": top[0] if top else None, "api_freeze_1": frozen[name][0],
            "same_1": bool(top) and top[0] == frozen[name][0],
            "same_top3": top == frozen[name],
            "tm_forward": pcr.get("tm_pair", {}).get("tm_forward"),
            "tm_reverse": pcr.get("tm_pair", {}).get("tm_reverse"),
            "dtm_fr": pcr.get("tm_pair", {}).get("diff"),
            "effective_p3": (d.get("metadata") or {}).get("design_settings", {}).get("effective_p3"),
        })
        print(f"  {name:<20} HTTP {r.status_code}  #1 {'same' if rows[-1]['same_1'] else 'DIFF'}  "
              f"top3 {'same' if rows[-1]['same_top3'] else 'DIFF'}", flush=True)

    first20 = rows[:N]
    summary = {
        "n": len(first20),
        "identical_1": sum(x["same_1"] for x in first20),
        "identical_top3": sum(x["same_top3"] for x in first20),
        "extra_" + EXTRA: next(({"status": x["status"], "same_1": x["same_1"], "same_top3": x["same_top3"]}
                                for x in rows if x["mirna"] == EXTRA), None),
        "dtm_fr_ge_3_of_1": sum((x["dtm_fr"] or 0) >= 3 for x in first20),
    }
    doc = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    if "designs" in doc:          # the Step 0 record becomes "before"
        doc["before"] = {"ui_body": doc.pop("ui_body", None), "summary": doc.pop("summary", None),
                         "designs": doc.pop("designs")}
    doc["after"] = {
        "algorithm_version": ALGORITHM_VERSION,
        "ui_body": {k: v for k, v in body.items() if k != "sequence"},
        "note": ("UI defaults since 2026-11-22: kPlusConc 0, bufferPH not sent unless changed — "
                 "effective monovalent 50 mM, the empty-request (API) conditions."),
        "names": names, "summary": summary, "designs": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(json.dumps(summary, indent=1))
    ok = (summary["identical_1"] == N and summary["identical_top3"] == N
          and (summary["extra_" + EXTRA] or {}).get("status") == 200)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
