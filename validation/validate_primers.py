#!/usr/bin/env python3
"""
validate_primers.py — Scientific validation loop for the stem-loop RT-qPCR primer designer.

Idea (deterministic ground truth):
  For Chen-2005 stem-loop RT-qPCR, given the mature miRNA sequence, two primers are
  fully determined and one is partially determined:
    - RT stem-loop primer  = FIXED universal body + revcomp(3'-terminal 6 nt of miRNA)
    - Universal reverse     = FIXED constant
    - Forward specific region = 5' prefix of the miRNA (same sense)
  We recompute these expected values INDEPENDENTLY from the exact sequence the tool used
  (metadata.mirna_sequence) and compare. This does not depend on any hand-entered sequence.

  We additionally check thermodynamic plausibility (Tm/GC/amplicon windows) and, for the
  let-7 panel, specificity concordance with Wang et al. 2017 (siblings differing by ~1 nt
  should be flagged as cross-reactive).

Usage:
  # 1) start backend (Terminal 1):  cd backend && python app.py   -> http://localhost:5000
  # 2) run:
  python validation/validate_primers.py --base-url http://localhost:5000 \
         --dataset validation/reference_mirnas.json --out validation/results.csv

Requires: requests  (pip install requests)

Sources: [Chen05] Chen 2005 Nucleic Acids Res 33:e179; [Wang17] Mol Med Rep 2017 DOI
10.3892/mmr.2017.8297; [MIQE09] Clin Chem 2009 DOI 10.1373/clinchem.2008.112797.
"""
import argparse
import csv
import json
import sys

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")

COMP = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}


def revcomp(dna: str) -> str:
    return "".join(COMP.get(b, "N") for b in reversed(dna.upper()))


def to_dna(rna: str) -> str:
    return rna.upper().replace("U", "T")


def ok(cond):
    return "PASS" if cond else "FAIL"


def get(d, *keys, default=None):
    """Nested get: get(d, 'a', 'b') -> d['a']['b'] or default."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def default_payload(mature_seq: str, mirna_id: str = "") -> dict:
    """Minimal /api/design body; empty param groups let backend apply its own defaults."""
    return {
        "sequence": {"matureSequence": mature_seq, "mirnaId": mirna_id},
        "thermodynamic": {},
        "primerConstraints": {},
        "qpcr": {},
        "detectionMethod": {},
        "experimentalContext": {},
    }


def fetch_sequence(base, mirna_id):
    """Mirror the real user flow: resolve a miRNA id to its mature sequence via miRBase route."""
    try:
        r = requests.get(f"{base}/api/mirbase/{mirna_id}", timeout=20)
        if r.status_code == 200:
            return r.json().get("sequence", "").upper(), None
        return None, f"mirbase {r.status_code}"
    except Exception as e:  # noqa: BLE001
        return None, f"mirbase error: {e}"


def run_design(base, mature_seq, mirna_id=""):
    r = requests.post(f"{base}/api/design", json=default_payload(mature_seq, mirna_id), timeout=60)
    return r


def validate_one(base, entry, consts, windows):
    """Return (row dict, list of check tuples)."""
    mid = entry.get("id")
    given_seq = entry.get("matureSequence")
    label = entry.get("label", mid or "?")

    # Resolve sequence
    if given_seq:
        mature = given_seq.upper()
        src = "inline"
    else:
        mature, err = fetch_sequence(base, mid)
        src = "mirbase"
        if not mature:
            return {"target": label, "status": f"SKIP ({err})"}, []

    resp = run_design(base, mature, mirna_id=mid or "")
    if resp.status_code != 200:
        # Edge cases may legitimately still return 200 with warnings; a 4xx is informative too.
        body = {}
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            pass
        # For edge-case entries we still inspect edge_cases if present
        if entry.get("expect_edge_code"):
            codes = [e.get("code") for e in body.get("edge_cases", [])]
            hit = entry["expect_edge_code"] in codes
            return ({"target": label, "status": f"HTTP {resp.status_code}",
                     "edge_expected": entry["expect_edge_code"],
                     "edge_found": ",".join(codes) or "-",
                     "edge_check": ok(hit)},
                    [("edge_case", hit)])
        return {"target": label, "status": f"HTTP {resp.status_code}: {body.get('error', '')[:60]}"}, []

    data = resp.json()
    used_seq = get(data, "metadata", "mirna_sequence", default=mature).upper()
    dna = to_dna(used_seq)

    checks = []
    row = {"target": label, "source": src, "length": len(used_seq), "status": "200"}

    # --- Edge-case entries: just verify the expected code fired ---
    if entry.get("expect_edge_code"):
        codes = [e.get("code") for e in data.get("edge_cases", [])]
        hit = entry["expect_edge_code"] in codes
        row.update({"edge_expected": entry["expect_edge_code"],
                    "edge_found": ",".join(codes) or "-", "edge_check": ok(hit)})
        checks.append(("edge_case", hit))
        return row, checks

    # --- Deterministic check 1: RT stem-loop primer ---
    rt = get(data, "stemloop_rt", "sequence", default="") or ""
    body = consts["stemloop_body"]
    olen = consts["overhang_len"]
    exp_overhang = revcomp(dna[-olen:])
    c_body = rt.startswith(body)
    c_over = rt.endswith(exp_overhang)
    c_len = len(rt) == len(body) + olen
    checks += [("rt_body_fixed", c_body), ("rt_overhang_deterministic", c_over), ("rt_length", c_len)]
    row["rt_overhang_expected"] = exp_overhang
    row["rt_overhang_actual"] = rt[-olen:] if len(rt) >= olen else rt

    # --- Deterministic check 2: universal reverse fixed ---
    rev = get(data, "universal_reverse", "sequence", default="") or ""
    c_rev = rev == consts["universal_reverse"]
    checks.append(("reverse_fixed", c_rev))

    # --- Deterministic check 3: forward specific region = 5' prefix of miRNA ---
    top = (data.get("top3") or [{}])[0]
    spec = (top.get("specific_region") or "").upper()
    fwd = (top.get("sequence") or "").upper()
    c_spec_prefix = bool(spec) and dna.startswith(spec)
    c_fwd_tail = bool(spec) and fwd.endswith(spec)  # forward = 5' tail + specific region
    checks += [("forward_specific_is_5prime_prefix", c_spec_prefix),
               ("forward_ends_with_specific", c_fwd_tail)]

    # --- Plausibility: Tm / GC / amplicon ---
    tm = top.get("tm_full")
    gc = top.get("gc_percent")
    amp = top.get("amplicon_size")
    tm_lo, tm_hi = windows["forward_tm_c"]
    gc_lo, gc_hi = windows["forward_gc_pct"]
    amp_lo, amp_hi = windows["amplicon_bp"]
    c_tm = tm is not None and tm_lo <= tm <= tm_hi
    c_gc = gc is not None and gc_lo <= gc <= gc_hi
    c_amp = amp is not None and amp_lo <= amp <= amp_hi
    checks += [("forward_tm_in_window", c_tm), ("forward_gc_in_window", c_gc),
               ("amplicon_in_window", c_amp)]
    row.update({"tm_full": tm, "gc_pct": gc, "amplicon_bp": amp,
                "grade": top.get("grade"), "score": top.get("total_score")})

    # --- Quality: top set has no critical structure flag ---
    crit = get(top, "structure_checks", "has_critical_flag", default=False)
    checks.append(("top_no_critical_flag", not crit))

    # --- Specificity concordance (let-7 family) ---
    siblings = entry.get("expected_cross_reactive_siblings")
    if siblings:
        xr = get(data, "specificity_warnings", "cross_reactivity", "cross_reactivity", default=[]) or []
        flagged = {r.get("sibling", r.get("name", "")).lower(): r.get("risk") for r in xr}
        hit = any(flagged.get(s.lower()) in ("HIGH", "IDENTICAL") for s in siblings)
        checks.append(("family_siblings_flagged", hit))
        row["siblings_flagged"] = ",".join(f"{k}:{v}" for k, v in flagged.items()) or "-"

    return row, checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:5000")
    ap.add_argument("--dataset", default="validation/reference_mirnas.json")
    ap.add_argument("--out", default="validation/results.csv")
    args = ap.parse_args()

    with open(args.dataset, encoding="utf-8") as f:
        ds = json.load(f)
    consts = ds["expected_constants"]
    windows = ds["plausibility_windows"]
    entries = list(ds.get("mirnas", [])) + list(ds.get("edge_cases", []))

    all_rows, total_pass, total_checks = [], 0, 0
    print(f"\n=== Primer designer validation — {args.base_url} ===\n")
    for e in entries:
        row, checks = validate_one(args.base_url, e, consts, windows)
        p = sum(1 for _, c in checks if c)
        n = len(checks)
        total_pass += p
        total_checks += n
        row["checks_pass"] = f"{p}/{n}" if n else row.get("status", "")
        failed = [name for name, c in checks if not c]
        row["failed_checks"] = ",".join(failed) if failed else ""
        all_rows.append(row)
        flag = "OK " if (n and p == n) else ("--- " if not n else "!!! ")
        print(f"{flag}{row['target']:<20} {row['checks_pass']:<8} "
              f"{('FAILED: ' + row['failed_checks']) if failed else row.get('status','')}")

    # Write CSV
    cols = ["target", "source", "length", "status", "checks_pass", "failed_checks",
            "rt_overhang_expected", "rt_overhang_actual", "tm_full", "gc_pct",
            "amplicon_bp", "grade", "score", "siblings_flagged",
            "edge_expected", "edge_found", "edge_check"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in all_rows:
            w.writerow(r)

    print(f"\n--- Summary: {total_pass}/{total_checks} checks passed "
          f"({100*total_pass/total_checks:.1f}%) ---")
    print(f"CSV written: {args.out}\n")
    # Non-zero exit if any deterministic check failed (useful for CI)
    sys.exit(0 if total_pass == total_checks else 1)


if __name__ == "__main__":
    main()
