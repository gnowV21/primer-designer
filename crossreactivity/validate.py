"""
validate.py — compare predicted R with published cross-reactivity measurements.

Inputs: validation/crossreactivity_<source>.csv with columns
    assay_mirna, target_mirna, measured_value, unit, source_figure_or_table
unit: '%' (relative detection vs perfect match) or 'dCq' (Cq(mismatch) − Cq(match)).
Rows with an empty measured_value are templates still to be filled — they are
skipped and counted, never imputed.

Per source: Spearman ρ (predicted R vs measured R), ROC AUC for "cross-reactive or
not" at the source's threshold, and the pairs on the wrong side of it. Plus a
sanity check over the whole matrix: miRNA pairs differing at 1–2 positions must
score far above random pairs.

Usage (repo root, after build_matrix):
    python -m crossreactivity.validate [--threshold-pct 1]
Writes validation/crossreactivity_validation_report.md and .json.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random

import numpy as np
import pandas as pd

from crossreactivity.api import CrossReactivity
from crossreactivity.model import load_config, load_mature

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
VAL_DIR = os.path.join(_ROOT, "validation")
MATRIX = os.path.join(_ROOT, "outputs", "crossreactivity_long.parquet")

# Sources whose numbers were also used to set model constants — agreement with them
# checks the implementation, it is not independent validation.
CIRCULAR = {"chen2005": "ΔCq_RT constants (rG·dT 3.7 %, 0.1 %, ≤ 0.3 %) come from Chen 2005"}


def measured_r(value: float, unit: str) -> float:
    unit = unit.strip().lower()
    if unit in ("%", "pct", "percent"):
        return value / 100.0
    if unit in ("dcq", "dct", "delta_cq", "δcq"):
        return 2.0 ** -value
    raise ValueError(f"unknown unit {unit!r} (use '%' or 'dCq')")


def spearman(x, y) -> float | None:
    from scipy.stats import spearmanr
    if len(x) < 3:
        return None
    rho = spearmanr(x, y).statistic
    return None if math.isnan(rho) else float(rho)


def roc_auc(scores, labels) -> float | None:
    """Mann–Whitney AUC; None when only one class is present."""
    pos = [s for s, l in zip(scores, labels) if l]
    neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def compare_source(xr: CrossReactivity, path: str, threshold: float) -> dict:
    name = os.path.basename(path).removeprefix("crossreactivity_").removesuffix(".csv")
    df = pd.read_csv(path, dtype={"measured_value": "string"})
    filled = df[df["measured_value"].fillna("").str.strip() != ""].copy()
    res = {"source": name, "file": os.path.relpath(path, _ROOT), "rows": len(df),
           "rows_filled": len(filled), "circular": CIRCULAR.get(name)}
    if filled.empty:
        res["status"] = "no measured values yet — fill measured_value in the CSV"
        return res
    filled["measured_R"] = [measured_r(float(v), u) for v, u in
                            zip(filled["measured_value"], filled["unit"])]
    preds, missing = [], []
    for a, t in zip(filled["assay_mirna"], filled["target_mirna"]):
        try:
            preds.append(xr.r(a, t))
        except KeyError:
            preds.append(np.nan)
            missing.append(a)
    filled["predicted_R"] = preds
    ok = filled.dropna(subset=["predicted_R"])
    off = ok[ok["assay_mirna"] != ok["target_mirna"]]
    labels = (off["measured_R"] >= threshold).tolist()
    pred_pos = (off["predicted_R"] >= threshold).tolist()
    wrong = off[[p != l for p, l in zip(pred_pos, labels)]]
    res.update({
        "status": "compared",
        "n_pairs": len(off),
        "assays_not_in_matrix": sorted(set(missing)),
        "threshold_R": threshold,
        "spearman_rho": spearman(off["predicted_R"], off["measured_R"]),
        "roc_auc": roc_auc(off["predicted_R"].tolist(), labels),
        "misclassified": wrong[["assay_mirna", "target_mirna", "measured_R",
                                "predicted_R"]].to_dict("records"),
    })
    return res


def sanity_family_vs_random(xr: CrossReactivity, seed: int = 0) -> dict:
    """Pairs of equal-length miRNAs differing at 1–2 positions vs random pairs."""
    cfg = load_config()
    mature = load_mature(cfg["mirbase_index_path"], cfg["species"])
    names = sorted(n for n in mature if n in xr.assays)
    by_len: dict[int, list[str]] = {}
    for n in names:
        by_len.setdefault(len(mature[n]), []).append(n)
    close = []
    for group in by_len.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                d = sum(x != y for x, y in zip(mature[a], mature[b]))
                if 1 <= d <= 2:
                    close += [(a, b), (b, a)]
    rng = random.Random(seed)
    rand = [tuple(rng.sample(names, 2)) for _ in range(20000)]
    rc = np.array([xr.r(a, b) for a, b in close])
    rr = np.array([xr.r(a, b) for a, b in rand])
    return {
        "n_close_pairs": len(close), "n_random_pairs": len(rand),
        "close_mean_R": float(rc.mean()) if len(rc) else None,
        "close_median_R": float(np.median(rc)) if len(rc) else None,
        "close_frac_above_10pct": float((rc > 2 ** -3.3).mean()) if len(rc) else None,
        "random_mean_R": float(rr.mean()),
        "random_frac_above_10pct": float((rr > 2 ** -3.3).mean()),
        "passes": bool(len(rc) and rc.mean() > 10 * rr.mean()),
    }


def _md(report: dict) -> str:
    lines = ["# Cross-reactivity matrix — comparison with published data", "",
             f"Matrix: `{report['matrix']}` (tool {report.get('tool_version')}, "
             f"miRBase {report.get('mirbase_release')}). Cross-reactive = R ≥ "
             f"{100 * report['threshold_R']:g} %.", ""]
    for s in report["sources"]:
        lines += [f"## {s['source']}", "", f"File: `{s['file']}` — {s['rows_filled']}/"
                  f"{s['rows']} rows filled."]
        if s.get("circular"):
            lines.append(f"**Not independent:** {s['circular']}.")
        if s["status"] != "compared":
            lines += ["", f"_{s['status']}_", ""]
            continue
        lines += ["", f"- pairs compared: {s['n_pairs']}",
                  f"- Spearman ρ: {s['spearman_rho']}",
                  f"- ROC AUC: {s['roc_auc']}",
                  f"- misclassified: {len(s['misclassified'])}", ""]
        if s["misclassified"]:
            lines += ["| assay | target | measured R | predicted R |", "|---|---|---|---|"]
            lines += [f"| {m['assay_mirna']} | {m['target_mirna']} | {m['measured_R']:.4f} | "
                      f"{m['predicted_R']:.4f} |" for m in s["misclassified"]]
            lines.append("")
    sc = report["sanity"]
    lines += ["## Sanity check — near-identical vs random pairs", "",
              f"- {sc['n_close_pairs']} ordered pairs of equal-length miRNAs differing at 1–2 "
              f"positions: mean R {sc['close_mean_R']:.4f}, median {sc['close_median_R']:.4f}, "
              f"{100 * sc['close_frac_above_10pct']:.1f} % above 10 %.",
              f"- {sc['n_random_pairs']} random pairs: mean R {sc['random_mean_R']:.6f}, "
              f"{100 * sc['random_frac_above_10pct']:.3f} % above 10 %.",
              f"- passes (close mean > 10 × random mean): **{sc['passes']}**", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", default=MATRIX)
    ap.add_argument("--threshold-pct", type=float, default=1.0,
                    help="measured/predicted R at or above this %% counts as cross-reactive")
    args = ap.parse_args(argv)
    xr = CrossReactivity.load(args.matrix)
    thr = args.threshold_pct / 100.0
    report = {
        "matrix": os.path.relpath(args.matrix, _ROOT),
        "tool_version": xr.metadata.get("tool_version"),
        "mirbase_release": (xr.metadata.get("mirbase") or {}).get("mirbase_release"),
        "threshold_R": thr,
        "sources": [compare_source(xr, p, thr) for p in
                    sorted(glob.glob(os.path.join(VAL_DIR, "crossreactivity_*.csv")))],
        "sanity": sanity_family_vs_random(xr),
    }
    with open(os.path.join(VAL_DIR, "crossreactivity_validation_report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=1, ensure_ascii=False, default=str)
    with open(os.path.join(VAL_DIR, "crossreactivity_validation_report.md"), "w",
              encoding="utf-8") as f:
        f.write(_md(report))
    print(_md(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
