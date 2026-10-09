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


def specific_region(primer: str, mirna_dna: str) -> str:
    """Longest 3' suffix of `primer` that is a 5' prefix of `mirna_dna`.

    Both stem-loop-qPCR forward primers = [5' Tm-raising tail] + [miRNA 5' prefix].
    This recovers the miRNA-specific part, letting us compare the biologically
    meaningful core across tools/protocols that use different tails.
    """
    primer = primer.upper()
    for length in range(len(primer), 0, -1):
        if mirna_dna.startswith(primer[-length:]):
            return primer[-length:]
    return ""


def anchored_region(primer: str, mirna_dna: str):
    """(core, start) — where a published forward primer sits on the miRNA.

    Normally the 5'-prefix core above (start 0). Some protocols print a forward with
    no 5' tail that starts at miRNA nt 2-3 (e.g. Bagheri 2021); then fall back to the
    longest 3' suffix of the primer found anywhere in the miRNA.
    """
    core = specific_region(primer, mirna_dna)
    if len(core) >= 10:
        return core, 0
    primer = primer.upper()
    for length in range(len(primer), len(core), -1):
        pos = mirna_dna.find(primer[-length:])
        if pos >= 0:
            return primer[-length:], pos
    return core, 0


def _norm(s):
    return (s or "").upper().replace("U", "T").replace(" ", "")


def compare_published(entry, rt, fwd, dna, olen):
    """Tool primers vs a cited published primer table. Returns (checks, row fields).

    Entry fields (all optional, never invented — only from a cited paper table):
      published_rt          full RT primer. Compared only when its stem-loop body is the
                            tool's (Chen 2005). Same length -> byte-exact; different
                            overhang length (5/7/8 nt) -> body must be identical.
      published_rt_overhang 3' overhang. Every overhang starts with the base pairing the
                            miRNA 3'-terminal nt, so the shorter one must be the 5'
                            prefix of the longer one.
      published_forward     forward primer. Scored: its miRNA core overlaps the tool's
                            core by >= 10 nt at the same miRNA coordinates. Cores < 10 nt
                            are recorded but not scored. Exact match recorded, not scored.
      published_rt_unscored reason the printed RT is shown but NOT scored (paper erratum,
                            modified body). Its printed sequence goes in published_rt_printed.
    """
    checks, row = [], {}
    rt, fwd = _norm(rt), _norm(fwd)
    tool_over = rt[-olen:]
    pub_rt = _norm(entry.get("published_rt"))
    pub_over = _norm(entry.get("published_rt_overhang"))
    pub_fwd = _norm(entry.get("published_forward"))

    if pub_rt:
        if len(pub_rt) == len(rt):
            c = rt == pub_rt
            checks.append(("published_rt_exact_match", c))
            row["published_rt_match"] = ok(c)
        else:
            plen = len(pub_over) or olen
            c = pub_rt[:-plen] == rt[:-olen]
            checks.append(("published_rt_body_match", c))
            row["published_rt_match"] = f"BODY {ok(c)} ({plen}-nt overhang)"

    if pub_over:
        if len(pub_over) >= olen:
            c = pub_over.startswith(tool_over)
        else:
            c = tool_over.startswith(pub_over)
        checks.append(("published_rt_overhang_match", c))
        row["published_rt_overhang_match"] = ok(c)

    if pub_fwd:
        tool_spec = specific_region(fwd, dna)
        pub_spec, pub_start = anchored_region(pub_fwd, dna)
        ov = max(0, min(len(tool_spec), pub_start + len(pub_spec)) - pub_start)
        row.update({
            "published_forward_exact": ok(fwd == pub_fwd),
            "published_forward_tool": fwd,
            "published_forward_ref": entry.get("published_forward"),
            "forward_tool_specific": tool_spec,
            "forward_pub_specific": pub_spec,
            "forward_pub_start_nt": pub_start + 1,
            "forward_specific_overlap_nt": ov,
        })
        if len(pub_spec) >= 10:
            c = ov >= 10
            checks.append(("published_forward_specific_agrees", c))
            row["published_forward_specific_shared"] = ok(c)
        else:
            row["published_forward_specific_shared"] = f"N/A (published core {len(pub_spec)} nt < 10)"

    for k in ("published_source", "published_rt_unscored", "published_rt_printed", "benchmark_group"):
        if entry.get(k):
            row[k] = entry[k]
    return checks, row


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
        # Documented known limitation: the tool is EXPECTED to refuse this miRNA.
        if entry.get("expect_design_failure"):
            return ({"target": label, "status": f"HTTP {resp.status_code} (expected)",
                     "failed_checks": ""}, [("expected_design_failure", True)])
        # A real miRNA the tool cannot design for is a FAIL, not a silent skip.
        return ({"target": label, "status": f"HTTP {resp.status_code}: {body.get('error', '')[:60]}"},
                [("design_succeeded", False)])

    data = resp.json()
    used_seq = get(data, "metadata", "mirna_sequence", default=mature).upper()
    dna = to_dna(used_seq)

    checks = [] if entry.get("expect_edge_code") else [("design_succeeded", True)]
    row = {"target": label, "source": src, "length": len(used_seq), "status": "200"}

    # A documented limitation that now designs fine: flag it so the dataset gets updated.
    if entry.get("expect_design_failure"):
        return row, [("expected_design_failure", False)]

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

    # --- Optional match vs published primer sequences (never fabricated) ---
    pub_checks, pub_row = compare_published(entry, rt, fwd, dna, olen)
    checks += pub_checks
    row.update(pub_row)

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
    ap.add_argument("--json-out", default="validation/results.json",
                    help="machine-readable summary (mergeable into benchmark_results.json)")
    args = ap.parse_args()

    with open(args.dataset, encoding="utf-8") as f:
        ds = json.load(f)
    consts = ds["expected_constants"]
    windows = ds["plausibility_windows"]
    entries = list(ds.get("mirnas", [])) + list(ds.get("edge_cases", []))

    all_rows, json_records, total_pass, total_checks = [], [], 0, 0
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
        json_records.append({
            "target": row["target"],
            "checks_pass": p,
            "checks_total": n,
            "passed": bool(n and p == n),
            "rt_overhang_expected": row.get("rt_overhang_expected"),
            "rt_overhang_actual": row.get("rt_overhang_actual"),
            "forward_tm_c": row.get("tm_full"),
            "forward_gc_pct": row.get("gc_pct"),
            "amplicon_bp": row.get("amplicon_bp"),
            "siblings_flagged": row.get("siblings_flagged"),
            "edge_expected": row.get("edge_expected"),
            "edge_found": row.get("edge_found"),
            "published_rt_match": row.get("published_rt_match"),
            "published_rt_overhang_match": row.get("published_rt_overhang_match"),
            "published_forward_exact": row.get("published_forward_exact"),
            "published_forward_specific_shared": row.get("published_forward_specific_shared"),
            "published_forward_tool": row.get("published_forward_tool"),
            "published_forward_ref": row.get("published_forward_ref"),
            "forward_tool_specific": row.get("forward_tool_specific"),
            "forward_pub_specific": row.get("forward_pub_specific"),
            "forward_specific_overlap_nt": row.get("forward_specific_overlap_nt"),
            "forward_pub_start_nt": row.get("forward_pub_start_nt"),
            "published_rt_printed": row.get("published_rt_printed"),
            "published_rt_unscored": row.get("published_rt_unscored"),
            "benchmark_group": row.get("benchmark_group"),
            "published_source": row.get("published_source"),
            "failed_checks": failed,
        })
        flag = "OK " if (n and p == n) else ("--- " if not n else "!!! ")
        print(f"{flag}{row['target']:<20} {row['checks_pass']:<8} "
              f"{('FAILED: ' + row['failed_checks']) if failed else row.get('status','')}")

    # Write CSV
    cols = ["target", "source", "length", "status", "checks_pass", "failed_checks",
            "rt_overhang_expected", "rt_overhang_actual", "tm_full", "gc_pct",
            "amplicon_bp", "grade", "score", "siblings_flagged",
            "published_rt_match", "published_rt_overhang_match",
            "published_forward_exact", "published_forward_specific_shared",
            "forward_specific_overlap_nt", "benchmark_group", "published_rt_unscored",
            "published_source", "edge_expected", "edge_found", "edge_check"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in all_rows:
            w.writerow(r)

    print(f"\n--- Summary: {total_pass}/{total_checks} checks passed "
          f"({100*total_pass/total_checks:.1f}%) ---")
    print(f"CSV written: {args.out}")

    # Machine-readable summary (mergeable into benchmark_results.json)
    from datetime import datetime, timezone
    summary = {
        "method": (
            "Deterministic ground truth from the Chen 2005 stem-loop method "
            "(RT primer = fixed universal body + revcomp of 3'-terminal 6 nt; "
            "universal reverse = fixed constant; forward specific region = 5' prefix "
            "of the miRNA), recomputed independently from the sequence the tool used. "
            "Plus thermodynamic-plausibility windows and let-7 specificity concordance "
            "with Wang 2017."
        ),
        "sources": ds.get("_meta", {}).get("sources", []),
        "run_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "checks_passed": total_pass,
        "checks_total": total_checks,
        "success_rate": round(total_pass / total_checks, 4) if total_checks else None,
        "targets": json_records,
    }
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"JSON written: {args.json_out}\n")

    # Non-zero exit if any deterministic check failed (useful for CI)
    sys.exit(0 if total_pass == total_checks else 1)


if __name__ == "__main__":
    main()
