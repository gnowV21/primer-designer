"""
test_hrm_features.py — validate the HRM pipeline against synthetic curves whose
true Tm is known by construction [SPEC_Phase1 §4.4].

SPEC_Phase1 §4.4 calls for the `hrm-algorithm-validator` skill; that skill does not
exist in this repo, so the same requirement — "unit-test normalize/derivative/
difference with synthetic data before trusting the result" — is met with pytest.

The point of a synthetic curve is that we KNOW the answer. A sigmoid melt curve
    F(T) = base + amp / (1 + exp((T - Tm) / k))
has its steepest descent exactly at T = Tm, so -dF/dT must peak there. If the
pipeline cannot recover a Tm it was handed, no number it produces can be trusted.
"""

import io

import numpy as np
import pandas as pd
import pytest

from hrm import auto_detect, derivative, difference, features, loader, normalizer

TEMP_MIN, TEMP_MAX, TEMP_STEP = 65.0, 95.0, 0.1


def melt_curve(tm: float, amp: float = 1.0, k: float = 0.6,
               base: float = 0.05, noise: float = 0.0,
               seed: int = 0) -> np.ndarray:
    """One sigmoid melt curve with its transition centred on `tm`."""
    temp = temp_axis()
    F = base + amp / (1.0 + np.exp((temp - tm) / k))
    if noise:
        F = F + np.random.default_rng(seed).normal(0, noise, len(temp))
    return F


def temp_axis() -> np.ndarray:
    return np.arange(TEMP_MIN, TEMP_MAX + TEMP_STEP / 2, TEMP_STEP)


def frame(**cols) -> pd.DataFrame:
    return pd.DataFrame({"Temp": temp_axis(), **cols})


# ── derivative: does -dF/dT peak at the true Tm? ────────────────────────────

@pytest.mark.parametrize("true_tm", [72.0, 79.4, 85.5])
def test_derivative_peak_recovers_true_tm(true_tm):
    df = frame(sample_1=melt_curve(true_tm))
    deriv = derivative.compute_derivative(df, smoothing=True)

    peak_temp = deriv["Temp"].values[int(np.argmax(deriv["sample_1"].values))]

    # Tolerance is one temperature step: the peak can only be located on the grid.
    assert abs(peak_temp - true_tm) <= TEMP_STEP, (
        f"Recovered Tm {peak_temp} differs from the true Tm {true_tm}"
    )


def test_derivative_peak_survives_noise():
    """Savitzky-Golay smoothing must hold the peak in place under realistic noise."""
    df = frame(sample_1=melt_curve(79.4, noise=0.01, seed=42))
    deriv = derivative.compute_derivative(df, smoothing=True)

    peak_temp = deriv["Temp"].values[int(np.argmax(deriv["sample_1"].values))]
    assert abs(peak_temp - 79.4) <= 0.3


def test_derivative_is_positive_at_the_melt():
    """Fluorescence FALLS as DNA melts, so -dF/dT must be POSITIVE at the transition."""
    df = frame(sample_1=melt_curve(79.4))
    deriv = derivative.compute_derivative(df, smoothing=True)
    assert deriv["sample_1"].max() > 0


# ── normalizer: bilinear normalization ─────────────────────────────────────

def test_normalize_spans_zero_to_one():
    df = frame(sample_1=melt_curve(79.4))
    df_norm, warnings = normalizer.bilinear_normalize(df, T_pre=68.0, T_post=92.0)

    F = df_norm["sample_1"].values
    assert F[0] == pytest.approx(1.0, abs=0.05), "pre-melt plateau must normalize to ~1.0"
    assert F[-1] == pytest.approx(0.0, abs=0.05), "post-melt plateau must normalize to ~0.0"
    assert F.min() >= -0.05 and F.max() <= 1.05, "values must stay inside the clip band"
    assert warnings == []


def test_normalize_is_monotonically_decreasing():
    """A clean single-transition curve must fall from 1 to 0 without going back up."""
    df = frame(sample_1=melt_curve(79.4))
    df_norm, _ = normalizer.bilinear_normalize(df, T_pre=68.0, T_post=92.0)

    F = df_norm["sample_1"].values
    assert np.all(np.diff(F) <= 1e-6)


def test_normalize_rejects_swapped_boundaries():
    df = frame(sample_1=melt_curve(79.4))
    with pytest.raises(ValueError, match="must be lower than"):
        normalizer.bilinear_normalize(df, T_pre=92.0, T_post=68.0)


def test_normalize_drops_flat_wells_and_warns():
    df = frame(
        sample_1=melt_curve(79.4),
        dead_well=np.full(len(temp_axis()), 0.5),   # never amplified
    )
    df_norm, warnings = normalizer.bilinear_normalize(df, T_pre=68.0, T_post=92.0)

    assert "dead_well" not in df_norm.columns
    assert any("dead_well" in w for w in warnings)


def test_normalize_raises_when_every_well_is_flat():
    flat = np.full(len(temp_axis()), 0.5)
    df = frame(a=flat, b=flat)
    with pytest.raises(ValueError, match="flat signal"):
        normalizer.bilinear_normalize(df, T_pre=68.0, T_post=92.0)


# ── difference: sample minus reference ─────────────────────────────────────

def test_difference_of_reference_with_itself_is_zero():
    df = frame(positive_ctrl=melt_curve(79.4), sample_1=melt_curve(79.4))
    df_norm, _ = normalizer.bilinear_normalize(df, T_pre=68.0, T_post=92.0)
    df_diff, _ = difference.compute_difference(df_norm, ref_col="positive_ctrl")

    assert np.allclose(df_diff["positive_ctrl"].values, 0.0)


def test_difference_is_near_zero_for_an_identical_sample():
    df = frame(positive_ctrl=melt_curve(79.4), sample_1=melt_curve(79.4))
    df_norm, _ = normalizer.bilinear_normalize(df, T_pre=68.0, T_post=92.0)
    df_diff, _ = difference.compute_difference(df_norm, ref_col="positive_ctrl")

    assert np.abs(df_diff["sample_1"].values).max() < 0.01


def test_difference_is_large_for_a_shifted_sample():
    """A 3 C Tm shift must show up as a clear departure from the reference."""
    df = frame(positive_ctrl=melt_curve(79.4), sample_1=melt_curve(76.4))
    df_norm, _ = normalizer.bilinear_normalize(df, T_pre=68.0, T_post=92.0)
    df_diff, _ = difference.compute_difference(df_norm, ref_col="positive_ctrl")

    assert np.abs(df_diff["sample_1"].values).max() > 0.3


def test_difference_rejects_unknown_reference():
    df = frame(sample_1=melt_curve(79.4))
    df_norm, _ = normalizer.bilinear_normalize(df, T_pre=68.0, T_post=92.0)
    with pytest.raises(ValueError, match="does not exist"):
        difference.compute_difference(df_norm, ref_col="nope")


# ── auto_detect ────────────────────────────────────────────────────────────

def test_auto_detect_brackets_the_melt_transition():
    df = frame(sample_1=melt_curve(79.4))
    d = auto_detect.auto_detect_temps(df)

    assert d["T_pre"] < 79.4 < d["T_post"], "the detected window must contain the Tm"
    assert d["confidence"] in ("high", "medium", "low")


def test_auto_detected_temps_feed_normalize_without_raising():
    """The two must compose: auto_detect's output has to be usable by normalize."""
    df = frame(sample_1=melt_curve(79.4))
    d = auto_detect.auto_detect_temps(df)

    df_norm, _ = normalizer.bilinear_normalize(df, d["T_pre"], d["T_post"])
    assert "sample_1" in df_norm.columns


# ── features: the numeric table handed to the LLM ──────────────────────────

def test_features_recover_tm_and_flag_a_matching_sample():
    df = frame(positive_ctrl=melt_curve(79.4), sample_1=melt_curve(79.4))
    deriv = derivative.compute_derivative(df, smoothing=True)
    out = features.extract_features(df, deriv)

    assert out["positive_control"] == "positive_ctrl"

    s1 = out["features"]["sample_1"]
    assert s1["Tm"] == pytest.approx(79.4, abs=0.15)
    assert s1["num_peaks"] == 1
    assert s1["delta_Tm_vs_pos"] == pytest.approx(0.0, abs=0.1)
    assert s1["flag"] == "match"

    assert out["features"]["positive_ctrl"]["flag"] == "control"


def test_features_flag_a_shifted_sample():
    """3 C below the control is far outside the 0.3 C reproducibility window."""
    df = frame(positive_ctrl=melt_curve(79.4), sample_1=melt_curve(76.4))
    deriv = derivative.compute_derivative(df, smoothing=True)
    out = features.extract_features(df, deriv)

    s1 = out["features"]["sample_1"]
    assert s1["delta_Tm_vs_pos"] == pytest.approx(-3.0, abs=0.15)
    assert s1["flag"] == "shifted"


def test_features_flag_two_peaks_as_suspect():
    """Two products (e.g. amplicon + primer-dimer) must never be called a match."""
    two_product = melt_curve(79.4, amp=0.6) + melt_curve(72.0, amp=0.4, base=0.0)
    df = frame(positive_ctrl=melt_curve(79.4), sample_1=two_product)

    deriv = derivative.compute_derivative(df, smoothing=True)
    out = features.extract_features(df, deriv)

    s1 = out["features"]["sample_1"]
    assert s1["num_peaks"] >= 2
    assert s1["flag"] == "suspect"


def test_features_flag_a_dead_well_as_noise():
    df = frame(
        positive_ctrl=melt_curve(79.4),
        sample_1=np.full(len(temp_axis()), 0.5),   # flat: no amplification
    )
    deriv = derivative.compute_derivative(df, smoothing=True)
    out = features.extract_features(df, deriv)

    assert out["features"]["sample_1"]["flag"] == "noise"


def test_a_noise_well_reports_no_numbers_at_all():
    """
    Regression: a non-amplifying well is not silent, it is NOISY. find_peaks on the
    noise floor returns dozens of "peaks" and a Tm partway up the ramp. This table is
    the only source the LLM may quote, so those artefacts must never reach it —
    otherwise the assistant will state that the no-template control melted.
    """
    rng = np.random.default_rng(3)
    noise = 0.05 + rng.normal(0, 0.003, len(temp_axis()))

    df = frame(positive_ctrl=melt_curve(79.4), negative_ctrl=noise)
    deriv = derivative.compute_derivative(df, smoothing=True)
    out = features.extract_features(df, deriv)

    neg = out["features"]["negative_ctrl"]
    assert neg["flag"] == "control"          # an empty NTC is expected, not suspect
    for key in ("Tm", "num_peaks", "peak_height", "fwhm", "delta_Tm_vs_pos"):
        assert neg[key] is None, f"{key} must be blank for a well that never amplified"


def test_features_flag_a_contaminated_ntc():
    """An NTC with a real melt peak invalidates the plate — it must be surfaced."""
    df = frame(
        positive_ctrl=melt_curve(79.4),
        negative_ctrl=melt_curve(79.4),   # should have been flat
    )
    deriv = derivative.compute_derivative(df, smoothing=True)
    out = features.extract_features(df, deriv)

    neg = out["features"]["negative_ctrl"]
    assert neg["flag"] == "suspect"
    assert "contamination" in neg["reason"].lower()


def test_features_work_without_a_positive_control():
    df = frame(sample_1=melt_curve(79.4))
    deriv = derivative.compute_derivative(df, smoothing=True)
    out = features.extract_features(df, deriv)

    assert out["positive_control"] is None
    assert out["features"]["sample_1"]["delta_Tm_vs_pos"] is None
    assert out["features"]["sample_1"]["Tm"] == pytest.approx(79.4, abs=0.15)


# ── loader ─────────────────────────────────────────────────────────────────

def test_loader_reads_csv_with_metadata_rows_above_the_header():
    """Instrument exports routinely carry title rows above the real header."""
    temp = temp_axis()
    F = melt_curve(79.4)

    lines = ["Experiment: SNP4 run,,", "Exported 2026-07-11,,", "Temp,positive_ctrl,sample_1"]
    lines += [f"{t:.1f},{f:.5f},{f:.5f}" for t, f in zip(temp, F)]

    buf = io.BytesIO("\n".join(lines).encode("utf-8"))
    buf.name = "run.csv"

    df = loader.load_melt_file(buf)

    assert list(df.columns) == ["Temp", "positive_ctrl", "sample_1"]
    assert len(df) == len(temp)
    assert df["Temp"].is_monotonic_increasing


def test_loader_reads_a_ragged_export():
    """
    Regression: real instrument exports are RAGGED — the title rows carry fewer
    fields than the data rows below them. pandas infers the column count from line 1
    and then dies with "Expected 1 fields, saw 6" on the first data row.
    """
    temp = temp_axis()
    F = melt_curve(79.4)

    lines = [
        "Melt Curve Export",           # 1 field  — no separator at all
        "Run SNP4,21-05-2026",         # 2 fields
        "Temp,positive_ctrl,sample_1",  # 3 fields — the real header
    ]
    lines += [f"{t:.1f},{f:.5f},{f:.5f}" for t, f in zip(temp, F)]

    buf = io.BytesIO("\n".join(lines).encode("utf-8"))
    buf.name = "ragged.csv"

    df = loader.load_melt_file(buf)

    assert list(df.columns) == ["Temp", "positive_ctrl", "sample_1"]
    assert len(df) == len(temp)


def test_loader_reads_a_tab_separated_export():
    temp = temp_axis()
    F = melt_curve(79.4)

    lines = ["Temp\tsample_1"] + [f"{t:.1f}\t{f:.5f}" for t, f in zip(temp, F)]
    buf = io.BytesIO("\n".join(lines).encode("utf-8"))
    buf.name = "run.tsv"

    df = loader.load_melt_file(buf)
    assert list(df.columns) == ["Temp", "sample_1"]


def test_loader_rejects_a_file_with_too_few_rows():
    buf = io.BytesIO(b"Temp,sample_1\n65.0,1.0\n65.1,0.9\n")
    buf.name = "tiny.csv"

    with pytest.raises(ValueError, match="Too little data"):
        loader.load_melt_file(buf)
