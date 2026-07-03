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
  3. Salt correction path (confirmed from primer3 C source, oligotm.c):
     - 'santalucia' mode (tool default, NOT 'owczarzy'):
         a. Divalent→monovalent: K_equiv = 120 * sqrt(Mg - dNTP)  [von Ahsen 2001]
         b. K_mM += K_equiv, then SantaLucia entropy correction: dS += 0.368*(len-1)*ln(K/1000)
     - 'owczarzy' mode (NOT used by tool): direct Owczarzy 2004 (Na+) / 2008 (Mg2+) formula.
     CIRCULARITY VERDICT:
       Na series: santalucia entropy correction on K_mM (Na+); Owczarzy 2004 Na+ data = FULLY INDEPENDENT.
       Mg series: von Ahsen 2001 (not Owczarzy) converts Mg2+ → equiv K_mM, then SantaLucia correction.
                  Owczarzy 2008 Mg2+ data = INDEPENDENT from BOTH steps (separate paper, separate dataset).
       → No circularity for either series. Safe to report both as independent validation.
  4. RT primer exclusion: oligos with primer_type='rt' are excluded from Tm accuracy check.
     RT primers hybridize with miRNA (RNA) → DNA:RNA hybrid; DNA:DNA NN params are not valid
     for absolute Tm on an RNA template (Sugimoto 1995). Only forward/reverse (DNA:DNA) are validated.
  5. --expand-salt: use all 9 Mg + 5 Na salt columns (~242 data points)
     instead of only the single reference column (34 points). Reveals whether
     the salt-correction function tracks experiment across the full salt range.

Usage:
  python calibration/check_tm.py
  python calibration/check_tm.py --expand-salt

Sources:
  [SL98]       DOI 10.1073/pnas.95.4.1460  (NN params + SantaLucia salt correction)
  [vAhsen01]   DOI 10.1093/clinchem/47.11.1956  (von Ahsen 2001 divalent→monovalent formula)
  [Owczarzy04] DOI 10.1021/bi034621r       (Na+ series, Table 2 — independent validation)
  [Owczarzy08] DOI 10.1021/bi702363u       (Mg2+ series, Table 1 — independent validation)
  [Sugimoto95] DOI 10.1021/bi00035a029     (DNA:RNA hybrid NN — NOT implemented here)
"""
import argparse
import json
import sys
import os

BIAS_WARN_C = 1.5   # systematic bias threshold for report flag
NOISE_FLOOR_C = 0.3  # Owczarzy 2008 experimental sigma(Tm); errors within 1-2x are excellent


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
      salt_na_mm    -> mv_conc  (monovalent; 1 mM for Mg-only Tris buffer)
      salt_mg_mm    -> dv_conc  (Mg2+ mM; 0 for Na-only series)
      dntp_mm       -> dntp_conc (0 for both Owczarzy series)
      primer_conc_nm = Ct (total strand).  primer3.calc_tm uses dna_conc/4
                      internally, so pass Ct directly -- do NOT pre-divide.
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


def expand_salt_series(oligos: list, meta: dict) -> list:
    """
    Expand each benchmark oligo across ALL measured salt concentrations.

    Mg-series: 18 oligos x 9 Mg concentrations = 162 data points
    Na-series: 16 oligos x 5 Na concentrations =  80 data points
    Total: 242 vs default 34 (single reference column).
    """
    mg_cols = meta.get("mg_columns_mM", [0.5, 1.5, 3.0, 10, 20, 50, 125, 300, 600])
    na_cols = meta.get("na_columns_mM", [69, 119, 220, 621, 1020])
    expanded = []
    for o in oligos:
        if "tm_by_mg_mM" in o:
            for i, mg in enumerate(mg_cols):
                if i < len(o["tm_by_mg_mM"]) and o["tm_by_mg_mM"][i] is not None:
                    entry = dict(o)
                    entry["salt_mg_mm"] = float(mg)
                    entry["tm_experimental_c"] = o["tm_by_mg_mM"][i]
                    entry["oligo_id"] = f"{o['oligo_id']}@Mg{mg}mM"
                    expanded.append(entry)
        elif "tm_by_na_mM" in o:
            for i, na in enumerate(na_cols):
                if i < len(o["tm_by_na_mM"]) and o["tm_by_na_mM"][i] is not None:
                    entry = dict(o)
                    entry["salt_na_mm"] = float(na)
                    entry["tm_experimental_c"] = o["tm_by_na_mM"][i]
                    entry["oligo_id"] = f"{o['oligo_id']}@Na{na}mM"
                    expanded.append(entry)
    return expanded


def _stats(rr):
    if not rr:
        return None, None
    e = [r["error"] for r in rr]
    return sum(abs(x) for x in e) / len(e), sum(e) / len(e)


def run_check(benchmark_path: str, report_path: str, expand_salt: bool = False):
    with open(benchmark_path, encoding="utf-8") as f:
        bench = json.load(f)

    meta = bench.get("_meta", {})
    all_oligos = bench.get("oligos", [])
    verified = [o for o in all_oligos if o.get("verified") is True]

    print(f"\n=== Tm model accuracy check ===")
    print(f"Benchmark: {benchmark_path}")
    print(f"Verified entries: {len(verified)} / {len(all_oligos)} total")

    if expand_salt:
        oligos = expand_salt_series(verified, meta)
        print(f"  --expand-salt: {len(oligos)} data points (all salt columns)")
    else:
        oligos = verified
        print(f"  Default: {len(oligos)} data points (single reference column per oligo)")

    # Exclude RT primers from absolute Tm validation: RT primer hybridizes with miRNA (RNA)
    # → DNA:RNA hybrid; DNA:DNA NN params (primer3) are not valid for absolute Tm on RNA template.
    # Only forward/reverse primers (DNA:DNA duplex path) are meaningfully validated here.
    rt_excluded = [o for o in oligos if o.get("primer_type") == "rt"]
    if rt_excluded:
        oligos = [o for o in oligos if o.get("primer_type") != "rt"]
        print(f"  Excluded {len(rt_excluded)} RT primer entries (DNA:RNA hybrid — DNA:DNA NN invalid for absolute Tm)")

    print()

    if not oligos:
        print("No entries to process.")
        _write_report(report_path, [], bench, expand_salt=expand_salt)
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
        gc = o.get("gc_pct")
        rows.append({
            "id":         o["oligo_id"],
            "length":     o.get("length_nt", len(o["sequence_dna"])),
            "gc_pct":     gc,
            "tm_exp":     exp,
            "tm_pred":    round(pred, 1),
            "error":      round(err, 1),
            "source_doi": o.get("source_doi", ""),
            "series":     "mg" if is_mg else "na",
            "na_mm":      o.get("salt_na_mm", 0),
            "mg_mm":      o.get("salt_mg_mm", 0),
        })
        if not expand_salt:
            cond = (f"[Mg {o.get('salt_mg_mm',0):.1f}mM Na {o.get('salt_na_mm',0):.0f}mM]"
                    if is_mg else f"[Na {o.get('salt_na_mm',0):.0f}mM]")
            print(f"  {o['oligo_id']:<28} {cond}  exp={exp:.1f} C  pred={pred:.1f} C  err={err:+.1f} C")

    if not rows:
        print("No rows processed.")
        _write_report(report_path, rows, bench, expand_salt=expand_salt)
        return

    mg_rows = [r for r in rows if r["series"] == "mg"]
    na_rows = [r for r in rows if r["series"] == "na"]

    # Stratify by oligo length
    short_rows = [r for r in rows if r["length"] <= 12]
    med_rows   = [r for r in rows if 13 <= r["length"] <= 20]
    long_rows  = [r for r in rows if r["length"] >= 21]

    # Stratify by GC content
    gc_lo_rows = [r for r in rows if (r.get("gc_pct") or 0) <= 40]
    gc_mi_rows = [r for r in rows if 40 < (r.get("gc_pct") or 0) <= 65]
    gc_hi_rows = [r for r in rows if (r.get("gc_pct") or 0) > 65]

    all_mae, all_bias   = _stats(rows)
    mg_mae,  mg_bias    = _stats(mg_rows)
    na_mae,  na_bias    = _stats(na_rows)

    print(f"\n{'-'*62}")
    print(f"  All ({len(rows)})         MAE={all_mae:.2f} C   Bias={all_bias:+.2f} C")
    if mg_rows:
        print(f"  Mg series ({len(mg_rows)})    MAE={mg_mae:.2f} C   Bias={mg_bias:+.2f} C  [Owczarzy 2008]")
    if na_rows:
        print(f"  Na series ({len(na_rows)})    MAE={na_mae:.2f} C   Bias={na_bias:+.2f} C  [Owczarzy 2004]")

    print(f"\n  -- By length --")
    for label, grp in [("<=12 nt", short_rows), ("13-20 nt", med_rows), ("21+ nt", long_rows)]:
        if grp:
            mae, bias = _stats(grp)
            print(f"  {label} ({len(grp)})    MAE={mae:.2f} C   Bias={bias:+.2f} C")

    print(f"\n  -- By GC% --")
    for label, grp in [("GC<=40%", gc_lo_rows), ("GC 41-65%", gc_mi_rows), ("GC>65%", gc_hi_rows)]:
        if grp:
            mae, bias = _stats(grp)
            print(f"  {label} ({len(grp)})    MAE={mae:.2f} C   Bias={bias:+.2f} C")

    if abs(all_bias) > BIAS_WARN_C:
        direction = "UNDER" if all_bias < 0 else "OVER"
        print(f"\n  WARNING: tool {direction}-predicts Tm by {all_bias:+.2f} C on average")
    print(f"  (Experimental noise floor sigma~{NOISE_FLOOR_C} C; errors within 1-2 C are excellent)")

    _write_report(report_path, rows, bench,
                  expand_salt=expand_salt,
                  all_mae=all_mae, all_bias=all_bias,
                  mg_rows=mg_rows, na_rows=na_rows,
                  mg_mae=mg_mae, mg_bias=mg_bias,
                  na_mae=na_mae, na_bias=na_bias,
                  short_rows=short_rows, med_rows=med_rows, long_rows=long_rows,
                  gc_lo_rows=gc_lo_rows, gc_mi_rows=gc_mi_rows, gc_hi_rows=gc_hi_rows)


def _write_report(path, rows, bench,
                  expand_salt=False,
                  all_mae=None, all_bias=None,
                  mg_rows=None, na_rows=None,
                  mg_mae=None, mg_bias=None,
                  na_mae=None, na_bias=None,
                  short_rows=None, med_rows=None, long_rows=None,
                  gc_lo_rows=None, gc_mi_rows=None, gc_hi_rows=None):
    mg_rows    = mg_rows or []
    na_rows    = na_rows or []
    short_rows = short_rows or []
    med_rows   = med_rows or []
    long_rows  = long_rows or []
    gc_lo_rows = gc_lo_rows or []
    gc_mi_rows = gc_mi_rows or []
    gc_hi_rows = gc_hi_rows or []

    mode_note = (f"**expand-salt mode**: all salt columns ({len(rows)} data points, "
                 f"18 Mg oligos × 9 conc + 16 Na oligos × 5 conc)"
                 if expand_salt else
                 f"**default mode**: single reference column per oligo ({len(rows)} data points)")

    lines = [
        "# Tm Model Accuracy Report — SPEC_phase5 PART C",
        "",
        f"- {mode_note}",
        "- Tool model: SantaLucia 1998 NN (primer3-py, `salt_corrections_method='santalucia'`)",
        "- Salt correction pipeline (confirmed from primer3 C source, oligotm.c):",
        "  - Na⁺ series: SantaLucia entropy correction directly on K_mM (Na⁺ only).",
        "    → **Owczarzy 2004 Na⁺ data: fully independent** validation of monovalent salt correction.",
        "  - Mg²⁺ series: step 1 = von Ahsen 2001 divalent→monovalent `120√(Mg−dNTP)`; "
        "step 2 = SantaLucia entropy on combined K_mM.",
        "    → **Owczarzy 2008 Mg²⁺ data: fully independent** from both steps "
        "(von Ahsen 2001 ≠ Owczarzy formula; SantaLucia 1998 ≠ Owczarzy 2008).",
        "  - **No circularity** for either series — safe to report both as independent validation.",
        "- Predictions at **each data point's measured conditions** (per-oligo salt/Ct from benchmark).",
        "- Ct convention: `primer_conc_nm` = Ct (total strand); passed directly to primer3.calc_tm "
        "which divides by 4 internally.",
        "- RT primers excluded: DNA:RNA hybrid Tm uses DNA:DNA NN params (approx. only); "
        "only forward/reverse (DNA:DNA) are validated here.",
        f"- Experimental noise floor: σ(Tm) ≈ {NOISE_FLOOR_C} °C (Owczarzy 2008); "
        "errors within 1–2 °C are excellent.",
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
        lines += ["## Summary by dataset", ""]
        lines += [
            "| Series | N | MAE (°C) | Bias (°C) | Source |",
            "|---|---|---|---|---|",
            f"| **All** | {len(rows)} | {all_mae:.2f} | {all_bias:+.2f} | — |",
        ]
        if mg_rows:
            lines.append(f"| Mg²⁺ series (Owczarzy 2008) | {len(mg_rows)} "
                         f"| {mg_mae:.2f} | {mg_bias:+.2f} | DOI 10.1021/bi702363u |")
        if na_rows:
            lines.append(f"| Na⁺ series (Owczarzy 2004)  | {len(na_rows)} "
                         f"| {na_mae:.2f} | {na_bias:+.2f} | DOI 10.1021/bi034621r |")
        lines.append("")

        # By length
        lines += ["## Summary by oligo length", ""]
        lines += [
            "| Length | N | MAE (°C) | Bias (°C) |",
            "|---|---|---|---|",
        ]
        for label, grp in [("≤12 nt", short_rows), ("13–20 nt", med_rows), ("21+ nt", long_rows)]:
            if grp:
                mae, bias = _stats(grp)
                lines.append(f"| {label} | {len(grp)} | {mae:.2f} | {bias:+.2f} |")
        lines.append("")

        # By GC
        lines += ["## Summary by GC%", ""]
        lines += [
            "| GC% | N | MAE (°C) | Bias (°C) |",
            "|---|---|---|---|",
        ]
        for label, grp in [("≤40%", gc_lo_rows), ("41–65%", gc_mi_rows), (">65%", gc_hi_rows)]:
            if grp:
                mae, bias = _stats(grp)
                lines.append(f"| {label} | {len(grp)} | {mae:.2f} | {bias:+.2f} |")
        lines.append("")

        if abs(all_bias) > BIAS_WARN_C:
            direction = "under-predicts" if all_bias < 0 else "over-predicts"
            lines += [
                f"⚠ **Systematic bias = {all_bias:+.2f}°C** (threshold ±{BIAS_WARN_C}°C). "
                f"Tool {direction} Tm.",
                "",
                "Possible causes: (1) SantaLucia salt correction underestimates Mg²⁺ "
                "stabilisation at low [Na⁺] (1 mM Tris buffer); "
                "(2) NN parameters slightly off for short oligos (≤12 nt); "
                "(3) benchmark conditions (1 mM monovalent, no dNTP) differ from tool defaults "
                "(50 mM Na + 1.5 mM Mg + 0.8 mM dNTP). "
                "Do NOT adjust `TM_FORWARD_TARGET` without in-lab measurements at tool conditions.",
                "",
            ]
        else:
            lines.append(f"Bias within ±{BIAS_WARN_C}°C — model well-calibrated for this dataset.")
            lines.append("")

        lines += [
            "## Per-data-point results", "",
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
        "- Salt correction (`salt_corrections_method='santalucia'`, primer3-py default, confirmed from oligotm.c):",
        "  - Na⁺: SantaLucia entropy correction on K_mM. Owczarzy 2004 Na⁺ = independent validation. ✓",
        "  - Mg²⁺: von Ahsen 2001 [DOI 10.1093/clinchem/47.11.1956] converts Mg²⁺−dNTP → K_equiv = 120√(Mg−dNTP), "
        "then SantaLucia entropy on K_mM+K_equiv. Owczarzy 2008 Mg²⁺ = independent from both steps. ✓",
        "  - No circularity for either series.",
        "- Validation datasets are independent of the SantaLucia 1998 training set.",
        "- Short oligos (≤12 nt): larger prediction errors expected (boundary of NN validity).",
        f"- Experimental noise floor: σ(Tm) ≈ {NOISE_FLOOR_C} °C (Owczarzy 2008, UV-melting). "
        "Model errors within 1–2 °C are excellent relative to this baseline.",
        "- ⚠ DNA:RNA hybrid: RT primer Tm uses DNA:DNA NN params. Actual RT primer Tm on miRNA "
        "target (DNA:RNA hybrid) may differ by 3–8 °C (Sugimoto 1995 DNA:RNA params not implemented). "
        "RT primers are excluded from this validation.",
        "",
        "*For research use only. Not for clinical in-vitro diagnostic use.*",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Report written: {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Validate the tool's Tm model against Owczarzy benchmarks.")
    ap.add_argument("--benchmark",    default="calibration/tm_benchmark.json")
    ap.add_argument("--report",       default="calibration/tm_report.md")
    ap.add_argument("--expand-salt",  action="store_true",
                    help="Use all 9 Mg + 5 Na salt columns (~242 points) instead of single reference column.")
    args = ap.parse_args()
    run_check(args.benchmark, args.report, expand_salt=args.expand_salt)
