"""PART C tests — melting curve (SPEC §C.4, §F PART C)."""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from visualization.melting import simulate_melting, _R, _KELVIN   # noqa: E402
from visualization.renderer import render_melting                 # noqa: E402
from visualization.constants import VIZ_SIMULATED_LABEL           # noqa: E402

_AMP = "GGCGTAGCAGCACGTAAATATTGGCGGTCGTATCCAGTGCGAATACCTCGGACCCTGCACTGG"  # 63 bp
_DH = 500000.0   # cal/mol, provided → deterministic


def _fwhm(temps, ys):
    hm = max(ys) / 2.0
    above = [t for t, v in zip(temps, ys) if v >= hm]
    return max(above) - min(above)


def test_theta_is_half_at_tm():
    tm = 79.4
    m = simulate_melting(_AMP, tm, dh_cal_per_mol=_DH)
    idx = m.temperatures.index(round(tm, 1))
    assert abs(m.f_norm[idx] - 0.5) < 1e-9


def test_fnorm_monotonic_decreasing():
    m = simulate_melting(_AMP, 79.4, dh_cal_per_mol=_DH)
    for a, b in zip(m.f_norm, m.f_norm[1:]):
        assert b <= a + 1e-12


def test_derivative_peak_at_tm():
    tm = 78.0
    m = simulate_melting(_AMP, tm, dh_cal_per_mol=_DH)
    peak_t = m.temperatures[m.neg_dfdt.index(max(m.neg_dfdt))]
    assert abs(peak_t - tm) <= 0.05


def test_peak_height_matches_analytic():
    tm = 80.0
    m = simulate_melting(_AMP, tm, dh_cal_per_mol=_DH)
    expected = _DH / (4.0 * _R * (tm + _KELVIN) ** 2)
    assert abs(m.peak_height - expected) / expected < 1e-6
    assert abs(max(m.neg_dfdt) - m.peak_height) / m.peak_height < 1e-3


def test_larger_dh_gives_higher_and_narrower_peak():
    lo = simulate_melting(_AMP, 80.0, dh_cal_per_mol=300000.0)
    hi = simulate_melting(_AMP, 80.0, dh_cal_per_mol=600000.0)
    assert hi.peak_height > lo.peak_height                     # higher
    assert _fwhm(hi.temperatures, hi.neg_dfdt) < _fwhm(lo.temperatures, lo.neg_dfdt)  # narrower


def test_fallback_branch_sets_approximate_source():
    long_amp = "AT" * 40   # 80 bp > 60 → primer3 NN unavailable → fallback
    m = simulate_melting(long_amp, 78.0, params={})
    assert m.dh_source == "approximate"


def test_nn_branch_for_short_amplicon():
    short = "GCGCGCGCGCGCGCGCGCGCGCGCGCGCGC"  # 30 bp ≤ 60 → NN available
    m = simulate_melting(short, 78.0, params={})
    assert m.dh_source == "nearest_neighbor"


def test_provided_dh_source():
    m = simulate_melting(_AMP, 79.4, dh_cal_per_mol=_DH)
    assert m.dh_source == "provided"


def test_determinism():
    a = simulate_melting(_AMP, 79.4, dh_cal_per_mol=_DH)
    b = simulate_melting(_AMP, 79.4, dh_cal_per_mol=_DH)
    assert a.temperatures == b.temperatures
    assert a.f_norm == b.f_norm
    assert a.neg_dfdt == b.neg_dfdt


def test_grid_is_351_points():
    m = simulate_melting(_AMP, 79.4, dh_cal_per_mol=_DH)
    assert len(m.temperatures) == 351
    assert m.temperatures[0] == 60.0 and m.temperatures[-1] == 95.0


# ── render_melting ───────────────────────────────────────────────────────────────

def test_render_wellformed_and_labels():
    m = simulate_melting(_AMP, 79.4, dh_cal_per_mol=_DH)
    svg = render_melting(m, mirna_id="hsa-miR-16-5p", amplicon_bp=63, gc_percent=57.1)
    ET.fromstring(svg)
    assert VIZ_SIMULATED_LABEL in svg
    assert "Tm = 79.4" in svg
    assert "63 bp" in svg


def test_render_shows_approximate_label():
    m = simulate_melting("AT" * 40, 78.0, params={})
    svg = render_melting(m, amplicon_bp=80)
    assert "approximated" in svg


def test_render_shows_dimer_warning():
    m = simulate_melting(_AMP, 79.4, dh_cal_per_mol=_DH)
    svg = render_melting(m, amplicon_bp=63,
                         dimer_tm_warning={"dimer_tm": 74.0, "delta_c": 5.4})
    assert "within 5.4" in svg and "may not confirm specificity" in svg


def test_render_deterministic():
    m = simulate_melting(_AMP, 79.4, dh_cal_per_mol=_DH)
    assert render_melting(m, amplicon_bp=63) == render_melting(m, amplicon_bp=63)
