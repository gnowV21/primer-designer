"""
derivative.py — the -dF/dT melt-peak curve [SPEC_Phase1 §4.2 step 2].

Ported from the existing hrm-tool project; algorithm unchanged, messages translated.

IMPORTANT — the input is RAW fluorescence, not normalized data. The melt-curve
derivative is independent of the 100%->0% normalization step: the peak of -dF/dT
IS the melting temperature Tm of the amplicon, the point where the strands
separate fastest. This is how HRM instruments determine Tm.

Order matters: Savitzky-Golay smoothing is applied BEFORE differentiating.
Differentiating first and smoothing afterwards shifts the peak, moving the
reported Tm.

Differentiation scheme:
  * interior points : central difference,        O(h^2)
  * boundary points : one-sided 2nd-order stencil, same O(h^2)

Raises RuntimeError if smoothing was requested but cannot be applied — it never
silently falls back, because a silent fallback would change the Tm without telling
anyone.
"""

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter


def compute_derivative(
    df: pd.DataFrame,
    smoothing: bool = True,
    sg_window: int = 11,
    sg_polyorder: int = 3,
) -> pd.DataFrame:
    sample_cols = [c for c in df.columns if c != "Temp"]
    temp = df["Temp"].values
    n = len(temp)

    if n < 3:
        raise RuntimeError(
            f"At least 3 temperature points are required to differentiate; got {n}."
        )

    window = None
    if smoothing:
        window = int(sg_window)
        if window % 2 == 0:
            window += 1
        window = max(window, sg_polyorder + 3)   # +3 leaves one extra margin

        # savgol_filter requires an odd window strictly smaller than n.
        if window >= n:
            candidate = n - 1
            if candidate % 2 == 0:
                candidate -= 1                   # step down to the next odd value
            window = max(candidate, 1)

        window = max(window, 5)   # biological floor: 5 pts = 0.4 C at a 0.1 C step

        # max(window, 5) above can push the window back up to >= n on tiny inputs.
        if window >= n:
            raise RuntimeError(
                f"Too few data points ({n}) to apply Savitzky-Golay smoothing. "
                "Disable smoothing or use a file with more points."
            )
        if window <= sg_polyorder:
            raise RuntimeError(
                f"Smoothing window ({window}) is <= polyorder ({sg_polyorder}) after "
                "clamping. Lower the polynomial order or disable smoothing."
            )

    result = {"Temp": temp}

    for col in sample_cols:
        F = df[col].values.copy()

        if smoothing:
            try:
                F = savgol_filter(F, window_length=window, polyorder=sg_polyorder)
            except Exception as exc:
                raise RuntimeError(
                    f"Savitzky-Golay smoothing failed for column '{col}': {exc}. "
                    "Try a smaller window length, or disable smoothing."
                ) from exc

        deriv = np.zeros(n)

        # Interior: central difference, O(h^2)
        dt2 = temp[2:] - temp[:-2]
        safe = np.abs(dt2) > 1e-12
        deriv[1:-1] = np.where(
            safe, -(F[2:] - F[:-2]) / np.where(safe, dt2, 1.0), 0.0
        )

        # Forward stencil at i=0:  f'(x0) ~ (-3f0 + 4f1 - f2) / (2h)
        h0 = temp[1] - temp[0]
        deriv[0] = -(-3 * F[0] + 4 * F[1] - F[2]) / (2 * h0) if abs(h0) > 1e-12 else 0.0

        # Backward stencil at i=n-1:  f'(xN) ~ (3fN - 4f(N-1) + f(N-2)) / (2h)
        h_end = temp[n - 1] - temp[n - 2]
        deriv[n - 1] = (
            -(3 * F[n - 1] - 4 * F[n - 2] + F[n - 3]) / (2 * h_end)
            if abs(h_end) > 1e-12
            else 0.0
        )

        result[col] = deriv

    return pd.DataFrame(result)
