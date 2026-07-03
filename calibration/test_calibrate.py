#!/usr/bin/env python3
"""
test_calibrate.py — self-contained tests for the calibration math (no backend needed).
Run: python calibration/test_calibrate.py
"""
import numpy as np

import calibrate_weights as cw


def test_simplex_projection():
    for v in [np.array([0.5, 0.2, 0.9]), np.array([-1.0, 2.0, 0.0]), np.random.randn(15)]:
        w = cw.project_simplex(v)
        assert abs(w.sum() - 1.0) < 1e-9, "simplex sum != 1"
        assert (w >= -1e-12).all(), "negative weight"
    print("PASS test_simplex_projection")


def test_large_lambda_recovers_prior():
    rng = np.random.default_rng(0)
    X = rng.uniform(0, 100, size=(30, 15))
    y = rng.uniform(0, 100, size=30)
    w = cw.fit_weights(X, y, cw.V4_WEIGHTS.copy(), lam=1e9)
    assert np.max(np.abs(w - cw.V4_WEIGHTS)) < 1e-3, "huge lambda should keep ~V4"
    print("PASS test_large_lambda_recovers_prior")


def test_synthetic_recovery_boosts_correlated_criterion():
    """Build data where the outcome depends mostly on ONE criterion; calibration
    (small lambda) should give that criterion more weight than the V4 prior."""
    rng = np.random.default_rng(42)
    n, d = 200, 15
    X = rng.uniform(0, 100, size=(n, d))
    true_idx = 6  # bound_fraction_binding in V4_KEYS
    true_w = np.full(d, 0.01)
    true_w[true_idx] = 1.0 - 0.01 * (d - 1)
    y = X @ true_w + rng.normal(0, 1.0, size=n)  # low noise
    w = cw.fit_weights(X, y, cw.V4_WEIGHTS.copy(), lam=0.0)
    assert w[true_idx] > cw.V4_WEIGHTS[true_idx], "correlated criterion should gain weight"
    assert w[true_idx] == max(w), "correlated criterion should dominate"
    # correlation table should rank the true criterion first
    corr = cw.correlation_table(X, y)
    assert corr[0][0] == cw.V4_KEYS[true_idx], "top-correlated criterion mislabeled"
    print(f"PASS test_synthetic_recovery (w[{cw.V4_KEYS[true_idx]}] "
          f"{cw.V4_WEIGHTS[true_idx]:.3f} -> {w[true_idx]:.3f})")


def test_adopt_gate_blocks_small_n():
    rng = np.random.default_rng(1)
    X = rng.uniform(0, 100, size=(5, 15))
    y = rng.uniform(0, 100, size=5)
    dec = cw.calibrate(X, y, n_min=20)
    assert dec["status"] == "KEEP V4", "gate must block adoption when N < N_MIN"
    print("PASS test_adopt_gate_blocks_small_n")


def test_pearson_spearman_sane():
    x = np.arange(10, dtype=float)
    assert cw.pearson(x, 2 * x + 1) > 0.999
    assert cw.spearman(x, x ** 2) > 0.999  # monotonic
    print("PASS test_pearson_spearman_sane")


if __name__ == "__main__":
    test_simplex_projection()
    test_large_lambda_recovers_prior()
    test_synthetic_recovery_boosts_correlated_criterion()
    test_adopt_gate_blocks_small_n()
    test_pearson_spearman_sane()
    print("\nAll calibration tests passed.")
