"""
features.py — turn melt curves into the NUMERIC TABLE the LLM is allowed to read
[SPEC_Phase1 §4.2 step 4, §4.3].

This module is the boundary enforced by SPEC_Phase1 §0: *the algorithm measures,
the LLM only explains*. Every number the chatbot may quote about an HRM run is
produced HERE, in Python. The LLM never sees a curve, never sees an image, and is
never asked to compute anything.

Per sample well we extract:
    Tm               peak of -dF/dT  (the melting temperature)
    num_peaks        how many real peaks the derivative has
    peak_height      height of the dominant peak
    fwhm             full width at half maximum of the dominant peak
    delta_Tm_vs_pos  Tm minus the positive control's Tm
    flag             match | shifted | suspect | noise

CONSTANT SOURCES
----------------
Tm is read off the -dF/dT peak, the standard instrument definition:
  Ririe KM, Rasmussen RP, Wittwer CT. "Product differentiation by analysis of DNA
  melting curves during the polymerase chain reaction." Anal Biochem.
  1997;245(2):154-160. doi:10.1006/abio.1996.9916
  -> a single sharp peak indicates one specific product; extra peaks indicate
     non-specific product or primer-dimer.

Run-to-run Tm reproducibility on HRM instruments has SD ~0.1 C:
  Herrmann MG, Durtschi JD, Bromley LK, Wittwer CT, Voelkerding KV. "Amplicon DNA
  melting analysis for mutation scanning and genotyping: cross-platform comparison
  of instruments and dyes." Clin Chem. 2006;52(3):494-503.
  doi:10.1373/clinchem.2005.063438
  -> TM_MATCH_TOLERANCE_C below is 3 x that SD.
"""

from typing import Optional

import numpy as np
import pandas as pd
from scipy.signal import find_peaks, peak_widths

# A Tm within 3 x the ~0.1 C inter-run SD [Herrmann 2006, doi:10.1373/clinchem.2005.063438]
# is indistinguishable from the control, i.e. the same product.
TM_MATCH_TOLERANCE_C = 0.3

# HEURISTIC (no single literature value — melt-peak noise depends on dye, instrument
# and input mass). A local maximum shorter than 10% of the dominant peak is treated
# as noise rather than a second product; without this, smoothing ripple would be
# counted as extra peaks and every well would be flagged "suspect".
MIN_PEAK_PROMINENCE_FRAC = 0.10

# HEURISTIC. A well whose dominant peak is under 15% of the positive control's peak
# has essentially not amplified — its Tm is meaningless and must not be interpreted.
NOISE_PEAK_HEIGHT_FRAC = 0.15

# HEURISTIC. A dominant peak more than 2x broader than the control's suggests a
# heterogeneous melting population (mixed products, heteroduplex) rather than one
# clean amplicon [shape rationale per Ririe 1997].
FWHM_BROAD_FACTOR = 2.0

# Column names (case-insensitive) recognised as the controls in the uploaded file
# [SPEC_Phase1 §4.1 example header].
_POSITIVE_ALIASES = ("positive_ctrl", "positive", "pos_ctrl", "pos", "positive_control")
_NEGATIVE_ALIASES = ("negative_ctrl", "negative", "neg_ctrl", "neg", "negative_control",
                     "ntc", "blank")


def find_control_column(columns: list[str], aliases: tuple) -> Optional[str]:
    """Match a control column by name, case-insensitively."""
    lowered = {c.lower().strip(): c for c in columns}
    for alias in aliases:
        if alias in lowered:
            return lowered[alias]
    return None


def _peak_features(temp: np.ndarray, deriv: np.ndarray) -> dict:
    """
    Peak statistics of one -dF/dT curve.

    Returns Tm/num_peaks/peak_height/fwhm/all_peaks, all None (all_peaks empty) when the
    curve has no peak at all (a flat, non-amplifying well).

    `all_peaks` lists EVERY detected peak as {Tm, height}, hottest-first — not just the
    dominant one. It exists because "what is the second peak?" is the most common question
    a two-peak well provokes, and reporting only the dominant peak left the model with no
    data to answer it: it would grab the dominant peak's Tm and FWHM and misattribute them
    to the secondary peak. Giving it the real numbers is the only honest fix — the
    alternative is a model guessing about a peak it cannot see.
    """
    max_signal = float(np.max(deriv))

    empty = {"Tm": None, "num_peaks": 0, "peak_height": None, "fwhm": None, "all_peaks": []}

    # A curve that never rises above zero has no melt transition.
    if max_signal <= 0:
        return empty

    # Prominence (not raw height) is what separates a real second product from a
    # ripple sitting on the flank of the main peak.
    prominence = MIN_PEAK_PROMINENCE_FRAC * max_signal
    peaks, _ = find_peaks(deriv, prominence=prominence)

    if len(peaks) == 0:
        return empty

    # The dominant peak defines Tm; the rest are reported alongside it.
    dominant = int(peaks[int(np.argmax(deriv[peaks]))])

    # peak_widths returns the width in SAMPLE INDICES, at half prominence
    # (rel_height=0.5). Convert to degrees C via the local temperature step.
    _, _, left_ips, right_ips = peak_widths(deriv, [dominant], rel_height=0.5)
    left_t  = float(np.interp(left_ips[0],  np.arange(len(temp)), temp))
    right_t = float(np.interp(right_ips[0], np.arange(len(temp)), temp))
    fwhm    = abs(right_t - left_t)

    all_peaks = sorted(
        (
            {"Tm": round(float(temp[i]), 2), "height": round(float(deriv[i]), 4)}
            for i in peaks
        ),
        key=lambda p: p["height"],
        reverse=True,
    )

    return {
        "Tm":          round(float(temp[dominant]), 2),
        "num_peaks":   int(len(peaks)),
        "peak_height": round(float(deriv[dominant]), 4),
        "fwhm":        round(fwhm, 2),
        "all_peaks":   all_peaks,
    }


def _classify(f: dict, pos: Optional[dict]) -> tuple[str, str]:
    """
    Assign the preliminary flag [SPEC_Phase1 §4.2: match / shifted / suspect / noise].

    Returns (flag, one-line English reason). The reason is passed to the LLM so its
    explanation is anchored to the rule that actually fired, not re-derived.

    Order is deliberate: a well that did not amplify ("noise") must be caught before
    its meaningless Tm is compared against anything.
    """
    if f["Tm"] is None:
        return "noise", "No melt peak detected — the well did not amplify."

    if pos and pos.get("peak_height"):
        if f["peak_height"] < NOISE_PEAK_HEIGHT_FRAC * pos["peak_height"]:
            return "noise", (
                f"Peak height {f['peak_height']} is below "
                f"{int(NOISE_PEAK_HEIGHT_FRAC * 100)}% of the positive control "
                f"({pos['peak_height']}) — amplification is too weak to interpret."
            )

    if f["num_peaks"] >= 2:
        return "suspect", (
            f"{f['num_peaks']} melt peaks detected — non-specific product or "
            "primer-dimer [Ririe 1997]."
        )

    if pos and pos.get("fwhm") and f["fwhm"] is not None:
        if f["fwhm"] > FWHM_BROAD_FACTOR * pos["fwhm"]:
            return "suspect", (
                f"Peak width {f['fwhm']} C is more than {FWHM_BROAD_FACTOR}x the "
                f"positive control ({pos['fwhm']} C) — heterogeneous melting."
            )

    delta = f.get("delta_Tm_vs_pos")
    if delta is not None:
        if abs(delta) > TM_MATCH_TOLERANCE_C:
            return "shifted", (
                f"Tm differs from the positive control by {delta:+.2f} C, beyond the "
                f"{TM_MATCH_TOLERANCE_C} C reproducibility window — likely a sequence "
                "variant or a different product."
            )
        return "match", (
            f"Single peak, Tm within {TM_MATCH_TOLERANCE_C} C of the positive control "
            f"({delta:+.2f} C)."
        )

    # No positive control in the file: we can still report a clean single peak, but
    # "match" would be a claim we have nothing to match AGAINST.
    return "match", "Single clean melt peak (no positive control supplied to compare against)."


def extract_features(
    df_raw: pd.DataFrame,
    df_deriv: pd.DataFrame,
    positive_col: Optional[str] = None,
) -> dict:
    """
    Build the numeric table of SPEC_Phase1 §4.3 — the ONLY HRM input the LLM sees.

    Args:
        df_raw:   cleaned raw fluorescence (used only to list the sample columns)
        df_deriv: -dF/dT from derivative.compute_derivative(df_raw)
        positive_col: name of the positive control; auto-detected when omitted.

    Returns:
        {
          "features": {sample: {Tm, num_peaks, peak_height, fwhm,
                                delta_Tm_vs_pos, flag, reason}},
          "positive_control": str | None,
          "negative_control": str | None,
        }
    """
    sample_cols = [c for c in df_deriv.columns if c != "Temp"]
    temp = df_deriv["Temp"].values

    if positive_col is None:
        positive_col = find_control_column(sample_cols, _POSITIVE_ALIASES)
    elif positive_col not in sample_cols:
        raise ValueError(
            f"Positive control column '{positive_col}' does not exist. "
            f"Available columns: {', '.join(sample_cols)}"
        )
    negative_col = find_control_column(sample_cols, _NEGATIVE_ALIASES)

    # Pass 1 — raw peak statistics for every well, including the control itself.
    raw_features = {
        col: _peak_features(temp, df_deriv[col].values) for col in sample_cols
    }

    pos = raw_features.get(positive_col) if positive_col else None

    # Pass 2 — delta vs the control, then classify. Needs pass 1 complete, because
    # every well is compared against the control's Tm/height/width.
    features = {}
    for col in sample_cols:
        f = dict(raw_features[col])

        if pos and pos["Tm"] is not None and f["Tm"] is not None:
            f["delta_Tm_vs_pos"] = round(f["Tm"] - pos["Tm"], 2)
        else:
            f["delta_Tm_vs_pos"] = None

        flag, reason = _classify(f, pos)
        f["flag"] = flag
        f["reason"] = reason

        # A well that did not amplify still produces peak statistics — find_peaks on
        # pure noise happily returns dozens of "peaks" and a Tm somewhere in the
        # middle of the ramp. Those numbers are artefacts of the noise floor, not
        # measurements, and this table is the ONLY thing the LLM may quote [§0, §4.3].
        # Leaving them in is how the assistant ends up asserting that the no-template
        # control melted at 73.8 C. Blank them: "no measurement" is the honest value.
        if flag == "noise":
            for key in ("Tm", "num_peaks", "peak_height", "fwhm", "delta_Tm_vs_pos"):
                f[key] = None
            f["all_peaks"] = []

        features[col] = f

    # The positive control is the yardstick — comparing it to itself is meaningless.
    if positive_col and positive_col in features:
        features[positive_col]["flag"] = "control"
        features[positive_col]["reason"] = "Positive control — the reference for every other well."

    if negative_col and negative_col in features:
        neg = features[negative_col]
        # An NTC that produces a peak means contamination or primer-dimer, which
        # invalidates the whole plate — the single most important thing to surface.
        if neg["Tm"] is not None and neg["flag"] != "noise":
            neg["flag"] = "suspect"
            neg["reason"] = (
                f"Negative control shows a melt peak at {neg['Tm']} C — "
                "contamination or primer-dimer; results on this plate are unreliable."
            )
        else:
            neg["flag"] = "control"
            neg["reason"] = "Negative control — no melt peak, as expected."

    return {
        "features":         features,
        "positive_control": positive_col,
        "negative_control": negative_col,
    }
