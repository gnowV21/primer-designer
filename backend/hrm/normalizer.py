"""
normalizer.py — bilinear normalization of the HRM fluorescence signal
[SPEC_Phase1 §4.2 step 1].

Ported unchanged (algorithm-wise) from the existing hrm-tool project; only the
user-facing messages were translated to English per the SPEC_Phase1 UI-language rule.

BIOLOGY
-------
HRM dyes (EvaGreen / LCGreen / SYTO-9) fluoresce ONLY when bound to dsDNA. As the
plate heats:

  * pre-melt  (around T_pre) : DNA still double-stranded, dye fully bound
                              -> fluorescence is at its MAXIMUM -> normalize to 1.0
  * melting   (T_pre..T_post): strands separate, dye is released
                              -> F_norm between 0 and 1 = fraction of dsDNA left
  * post-melt (around T_post): fully single-stranded, only background remains
                              -> normalize to 0.0

ALGORITHM (window of +/- MARGIN around each boundary)
----------------------------------------------------
  1. Two fit windows:  [T_pre +/- MARGIN] and [T_post +/- MARGIN], clamped to the
     data range. Each needs >= 3 points for a stable line fit.
  2. Fit a straight baseline in each window:
         L_pre(T)  = a_pre  * T + b_pre     (the "dye-saturated" dsDNA baseline)
         L_post(T) = a_post * T + b_post    (the ssDNA background baseline)
  3. Normalize across the whole temperature range:
         F_norm(T) = (F_raw(T) - L_post(T)) / (L_pre(T) - L_post(T))
     numerator   = distance from the signal down to the background baseline
     denominator = total amplitude between "saturated" and "background"
     result      = fraction of dsDNA remaining at temperature T
  4. Clip to [-0.05, 1.05] — tolerates noise, rejects extreme outliers.
     Scale stays 0.0-1.0 (NOT multiplied by 100).

Caveat: T_pre / T_post must sit in the flat plateau regions. Placed too close to
the melt transition, the +/- MARGIN window bleeds into the melting zone, the
baseline slope comes out wrong, and F_norm can spike above 1.0.
"""

from typing import List, Tuple

import numpy as np
import pandas as pd

# Half-width of the baseline fit window around each boundary point (deg C per side).
MARGIN = 2.0


def bilinear_normalize(
    df: pd.DataFrame, T_pre: float, T_post: float
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Returns (normalized DataFrame with a 'Temp' column, list of warnings).

    Raises ValueError when T_pre >= T_post, when either baseline window has fewer
    than 3 points, or when every well is flat (failed PCR).
    """
    if T_pre >= T_post:
        raise ValueError(
            f"T_pre ({T_pre} C) must be lower than T_post ({T_post} C). "
            "Check the order of the two values."
        )

    sample_cols = [c for c in df.columns if c != "Temp"]
    temp = df["Temp"].values
    t_min, t_max = float(temp[0]), float(temp[-1])

    # Fit windows of +/- MARGIN around each boundary, clamped to the data range.
    pre_lo = max(t_min, T_pre - MARGIN)
    pre_hi = min(t_max, T_pre + MARGIN)
    post_lo = max(t_min, T_post - MARGIN)
    post_hi = min(t_max, T_post + MARGIN)

    pre_mask = (temp >= pre_lo) & (temp <= pre_hi)
    post_mask = (temp >= post_lo) & (temp <= post_hi)

    n_pre = int(pre_mask.sum())
    n_post = int(post_mask.sum())

    if n_pre < 3:
        raise ValueError(
            f"The pre-melt window ({pre_lo:.1f} C - {pre_hi:.1f} C) has only {n_pre} "
            "point(s); at least 3 are required. Adjust T_pre or check the temperature "
            "range of the data."
        )
    if n_post < 3:
        raise ValueError(
            f"The post-melt window ({post_lo:.1f} C - {post_hi:.1f} C) has only {n_post} "
            "point(s); at least 3 are required. Adjust T_post or check the temperature "
            "range of the data."
        )

    result: dict = {"Temp": temp}
    warnings: List[str] = []
    flat_wells: List[str] = []

    for col in sample_cols:
        F = df[col].values

        # Fit the dsDNA-saturated (pre-melt) and ssDNA-background (post-melt) baselines.
        coef_pre = np.polyfit(temp[pre_mask], F[pre_mask], 1)
        L_pre = np.polyval(coef_pre, temp)

        coef_post = np.polyfit(temp[post_mask], F[post_mask], 1)
        L_post = np.polyval(coef_post, temp)

        denom = L_pre - L_post

        # Flat-well detection: signal amplitude below 1% of the measured range.
        signal_range = float(np.ptp(F))
        flat_threshold = max(1e-6, 0.01 * signal_range)
        denom_range = float(np.max(np.abs(denom)))
        if denom_range < flat_threshold:
            flat_wells.append(col)
            continue

        # Preserve the sign when the denominator approaches zero, so F_norm cannot flip.
        denom_safe = np.where(
            np.abs(denom) < 1e-12, np.copysign(1e-12, denom), denom
        )

        F_norm = (F - L_post) / denom_safe
        F_norm = np.clip(F_norm, -0.05, 1.05)
        result[col] = F_norm

    if flat_wells:
        warnings.append(
            f"Flat signal in these columns (failed wells?): {', '.join(flat_wells)}. "
            "They were excluded from the result."
        )

    if len(result) <= 1:   # only the 'Temp' column survived
        raise ValueError(
            "Every sample column has a flat signal. Check the data, or pick "
            "different T_pre / T_post values."
        )

    return pd.DataFrame(result), warnings


def to_response(df_norm: pd.DataFrame) -> dict:
    """Convert the normalized DataFrame into a JSON-serializable dict."""
    sample_cols = [c for c in df_norm.columns if c != "Temp"]
    return {
        "temp":       df_norm["Temp"].tolist(),
        "normalized": {col: df_norm[col].tolist() for col in sample_cols},
    }
