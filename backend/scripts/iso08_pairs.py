"""
ISO-08 read-only check (AUDIT_REPORT.md ISO-08): miRBase 22.1 entries of one species
where one entry equals another plus >= 3 nt at its 3' end (same 5' start, identical
common part).

rt_axis only tries 3'-end registers shifted by up to ASSAY_MAX_END_SHIFT (2) nt, so for
these pairs it never reaches the register where the overhang pairs fully and returns
the >= 2-mismatch value of an unshifted register instead. This script counts the
pairs and reports, for every ordered pair (assay target -> other entry):
  - rt_axis ΔCq, chosen register, mismatches, basis;
  - the row of the cross-reactivity matrix (level, ΔCq);
  - the assay_screen value of that entry (S2 input) and whether the entry is the one
    that sets the design's min ΔCq (the S2 'worst'), or ties with it.
No algorithm code is changed; nothing feeds the tool.

Inputs:
  backend/data/mirbase_overhang_index.json        (miRBase 22.1, committed)
  outputs/crossreactivity_long.csv                (hsa matrix, committed; identical to
                                                   the 4.0.0 freeze rebuild, THESIS_FREEZE §2)
  outputs/freeze_matrix/cache/designs_hsa.jsonl   (design records of the freeze rebuild:
                                                   forward specific length, overhang, grade;
                                                   not committed — rebuild with
                                                   crossreactivity.design_all, or pass --designs)
assay_screen is recomputed with the backend default parameters, the same request the
matrix uses (crossreactivity/config.json design_request).

Usage (from backend/):
  python scripts/iso08_pairs.py [--designs PATH] [--matrix PATH] [--species hsa]
Writes ../benchmark/iso08_pairs.json.
"""
import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

OUT_JSON = os.path.join(ROOT, "benchmark", "iso08_pairs.json")
DEFAULT_DESIGNS = os.path.join(ROOT, "outputs", "freeze_matrix", "cache", "designs_hsa.jsonl")
DEFAULT_MATRIX = os.path.join(ROOT, "outputs", "crossreactivity_long.csv")
MIN_END_DIFF = 3          # ASSAY_MAX_END_SHIFT + 1: the first shift rt_axis does not try


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_pairs(seqs: dict) -> list:
    """(short, long, d) for every pair where long == short + d nt at the 3' end, d >= 3."""
    names = sorted(seqs)
    out = []
    for a in names:
        for b in names:
            if a != b and len(seqs[b]) - len(seqs[a]) >= MIN_END_DIFF and seqs[b].startswith(seqs[a]):
                out.append((a, b, len(seqs[b]) - len(seqs[a])))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--designs", default=DEFAULT_DESIGNS)
    ap.add_argument("--matrix", default=DEFAULT_MATRIX)
    ap.add_argument("--species", default="hsa")
    ap.add_argument("--out", default=OUT_JSON)
    args = ap.parse_args()

    from algorithm.constants import ALGORITHM_VERSION, ASSAY_MAX_END_SHIFT, TIERED_RT_CAPTURE_BELOW
    from algorithm.specificity_check import overhang_collision as oc
    from algorithm.specificity_check.assay_model import fwd_axis, rt_axis, variant_category

    assert ASSAY_MAX_END_SHIFT + 1 == MIN_END_DIFF, "rt_axis register range changed"
    seqs = {n: oc._dna(s) for n, s in oc._load_index()["mature"][args.species].items()}
    with open(args.designs, encoding="utf-8") as fh:
        designs = {r["mirna"]: r for r in map(json.loads, fh)}
    with open(args.matrix, encoding="utf-8", newline="") as fh:
        matrix = {(r["assay_mirna"], r["target_mirna"]): r for r in csv.DictReader(fh)}

    pairs = find_pairs(seqs)
    p3 = oc._get_p3_params({})
    screens, rows = {}, []
    for short, long_, d in pairs:
        for target, other, diff in ((short, long_, d), (long_, short, -d)):
            des = designs.get(target) or {}
            t, o = seqs[target], seqs[other]
            ov = des.get("overhang_len") or 6
            rt = rt_axis(t, o, ov)
            m = matrix.get((target, other))
            row = {
                "target": target, "other": other,
                "end_diff_nt": diff,              # > 0: the other entry is longer at 3'
                "target_seq": t, "other_seq": o,
                "category": variant_category(t, o),
                "design_status": des.get("status"),
                "overhang_len": ov,
                "rt_delta_cq": rt["delta_cq"], "rt_shift_3p": rt["shift_3p"],
                "rt_mismatches": len(rt["mismatch_positions"]), "rt_basis": rt["basis"],
                "matrix_level": m["level"] if m else ("NONE" if des.get("status") == "ok" else None),
                "matrix_delta_cq": float(m["delta_cq"]) if m else None,
            }
            if des.get("status") == "ok":
                L = des["fwd_specific_len"]
                if target not in screens:
                    screens[target] = oc.assay_screen(t, target, {}, ov, {L},
                                                      species=args.species,
                                                      rt_capture_below=TIERED_RT_CAPTURE_BELOW)[L]
                scr = screens[target]
                exact = None
                if rt["delta_cq"] < oc._SCREEN_FLOOR_CQ:
                    gap = oc._tm_gap_fn(t, L, p3)
                    v = round(rt["delta_cq"] + fwd_axis(t[:L], o, lambda r, oo=o: gap(oo, r))["delta_cq"], 2)
                    exact = v if v < oc._SCREEN_FLOOR_CQ else None
                is_worst = scr["worst"] == other
                row.update({
                    "fwd_specific_len": L,
                    "screen_delta_cq": exact,
                    "screen_min_delta_cq": scr["min_delta_cq"],
                    "screen_worst": scr["worst"],
                    "s2_worst": ("yes" if is_worst else
                                 "tie" if exact is not None and exact == scr["min_delta_cq"] else "no"),
                    "in_tm_margin": rt["delta_cq"] < TIERED_RT_CAPTURE_BELOW,
                    "grade": des.get("grade"),
                })
            rows.append(row)

    summary = {
        "n_entries": len(seqs),
        "n_pairs": len(pairs),
        "n_distinct_sequence_pairs": len({(seqs[a], seqs[b]) for a, b, _ in pairs}),
        "pairs_by_end_diff_nt": dict(sorted(Counter(d for _, _, d in pairs).items())),
        "n_ordered_pairs": len(rows),
        "n_ordered_with_design": sum(r["design_status"] == "ok" for r in rows),
        "rt_delta_cq": dict(sorted(Counter(str(r["rt_delta_cq"]) for r in rows).items())),
        "matrix_level": dict(Counter(str(r["matrix_level"]) for r in rows)),
        "s2_worst": dict(Counter(r.get("s2_worst") for r in rows)),
        "in_tm_margin": sum(bool(r.get("in_tm_margin")) for r in rows),
    }
    out = {
        "generated": date.today().isoformat(),
        "algorithm_version": ALGORITHM_VERSION,
        "species": args.species,
        "rule": f"one entry == other entry + >= {MIN_END_DIFF} nt at the 3' end (same prefix); "
                f"rt_axis tries 3'-end shifts up to ±{ASSAY_MAX_END_SHIFT} nt only",
        "inputs": {
            os.path.relpath(p, ROOT).replace("\\", "/"): _sha256(p)
            for p in (os.path.join(BACKEND, "data", "mirbase_overhang_index.json"),
                      args.matrix, args.designs)
        },
        "assay_screen_params": "backend defaults ({}), as crossreactivity/config.json design_request",
        "summary": summary,
        "rows": rows,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"wrote {os.path.relpath(args.out, ROOT)}")


if __name__ == "__main__":
    main()
