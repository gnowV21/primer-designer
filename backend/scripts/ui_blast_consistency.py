"""ui_blast_consistency.py — design-time S1 vs the "Show all hits" BLAST check.

docs/SPEC_ui_tiered_4.0.0.md §2.5: OffTargetPanel shows the design-time BLAST result
(ranking.specificity.blast) and its "Show all hits" button calls /api/blast-check with
the inputs the frontend sends (forward + universal reverse, mirna_id, mirna_sequence,
the design's effective_p3, species, rt_primer). This script makes both calls in-process
with the frontend's default parameters and counts sets whose overall_risk differs.

Usage (repo root):
    python backend/scripts/ui_blast_consistency.py [--n 40] [--seed 2026]
Output: benchmark/ui_blast_consistency.json
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "backend"))
os.chdir(os.path.join(_ROOT, "backend"))

from crossreactivity import design_all as da  # noqa: E402
from crossreactivity.model import load_config, load_mature  # noqa: E402

def frontend_body() -> dict:
    """The /api/design body the designer sends with its defaults, read from the frontend
    itself (constants/defaults.js + utils/designRequest.buildDesignBody) via Node."""
    import subprocess
    js = ("const d = await import('./frontend/src/constants/defaults.js');"
          "const r = await import('./frontend/src/utils/designRequest.js');"
          "console.log(JSON.stringify(r.buildDesignBody(d.DEFAULTS)));")
    out = subprocess.check_output(["node", "--input-type=module", "-e", js], cwd=_ROOT)
    return json.loads(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--names", nargs="*", default=["hsa-miR-21-5p", "hsa-let-7a-5p", "hsa-miR-590-3p"])
    args = ap.parse_args(argv)

    from app import app, limiter
    app.config["TESTING"] = True
    limiter.enabled = False                 # the 10/min limit is for browsers, not this check
    client = app.test_client()
    base = frontend_body()

    cfg = load_config(da.CONFIG_PATH)
    mature = load_mature(cfg["mirbase_index_path"], "hsa")
    names = list(args.names) + random.Random(args.seed).sample(sorted(set(mature) - set(args.names)), args.n)

    rows, n_sets, n_diff = [], 0, 0
    for name in names:
        rna = mature[name].replace("T", "U")
        body = {**base, "sequence": {**base["sequence"], "matureSequence": rna, "mirnaName": name}}
        d = client.post("/api/design", json=body).get_json() or {}
        meta = d.get("metadata") or {}
        rt = (d.get("stemloop_rt") or {}).get("sequence")
        rev = (d.get("universal_reverse") or {}).get("sequence")
        for s in d.get("top3") or []:
            design_risk = s["ranking"]["specificity"]["blast"]["overall_risk"]
            chk = client.post("/api/blast-check", json={
                "forward_primer": s["sequence"], "reverse_primer": rev, "mirna_id": meta.get("mirna_id"),
                "mirna_sequence": meta.get("mirna_sequence"),
                "conditions": (meta.get("design_settings") or {}).get("effective_p3"),
                "species": meta.get("species_code"), "rt_primer": rt,
            }).get_json() or {}
            check_risk = (chk.get("summary") or {}).get("overall_risk")
            n_sets += 1
            same = design_risk == check_risk
            n_diff += not same
            rows.append({"mirna": name, "rank": s["rank"], "sequence": s["sequence"],
                         "design_risk": design_risk, "check_risk": check_risk, "same": same,
                         "rt_step_applied": (chk.get("classification") or {}).get("rt_step_applied")})
        print(f"{name}: {[(r['design_risk'], r['check_risk']) for r in rows if r['mirna'] == name]}", flush=True)

    out = {"designs": len(names), "sets": n_sets, "overall_risk_different": n_diff,
           "seed": args.seed, "named": args.names, "rows": rows}
    path = os.path.join(_ROOT, "benchmark", "ui_blast_consistency.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"{n_sets} sets in {len(names)} designs, overall_risk different: {n_diff} -> {path}")
    return 1 if n_diff else 0


if __name__ == "__main__":
    sys.exit(main())
