"""
auto_detect.py — pick T_pre / T_post automatically from the melt curve.

Ported from the existing hrm-tool project; algorithm unchanged.

Normalization needs two plateau temperatures. Asking the user to eyeball them from
a chart is exactly the sort of judgement call SPEC_Phase1 §0 wants the algorithm to
make, so we derive them from the shape of the transition and report a confidence.

Algorithm:
  1. Smooth the mean signal across wells (running mean) to suppress noise.
  2. Compute |dF/dT| (absolute local slope).
  3. Active melt zone = consecutive points where |slope| > 20% of the peak slope.
  4. T_pre  = left  edge of that zone, backed off by a 5-point stability buffer.
  5. T_post = right edge of that zone, advanced by the same buffer.
  6. Fall back to the 25th/75th temperature percentiles if the zone is degenerate.

Confidence comes from the SNR of the peak slope against the baseline slope.
"""

import numpy as np
import pandas as pd

# Points of margin between the detected melt zone and the baseline fit windows.
_BUFFER = 5

# bilinear_normalize needs >= 3 points in each baseline window.
_MIN_BASELINE_PTS = 3

# A point is "melting" once its slope exceeds this fraction of the peak slope.
_ONSET_FRACTION = 0.20


def auto_detect_temps(df: pd.DataFrame) -> dict:
    """Returns {T_pre, T_post, confidence} with confidence in {high, medium, low}."""
    sample_cols = [c for c in df.columns if c != "Temp"]
    temp = df["Temp"].values
    n = len(temp)

    mean_signal = df[sample_cols].mean(axis=1).values

    # 1. Smooth
    smooth_win = min(11, max(3, n // 20))
    smoothed = _running_mean(mean_signal, smooth_win)

    # 2. |dF/dT| via central differences
    abs_slope = np.zeros(n)
    for i in range(1, n - 1):
        dt = temp[i + 1] - temp[i - 1]
        abs_slope[i] = (
            abs(smoothed[i + 1] - smoothed[i - 1]) / dt if abs(dt) > 1e-12 else 0.0
        )
    abs_slope[0] = abs_slope[1]
    abs_slope[n - 1] = abs_slope[n - 2]

    peak_slope = float(np.max(abs_slope))

    # 3. Active melt zone
    in_melt = abs_slope >= _ONSET_FRACTION * peak_slope
    if not np.any(in_melt):
        return _quartile_fallback(temp, confidence="low")   # curve is entirely flat

    melt_indices = np.where(in_melt)[0]
    left_edge = int(melt_indices[0])
    right_edge = int(melt_indices[-1])

    # 4/5. Back off from each edge, but keep >= 3 points in each baseline window.
    pre_idx = max(0, left_edge - _BUFFER)
    post_idx = min(n - 1, right_edge + _BUFFER)

    while pre_idx < left_edge and (pre_idx + 1) < _MIN_BASELINE_PTS:
        pre_idx += 1
    while post_idx > right_edge and (n - post_idx) < _MIN_BASELINE_PTS:
        post_idx -= 1

    T_pre_raw = float(temp[pre_idx])
    T_post_raw = float(temp[post_idx])

    # Confidence: peak slope vs the noise floor of the slope.
    baseline_slope = float(np.percentile(abs_slope, 10))
    snr = peak_slope / (baseline_slope + 1e-9)
    if snr > 20:
        confidence = "high"
    elif snr > 5:
        confidence = "medium"
    else:
        confidence = "low"

    # 6. A transition narrower than 5 C means detection failed.
    if T_pre_raw >= T_post_raw - 5:
        return _quartile_fallback(temp, confidence="low")

    return {
        "T_pre":      round(T_pre_raw, 2),
        "T_post":     round(T_post_raw, 2),
        "confidence": confidence,
    }


def _quartile_fallback(temp: np.ndarray, confidence: str) -> dict:
    return {
        "T_pre":      round(float(np.percentile(temp, 25)), 2),
        "T_post":     round(float(np.percentile(temp, 75)), 2),
        "confidence": confidence,
    }


def _running_mean(x: np.ndarray, w: int) -> np.ndarray:
    pad = w // 2
    padded = np.pad(x, pad, mode="edge")
    return np.convolve(padded, np.ones(w) / w, mode="valid")[: len(x)]
