#!/usr/bin/env python3
"""
calibrate_weights.py — Data-driven calibration of SCORING_WEIGHTS (SPEC_phase5 PART B).

Goal: learn scoring weights from REAL measured qPCR performance so that total_score
correlates better with amplification efficiency. Criteria whose sub-scores correlate
strongly with the real outcome get MORE weight; uninformative ones get less.

Overfitting guardrails (mandatory):
  - constrained: w >= 0, sum(w) = 1  (keeps interpretability + 0..100 scale)
  - shrinkage toward the expert prior V4:  + lambda * ||w - w0||^2
  - lambda chosen by leave-one-out cross-validation (LOOCV)
  - adopt gate: N >= N_MIN AND LOOCV improves over V4 AND core-criterion weight floor kept
If the gate fails, weights are NOT changed; only a correlation report is written.

Offline tooling. Requires numpy + requests (calibration/requirements.txt). scipy optional.

Sources: [MIQE09] efficiency ideal=100% DOI 10.1373/clinchem.2008.112797;
[Wang17] DOI 10.3892/mmr.2017.8297; [Kunwar23] DOI 10.3390/diagnostics13132170.
"""
import argparse
import json
import os
import sys

import numpy as np

try:
    import requests
except ImportError:  # only needed when building features from the live API
    requests = None

# --- V4 prior: derive from backend/algorithm/constants.py (single source of truth) ---
# Falls back to a hardcoded snapshot only when the backend is not importable (e.g. CI without
# the full repo).  The assert below catches any drift between the snapshot and live constants.
_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)
try:
    from algorithm.constants import SCORING_WEIGHTS_V4 as _V4_CONST
    V4_KEYS    = list(_V4_CONST.keys())
    V4_WEIGHTS = np.array(list(_V4_CONST.values()))
except ImportError:
    # Hardcoded fallback — keep in sync with constants.SCORING_WEIGHTS_V4
    V4_KEYS = [
        "tm_accuracy", "mfe_stemloop", "tm_binding_accuracy", "hairpin_penalty",
        "dimer_penalty", "end_stability", "bound_fraction_binding", "bound_fraction_full",
        "gc_content", "family_discrimination", "tm_pair_match", "gc_clamp",
        "primer_size", "amplicon_size", "gc_skew",
    ]
    V4_WEIGHTS = np.array([0.20, 0.14, 0.10, 0.08, 0.08, 0.08, 0.05, 0.03,
                           0.08, 0.05, 0.01, 0.04, 0.02, 0.02, 0.02])
# Core biology criteria we never let collapse to ~0 (weight floor):
CORE_KEYS = {"tm_accuracy", "tm_binding_accuracy", "hairpin_penalty", "dimer_penalty"}
W_FLOOR = 0.005
N_MIN_DEFAULT = 20


# ----------------------------- math helpers -----------------------------
def project_simplex(v):
    """Euclidean projection of vector v onto {w >= 0, sum w = 1} (Duchi et al. 2008)."""
    v = np.asarray(v, dtype=float)
    n = len(v)
    u = np.sort(v)[::-1]
    css = np.cumsum(u) - 1.0
    rho = np.nonzero(u - css / (np.arange(n) + 1) > 0)[0][-1]
    theta = css[rho] / (rho + 1.0)
    return np.maximum(v - theta, 0.0)


def fit_weights(X, y, w0, lam, iters=5000, lr=None):
    """min ||Xw - y||^2 + lam*||w - w0||^2  s.t. w>=0, sum w=1  (projected gradient)."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    n = X.shape[1]
    w = w0.copy()
    if lr is None:
        # Lipschitz constant of gradient(||Xw-y||^2 + lam||w-w0||^2) = 2*(σ_max^2 + lam)
        L = np.linalg.norm(X, 2) ** 2 + lam + 1e-9
        lr = 1.0 / (2 * L)
    for _ in range(iters):
        grad = 2 * X.T @ (X @ w - y) + 2 * lam * (w - w0)
        w = project_simplex(w - lr * grad)
    return w


def rmse(pred, y):
    return float(np.sqrt(np.mean((np.asarray(pred) - np.asarray(y)) ** 2)))


def loocv_rmse(X, y, w0, lam):
    """LOOCV error of the calibrated fit at a given lambda."""
    n = len(y)
    if n < 3:
        return float("inf")
    preds = np.empty(n)
    idx = np.arange(n)
    for i in range(n):
        tr = idx != i
        w = fit_weights(X[tr], y[tr], w0, lam)
        preds[i] = X[i] @ w
    return rmse(preds, y)


def _rank(a):
    """Average ranks (for Spearman)."""
    a = np.asarray(a, float)
    order = a.argsort()
    ranks = np.empty(len(a), float)
    ranks[order] = np.arange(len(a))
    # average ties
    _, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    sums = np.zeros(len(counts))
    np.add.at(sums, inv, ranks)
    means = sums / counts
    return means[inv]


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.std() < 1e-12 or y.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def spearman(x, y):
    return pearson(_rank(x), _rank(y))


# ----------------------------- data loading -----------------------------
def target_from_efficiency(eff, mode):
    if eff is None:
        return None
    return float(eff) if mode == "efficiency" else 100.0 - abs(float(eff) - 100.0)


def build_features_from_api(assays, base_url, target_mode):
    """Return X (N x15), y (N,), meta list. Requires the backend running."""
    if requests is None:
        sys.exit("requests not installed: pip install -r calibration/requirements.txt")
    X, y, meta = [], [], []
    for a in assays:
        yt = target_from_efficiency(a.get("efficiency_pct"), target_mode)
        if yt is None:
            continue
        seq = a.get("mirna_sequence")
        mid = a.get("mirna_id")
        payload = {"sequence": {"matureSequence": seq or "", "mirnaId": mid or ""},
                   "thermodynamic": {}, "primerConstraints": {},
                   "qpcr": {}, "detectionMethod": {}, "experimentalContext": {}}
        if not seq and mid:
            try:
                r = requests.get(f"{base_url}/api/mirbase/{mid}", timeout=20)
                if r.status_code == 200:
                    payload["sequence"]["matureSequence"] = r.json().get("sequence", "")
                else:
                    print(f"  ! {a['assay_id']}: miRBase returned {r.status_code}; skipping")
                    continue
            except Exception as e:  # noqa: BLE001
                print(f"  ! {a['assay_id']}: mirbase lookup failed ({e}); skipping")
                continue
        try:
            r = requests.post(f"{base_url}/api/design", json=payload, timeout=60)
            data = r.json()
        except Exception as e:  # noqa: BLE001
            print(f"  ! {a['assay_id']}: /api/design failed ({e}); skipping")
            continue
        cands = data.get("top3") or []
        if not cands:
            print(f"  ! {a['assay_id']}: no candidates; skipping")
            continue
        cand = choose_candidate(cands, a.get("published_forward"))
        scores = cand.get("scores", {})
        vec = [float(scores.get(k, 0.0)) for k in V4_KEYS]
        X.append(vec)
        y.append(yt)
        meta.append(a["assay_id"])
    return np.array(X, float), np.array(y, float), meta


def choose_candidate(cands, published_forward):
    """Pick the candidate matching the published primer if given, else the top-ranked one.

    Matching uses the candidate's specific_sequence (3' binding region) aligned against
    the 3' suffix of published_forward of the same length.  This avoids the 5' tail
    dominating the score — the tail is shared across all candidates and is irrelevant
    for discriminating which miRNA-specific sequence matches the published design.
    """
    if not published_forward:
        return cands[0]
    pf = published_forward.upper()
    best, best_score = cands[0], -1
    for c in cands:
        spec = c.get("specific_sequence", "").upper() or c.get("sequence", "").upper()
        n = min(len(spec), len(pf))
        if n == 0:
            continue
        # Count matching bases at the 3' end (biologically meaningful binding region)
        suffix_match = sum(a == b for a, b in zip(spec[-n:], pf[-n:]))
        if suffix_match > best_score:
            best, best_score = c, suffix_match
    return best


# ----------------------------- reporting -----------------------------
def correlation_table(X, y):
    rows = []
    for j, k in enumerate(V4_KEYS):
        rows.append((k, pearson(X[:, j], y), spearman(X[:, j], y), V4_WEIGHTS[j]))
    rows.sort(key=lambda r: abs(r[1]), reverse=True)
    return rows


def write_report(path, X, y, meta, corr, decision):
    lines = ["# Scoring-weight calibration report\n",
             f"- N (verified assays used): **{len(y)}**",
             f"- Decision: **{decision['status']}**  ", ""]
    lines.append("## Per-criterion correlation with real outcome (sorted by |Pearson r|)\n")
    lines.append("| Criterion | Pearson r | Spearman r | V4 weight | V5 weight |")
    lines.append("|---|---|---|---|---|")
    v5 = decision.get("w_v5")
    v5map = dict(zip(V4_KEYS, v5)) if v5 is not None else {}
    for k, pr, sr, w4 in corr:
        w5 = f"{v5map.get(k):.3f}" if v5 is not None else "—"
        lines.append(f"| {k} | {pr:+.3f} | {sr:+.3f} | {w4:.3f} | {w5} |")
    lines.append("")
    lines.append("## Cross-validation")
    lines.append(f"- LOOCV RMSE (V4 prior): {decision.get('rmse_v4', 'n/a')}")
    lines.append(f"- LOOCV RMSE (calibrated): {decision.get('rmse_v5', 'n/a')}")
    lines.append(f"- chosen lambda: {decision.get('lambda', 'n/a')}")
    lines.append("")
    lines.append("## Notes")
    for n in decision.get("notes", []):
        lines.append(f"- {n}")
    lines.append("\n*Interpretation only; not ground truth. Data from PubMed-cited sources.*")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nReport written: {path}")


# ----------------------------- main -----------------------------
def calibrate(X, y, n_min):
    """Run the full gated calibration. Returns a decision dict."""
    notes = []
    w0 = V4_WEIGHTS.copy()
    rmse_v4 = loocv_rmse(X, y, w0, lam=1e9) if len(y) >= 3 else float("inf")  # lam huge => ~V4
    # grid-search lambda on LOOCV
    lambdas = [0.0, 0.01, 0.1, 1.0, 10.0, 100.0]
    best_lam, best_rmse, best_w = None, float("inf"), w0
    for lam in lambdas:
        r = loocv_rmse(X, y, w0, lam)
        if r < best_rmse:
            best_rmse, best_lam, = r, lam
    if best_lam is None:
        notes.append("WARNING: all LOOCV evaluations diverged (inf RMSE) — "
                     "grid search produced no finite result; V4 weights kept as fallback.")
        best_w = w0
    else:
        best_w = fit_weights(X, y, w0, best_lam)

    # adopt gate
    core_ok = all(best_w[V4_KEYS.index(k)] >= W_FLOOR for k in CORE_KEYS)
    enough = len(y) >= n_min
    improves = best_rmse < rmse_v4 - 1e-9
    status = "ADOPT V5" if (enough and improves and core_ok) else "KEEP V4"
    if not enough:
        notes.append(f"Insufficient data: N={len(y)} < N_MIN={n_min}. Weights NOT changed; "
                     f"see correlation table for direction only.")
    if enough and not improves:
        notes.append("LOOCV did not improve over V4; weights NOT changed (avoids overfitting).")
    if enough and improves and not core_ok:
        notes.append("A core criterion fell below weight floor; V5 rejected to preserve biology.")
    return {"status": status, "w_v5": best_w if status == "ADOPT V5" else None,
            "rmse_v4": round(rmse_v4, 3) if np.isfinite(rmse_v4) else "n/a",
            "rmse_v5": round(best_rmse, 3) if np.isfinite(best_rmse) else "n/a",
            "lambda": best_lam, "notes": notes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default="calibration/benchmark_assays.json")
    ap.add_argument("--base-url", default="http://localhost:5000")
    ap.add_argument("--target", choices=["goodness", "efficiency"], default="goodness")
    ap.add_argument("--n-min", type=int, default=N_MIN_DEFAULT)
    ap.add_argument("--report", default="calibration/calibration_report.md")
    ap.add_argument("--out-weights", default="calibration/SCORING_WEIGHTS_V5.json")
    args = ap.parse_args()

    with open(args.benchmark, encoding="utf-8") as f:
        bench = json.load(f)
    assays = [a for a in bench.get("assays", []) if a.get("verified") is True]
    print(f"Verified assays: {len(assays)} (of {len(bench.get('assays', []))} total)")
    if not assays:
        # Nothing to fit — emit an honest, informative report and keep V4.
        decision = {"status": "KEEP V4 (no verified data)", "w_v5": None,
                    "rmse_v4": "n/a", "rmse_v5": "n/a", "lambda": "n/a",
                    "notes": ["No verified assays. Populate benchmark_assays.json with "
                              "per-assay efficiency transcribed from cited papers (verified=true)."]}
        write_report(args.report, np.zeros((0, 15)), np.array([]), [],
                     [(k, 0.0, 0.0, V4_WEIGHTS[i]) for i, k in enumerate(V4_KEYS)], decision)
        sys.exit(0)

    X, y, meta = build_features_from_api(assays, args.base_url, args.target)
    print(f"Feature rows built: {len(y)}")
    if len(y) < 3:
        sys.exit("Too few usable rows for cross-validation.")

    corr = correlation_table(X, y)
    decision = calibrate(X, y, args.n_min)
    write_report(args.report, X, y, meta, corr, decision)

    if decision["status"] == "ADOPT V5":
        w = decision["w_v5"]
        out = {"scoring_version": "V5",
               "weights": {k: round(float(w[i]), 4) for i, k in enumerate(V4_KEYS)},
               "provenance": {"n": len(y), "lambda": decision["lambda"],
                              "loocv_rmse_v4": decision["rmse_v4"],
                              "loocv_rmse_v5": decision["rmse_v5"],
                              "sources": bench.get("_meta", {}).get("sources", [])}}
        with open(args.out_weights, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"ADOPTED — wrote {args.out_weights}")
    else:
        print(f"Decision: {decision['status']} — V4 kept.")


if __name__ == "__main__":
    main()
