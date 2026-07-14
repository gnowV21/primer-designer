"""
difference.py — difference plot against a reference well [SPEC_Phase1 §4.2 step 3].

Ported from the existing hrm-tool project; algorithm unchanged, messages translated.

Each sample curve minus the reference curve (normally the positive control). A
genotype identical to the reference gives a flat line near zero; a variant departs
from zero across the melt transition.
"""

from typing import List, Tuple

import numpy as np
import pandas as pd


def _find_t50(temp: np.ndarray, F: np.ndarray, target: float) -> float | None:
    """
    Temperature at which F crosses `target`.

    Normalized HRM curves decrease monotonically in theory (1.0 -> 0.0), but real
    data has noise that creates small non-monotone bumps. np.interp requires a
    strictly increasing xp, so we first strip points where F fails to keep
    decreasing, then reverse. Returns None if the target lies outside the range.
    """
    F_min, F_max = float(np.nanmin(F)), float(np.nanmax(F))
    if not (F_min <= target <= F_max):
        return None

    keep = np.ones(len(F), dtype=bool)
    running_min = F[0]
    for i in range(1, len(F)):
        if F[i] < running_min:
            running_min = F[i]
        else:
            keep[i] = False

    F_mono = F[keep]
    T_mono = temp[keep]

    if len(F_mono) < 2:
        return None
    if not (float(np.min(F_mono)) <= target <= float(np.max(F_mono))):
        return None

    # F_mono strictly decreases -> reverse it so np.interp sees increasing xp.
    return float(np.interp(target, F_mono[::-1], T_mono[::-1]))


def compute_difference(
    df_norm: pd.DataFrame,
    ref_col: str,
    temp_shift: bool = False,
    shift_target: float = 0.5,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Difference plot: every sample minus `ref_col`.

    With temp_shift=True, each sample's temperature axis is first shifted so its
    F=shift_target crossing lines up with the reference's, then resampled back onto
    the original grid. This removes a pure Tm offset and isolates curve-SHAPE
    differences.

    Returns (df_diff, warnings).
    """
    sample_cols = [c for c in df_norm.columns if c != "Temp"]
    temp = df_norm["Temp"].values
    warnings: List[str] = []

    if ref_col not in sample_cols:
        raise ValueError(
            f"Reference column '{ref_col}' does not exist. "
            f"Available columns: {', '.join(sample_cols)}"
        )

    F_ref = df_norm[ref_col].values.copy()

    ref_t50 = None
    if temp_shift:
        ref_t50 = _find_t50(temp, F_ref, shift_target)
        if ref_t50 is None:
            warnings.append(
                f"Could not locate the F={shift_target} crossing in the reference "
                f"column '{ref_col}' (range: {F_ref.min():.2f}-{F_ref.max():.2f}). "
                "Temperature shifting was skipped."
            )
            temp_shift = False

    result = {"Temp": temp}
    result[ref_col] = np.zeros(len(temp))   # reference minus itself = 0

    for col in sample_cols:
        if col == ref_col:
            continue

        F_col = df_norm[col].values.copy()

        if temp_shift and ref_t50 is not None:
            col_t50 = _find_t50(temp, F_col, shift_target)

            if col_t50 is None:
                warnings.append(
                    f"Could not locate the F={shift_target} crossing in column '{col}' "
                    f"(range: {F_col.min():.2f}-{F_col.max():.2f}). "
                    "Shifting was skipped for this column."
                )
                F_shifted = F_col
            else:
                # delta > 0: col melts later than ref  -> shift col LEFT
                # delta < 0: col melts earlier than ref -> shift col RIGHT
                delta = col_t50 - ref_t50
                temp_shifted = temp - delta

                # np.interp clamps out-of-range values to the boundary (no NaN).
                F_shifted = np.interp(
                    temp, temp_shifted, F_col, left=F_col[0], right=F_col[-1]
                )
        else:
            F_shifted = F_col

        result[col] = F_shifted - F_ref

    return pd.DataFrame(result), warnings
