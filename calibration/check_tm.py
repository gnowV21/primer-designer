#!/usr/bin/env python3
"""
check_tm.py — SPEC_phase5 PART C: Tm model accuracy validation.

Compares the tool's SantaLucia 1998 NN Tm predictions against experimentally
measured values from Owczarzy 2004 (Na+ series) and Owczarzy 2008 (Mg2+ series).

KEY IMPLEMENTATION NOTES:
  1. Predictions at EACH OLIGO'S MEASURED CONDITIONS (salt_na_mm, salt_mg_mm,
     dntp_mm, primer_conc_nm from benchmark), NOT the tool's default salt.
  2. primer3.calc_tm() uses dna_conc/4 INTERNALLY (SantaLucia non-self-
     complementary formula: Tm = dH/(dS + R*ln(CT/4))). Pass Ct directly;
     do NOT pre-divide by 4 (confirmed experimentally — see tm_benchmark.json
     known_bias_2026-07-03).

Usage:
  python calibration/check_tm.py \\
    --benchmark calibration/tm_benchmark.json \\
    --report    calibration/tm_report.md

Sources:
  [SL98]       DOI 10.1073/pnas.95.4.1460
  [Owczarzy04] DOI 10.1021/bi034621r  (Na+ series, Table 2)
  [Owczarzy08] DOI 10.1021/bi702363u  (Mg2+/dNTP series, Table 1)
"""
import argparse
import json
import sys
import os

BIAS_WARN_C = 1.5   # °C — systematic bias threshold for report flag


def _load_backend():
    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from algorithm.thermodynamics import calculate_tm_nn
    return calculate_tm_nn


def predict_tm(oligo: dict, calculate_tm_nn) -> float | None:
    """
    Predict Tm at the oligo's MEASURED conditions.

    Salt parameters are read per-oligo from the benchmark:
      salt_na_mm    → mv_conc  (monovalent; 1 mM for Mg-only Tris buffer)
      salt_mg_mm    → dv_conc  (Mg2+ mM; 0 for Na-only series)
      dntp_mm       → dntp_conc (0 for both Owczarzy series)
      primer_conc_nm = Ct (total strand).  primer3.calc_tm uses dna_conc/4
                      internally, so pass Ct directly — do NOT pre-divide.
    """
    seq = oligo.get("sequence_dna", "")
    if not seq:
        return None

    na_mm  = float(oligo.get("salt_na_mm",  0) or 0)
    mg_mm  = float(oligo.get("salt_mg_mm",  0) or 0)
    dnt_mm = float(oligo.get("dntp_mm",     0) or 0)
    ct_nm  = float(oligo.get("primer_conc_nm", 2000) or 2000)

    params = {
        "saltConcentration":      na_mm,
        "magnesiumConcentration": mg_mm,
        "dntpTotal":              dnt_mm,
        "primerConcentration":    ct_nm,   # = Ct; primer3 divides by 4 internally
        "tmMethod":               "santalucia",
    }
    try:
        return calculate_tm_nn(seq, params)
    except Exception as exc:
        print(f"  ! calc_tm failed for {oligo.get('oligo_id', seq[:10])}: {exc}")
        return None


def run_check(benchmark_path: str, report_path: str):
    with open(benchmark_path, encoding="utf-8") as f:
        bench = json.load(f)

    all_oligos = bench.get("oligos", [])
    oligos = [o for o in all_oligos if o.get("verified") is True]

    print(f"\n=== Tm model accuracy check ===")
    print(f"Benchmark: {benchmark_path}")
    print(f"Verified entries: {len(oligos)} / {len(all_oligos)} total\n")

    if not oligos:
        print("No verified entries — emitting stub report.")
        _write_report(report_path, [], bench)
        return

    try:
        calculate_tm_nn = _load_backend()
    except Exception as exc:
        sys.exit(f"Could not import backend thermodynamics module: {exc}\n"
                 "Run from the repo root or ensure backend/ is importable.")

    rows = []
    for o in oligos:
        exp = o.get("tm_experimental_c")
        if not o.get("sequence_dna") or exp is None:
            continue
        pred = predict_tm(o, calculate_tm_nn)
        if pred is None:
            continue
        err = pred - exp
        is_mg = (o.get("salt_mg_mm") or 0) > 0
        rows.append({
            "id":         o["oligo_id"],
            "length":     o.get("length_nt", len(o["sequence_dna"])),
            "gc_pct":     o.get("gc_pct"),
            "tm_exp":     exp,
            "tm_pred":    round(pred, 1),
            "error":      round(err, 1),
            "source_doi": o.get("source_doi", ""),
            "series":     "mg" if is_mg else "na",
            "na_mm":      o.get("salt_na_mm", 0),
            "mg_mm":      o.get("salt_mg_mm", 0),
        })
        cond = (f"[Mg {o.get('salt_mg_mm',0):.1f}mM Na {o.get('salt_na_mm',0):.0f}mM]"
                if is_mg else f"[Na {o.get('salt_na_mm',0):.0f}mM]")
        print(f"  {o['oligo_id']:<28} {cond}  exp={exp:.1f}°C  pred={pred:.1f}°C  err={err:+.1f}°C")

    if not rows:
        print("No rows processed.")
        _write_report(report_path, rows, bench)
        return

    def _stats(rr):
        if not rr:
            return None, None
        e = [r["error"] for r in rr]
        return sum(abs(x) for x in e) / len(e), sum(e) / len(e)

    mg_rows = [r for r in rows if r["series"] == "mg"]
    na_rows = [r for r in rows if r["series"] == "na"]
    all_mae, all_bias   = _stats(rows)
    mg_mae, mg_bias     = _stats(mg_rows)
    na_mae, na_bias     = _stats(na_rows)

    print(f"\n{'-'*62}")
    print(f"  All ({len(rows)})       MAE={all_mae:.2f} C   Bias={all_bias:+.2f} C")
    if mg_rows:
        print(f"  Mg series ({len(mg_rows)})  MAE={mg_mae:.2f} C   Bias={mg_bias:+.2f} C  [Owczarzy 2008]")
    if na_rows:
        print(f"  Na series ({len(na_rows)})  MAE={na_mae:.2f} C   Bias={na_bias:+.2f} C  [Owczarzy 2004]")
    if abs(all_bias) > BIAS_WARN_C:
        direction = "UNDER" if all_bias < 0 else "OVER"
        print(f"  WARNING: tool {direction}-predicts Tm by {all_bias:+.2f} C on average")

    _write_report(report_path, rows, bench,
                  all_mae=all_mae, all_bias=all_bias,
                  mg_rows=mg_rows, na_rows=na_rows,
                  mg_mae=mg_mae, mg_bias=mg_bias,
                  na_mae=na_mae, na_bias=na_bias)


def _write_report(path, rows, bench,
                  all_mae=None, all_bias=None,
                  mg_rows=None, na_rows=None,
                  mg_mae=None, mg_bias=None,
                  na_mae=None, na_bias=None):
    mg_rows = mg_rows or []
    na_rows = na_rows or []

    lines = [
        "# Tm Model Accuracy Report — SPEC_phase5 PART C",
        "",
        f"- Verified oligos: {len(rows)}",
        "- Tool model: SantaLucia 1998 NN (primer3-py)",
        "- Predictions at **each oligo's measured conditions** (per-oligo salt/Ct from benchmark)",
        "- Ct convention: benchmark `primer_conc_nm` = Ct (total strand); passed directly to "
        "primer3.calc_tm which divides by 4 internally",
        "",
    ]

    if not rows:
        lines += [
            "**No verified experimental data yet.**",
            "",
            "Populate `calibration/tm_benchmark.json` with `verified: true` entries "
            "(transcribed from Owczarzy 2004/2008 tables) to enable this analysis.",
        ]
    else:
        lines += ["## Summary", ""]
        lines += [
            "| Series | N | MAE (°C) | Bias (°C) | Source |",
            "|---|---|---|---|---|",
            f"| **All** | {len(rows)} | {all_mae:.2f} | {all_bias:+.2f} | — |",
        ]
        if mg_rows:
            lines.append(f"| Mg²⁺ 1.5 mM (Owczarzy 2008) | {len(mg_rows)} "
                         f"| {mg_mae:.2f} | {mg_bias:+.2f} | DOI 10.1021/bi702363u |")
        if na_rows:
            lines.append(f"| Na⁺ 69 mM (Owczarzy 2004)   | {len(na_rows)} "
                         f"| {na_mae:.2f} | {na_bias:+.2f} | DOI 10.1021/bi034621r |")
        lines.append("")

        if abs(all_bias) > BIAS_WARN_C:
            direction = "under-predicts" if all_bias < 0 else "over-predicts"
            lines += [
                f"⚠ **Systematic bias = {all_bias:+.2f}°C** (threshold ±{BIAS_WARN_C}°C). "
                f"Tool {direction} Tm.",
                "",
                "Possible causes: (1) primer3 salt-correction underestimates Mg²⁺ stabilisation "
                "at low concentrations; (2) NN parameters slightly off for short oligos (≤12 nt); "
                "(3) benchmark conditions (1 mM monovalent, no dNTP) differ from tool defaults "
                "(50 mM Na + 1.5 mM Mg + 0.8 mM dNTP). The bias at **actual operating conditions** "
                "(50 mM Na + 1.5 mM Mg + 0.8 mM dNTP, primers 15–25 nt) may differ. "
                "Do NOT adjust `TM_FORWARD_TARGET` without in-lab measurements at tool conditions.",
            ]
        else:
            lines.append(f"Bias within ±{BIAS_WARN_C}°C — model well-calibrated for this dataset.")

        lines += [
            "",
            "## Per-oligo results", "",
            "| ID | nt | GC% | Na (mM) | Mg (mM) | Tm exp | Tm pred | Error |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            gc = f"{r['gc_pct']:.0f}" if r.get("gc_pct") is not None else "—"
            lines.append(
                f"| {r['id']} | {r['length']} | {gc} | {r['na_mm']} | {r['mg_mm']} "
                f"| {r['tm_exp']:.1f} | {r['tm_pred']:.1f} | {r['error']:+.1f} |"
            )

    lines += [
        "",
        "## Prediction method",
        "- Base NN: SantaLucia 1998 (DOI 10.1073/pnas.95.4.1460) via primer3-py.",
        "- Mg²⁺/dNTP salt correction: Owczarzy 2008 (DOI 10.1021/bi702363u) "
        "(note: `thermodynamics.py` header may say '2004' — Owczarzy 2004 is Na⁺-only).",
        "- Validation datasets are **independent** of the SantaLucia 1998 training set.",
        "- Short oligos (≤12 nt): larger prediction errors are expected (boundary of NN validity).",
        "",
        "*For research use only. Not for clinical in-vitro diagnostic use.*",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Report written: {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Validate the tool's Tm model against Owczarzy benchmarks.")
    ap.add_argument("--benchmark", default="calibration/tm_benchmark.json")
    ap.add_argument("--report",    default="calibration/tm_report.md")
    args = ap.parse_args()
    run_check(args.benchmark, args.report)
