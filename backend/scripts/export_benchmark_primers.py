#!/usr/bin/env python3
"""
export_benchmark_primers.py — one combined data file for every miRNA the project
has benchmarked, merging:
  - benchmark/panel.json          (50-miRNA in-silico panel, tool only)
  - validation/reference_mirnas.json (16-miRNA deterministic ground-truth panel;
    9 of them carry a REAL published primer — journal paper or lab thesis)

For every unique miRNA it calls this tool's own /api/design (same engine the
app uses) and records the tool's primer set next to the published one where
one exists. Never fabricates a published sequence — those fields stay blank
unless reference_mirnas.json already cites one.

Usage (backend must be running on :5000):
  python backend/scripts/export_benchmark_primers.py
Writes: benchmark/primer_benchmark_export.csv + .json
"""
import csv
import json
import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "validation"))
from validate_primers import compare_published  # noqa: E402  single source of truth

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
BASE = "http://localhost:5000"


def load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)


def fetch_sequence(mirna_id):
    r = requests.get(f"{BASE}/api/mirbase/{mirna_id}", timeout=20)
    r.raise_for_status()
    return r.json()["sequence"].upper()


def design(mature_seq, mirna_id):
    payload = {
        "sequence": {"matureSequence": mature_seq, "mirnaId": mirna_id},
        "thermodynamic": {}, "primerConstraints": {}, "qpcr": {},
        "detectionMethod": {}, "experimentalContext": {},
    }
    r = requests.post(f"{BASE}/api/design", json=payload, timeout=120)
    r.raise_for_status()
    return require_blast(r.json())


def require_blast(data: dict) -> dict:
    """Thesis data must not silently lose S1 (SPEC_scoring_tiered_4.0.0 QD 24e): a
    tiered design without BLAST stops the run."""
    rs = (data or {}).get("ranking_summary") or {}
    if rs and not rs.get("blast_available", True):
        raise SystemExit("BLAST unavailable on the backend ("
                         f"{rs.get('blast_unavailable_reason')}) — tiered specificity "
                         "ranking would be S2 + S3 only. Fix BLAST+ / the DB and re-run.")
    if rs:
        sp = ((data or {}).get("metadata") or {}).get("species_code") or "?"
        s = BLAST_STATS.setdefault(sp, {"designs": 0, "blast_candidates": 0, "cache_hits": 0,
                                        "cache_write_errors": 0})
        s["designs"] += 1
        s["blast_candidates"] += rs.get("blast_candidates") or 0
        s["cache_hits"] += rs.get("blast_cache_hits") or 0
        s["cache_write_errors"] += bool(rs.get("blast_cache_write_error"))
    return data


BLAST_STATS: dict = {}   # species code → designs / BLASTed candidates / cache hits


def write_blast_stats(name: str) -> None:
    """Per-species BLAST cache use of this run → benchmark/logs/<name>_blast_stats.json
    (SPEC_scoring_tiered_4.0.0 Giai đoạn 3: cache hit ≥ 90 % for hsa designs)."""
    import json as _j
    import os as _o
    for s in BLAST_STATS.values():
        s["new_blast_calls"] = s["blast_candidates"] - s["cache_hits"]
        s["cache_hit_rate"] = round(s["cache_hits"] / s["blast_candidates"], 4) if s["blast_candidates"] else None
    root = _o.path.normpath(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)), *([".."] * 2)))
    path = _o.path.join(root, "benchmark", "logs", f"{name}_blast_stats.json")
    _o.makedirs(_o.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        _j.dump(BLAST_STATS, f, indent=1, sort_keys=True)
    print(f"BLAST stats ({path}): " + _j.dumps(BLAST_STATS, sort_keys=True))



def main():
    panel = load("benchmark/panel.json")["mirnas"]
    ref = load("validation/reference_mirnas.json")["mirnas"]

    # Union by label (one miRNA may be benchmarked against several papers);
    # reference entries (which may carry published_* citations) win.
    merged = {e["id"]: {"id": e["id"], "sequence": e.get("sequence")} for e in panel}
    for e in ref:
        key = e.get("label", e["id"])
        merged.setdefault(key, {"id": e["id"]})
        merged[key].update(e)

    rows, n_ok, n_published = [], 0, 0
    for label, entry in sorted(merged.items()):
        mid = entry["id"]
        seq = entry.get("sequence") or entry.get("matureSequence")
        try:
            if not seq:
                seq = fetch_sequence(mid)
            data = design(seq, mid)
        except Exception as exc:  # noqa: BLE001
            rows.append({"id": mid, "label": label, "status": f"ERROR: {exc}"})
            continue

        used = data["metadata"]["mirna_sequence"].upper()
        used_dna = used.replace("U", "T")          # primers are DNA; match on DNA bases
        rt = data["stemloop_rt"]["sequence"]
        olen = len(rt) - 44
        top = (data.get("top3") or [{}])[0]
        fwd = (top.get("sequence") or "").upper()
        spec = (top.get("specific_region") or "").upper()

        _, cmp = compare_published(entry, rt, fwd, used_dna, olen)
        row = {
            "id": mid,
            "label": label,
            "status": "OK",
            "mirna_sequence": used,
            "length_nt": len(used),
            "gc_pct_mirna": entry.get("gc_pct"),
            "role_note": entry.get("role", ""),
            "benchmark_group": entry.get("benchmark_group", ""),
            # tool output
            "tool_rt_primer": rt,
            "tool_rt_overhang": rt[-olen:],
            "tool_universal_reverse": data["universal_reverse"]["sequence"],
            "tool_forward_primer": fwd,
            "tool_forward_specific_region": spec,
            "tool_forward_tm_c": top.get("tm_full"),
            "tool_forward_gc_pct": top.get("gc_percent"),
            "tool_amplicon_bp": top.get("amplicon_size"),
            "tool_score": top.get("total_score"),
            "tool_grade": top.get("grade"),
            # published (journal / thesis) — blank unless cited in reference_mirnas.json
            "published_rt_primer": entry.get("published_rt") or entry.get("published_rt_printed", ""),
            "published_rt_overhang": entry.get("published_rt_overhang", ""),
            "published_forward_primer": entry.get("published_forward", ""),
            "published_source": entry.get("published_source", ""),
            "rt_exact_match": cmp.get("published_rt_match", ""),
            "rt_not_scored_reason": entry.get("published_rt_unscored", ""),
            "rt_overhang_match": cmp.get("published_rt_overhang_match", ""),
            "published_forward_specific_region": cmp.get("forward_pub_specific", ""),
            "published_forward_start_nt": cmp.get("forward_pub_start_nt", ""),
            "forward_specific_overlap_nt": cmp.get("forward_specific_overlap_nt", ""),
            "forward_specific_agrees": cmp.get("published_forward_specific_shared", ""),
        }
        if any(entry.get(k) for k in ("published_rt", "published_rt_overhang", "published_forward")):
            n_published += 1

        rows.append(row)
        n_ok += 1

    out_json = os.path.join(ROOT, "benchmark", "primer_benchmark_export.json")
    out_csv = os.path.join(ROOT, "benchmark", "primer_benchmark_export.csv")

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "generated_by": "backend/scripts/export_benchmark_primers.py",
            "note": "Tool primer set vs published (journal/thesis) primer set, where cited. "
                    "Published sequences are never invented — see each row's published_source.",
            "n_mirnas": len(rows),
            "n_design_ok": n_ok,
            "n_with_published_primer": n_published,
            "rows": rows,
        }, f, indent=2, ensure_ascii=False)

    cols = list(rows[0].keys()) if rows else []
    # make sure every row has every column (ERROR rows are sparse)
    all_cols = []
    for r in rows:
        for k in r:
            if k not in all_cols:
                all_cols.append(k)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=all_cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"{len(rows)} miRNAs total, {n_ok} designed OK, {n_published} with a published primer to compare.")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_csv}")
    write_blast_stats("benchmark_export")


if __name__ == "__main__":
    sys.exit(main())
