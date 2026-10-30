# ================================================================
# tests/test_assay_model.py — assay-level ΔCq model (2026-10-29)
#
# ΔCq_assay = ΔCq_RT + ΔCq_FWD, lower bounds of published data:
# Schamberger 2014 (3' isomiRs), Chen 2005 (overhang mismatches),
# Czimmerer 2013, Stadhouders 2010 (forward 3' mismatches), Kwok 1990.
# ================================================================

import pytest

from algorithm.specificity_check.assay_model import (
    variant_category, rt_axis, fwd_axis, evaluate, assay_label, cross_reactivity_pct,
)

_T = "TAGCTTATCAGACTGATGTTGA"     # miR-21-5p (DNA)


# ── how another miRBase entry relates to the target ──────────────

@pytest.mark.parametrize("other,cat", [
    (_T, "same_sequence"),
    (_T[:-1], "shifted_3p"),            # 3' end 1 nt shorter
    (_T + "A", "shifted_3p"),           # 3' end 1 nt longer
    (_T[1:], "shifted_5p"),             # 5' end trimmed (seed shifts)
    ("A" + _T, "shifted_5p"),
    (_T[1:-1], "shifted_5p"),           # both ends: the 5' shift dominates
    (_T[:-3], "other"),                # 3 nt shorter: beyond the ±2 range
    ("TAGCTTATCAGTCTGATGTTGA", "other"),
])
def test_variant_category(other, cat):
    assert variant_category(_T, other) == cat


# ── RT axis: 3' isomiRs [Schamberger14] ──────────────────────────

def test_rt_3p_shorter_by_one_is_captured():
    assert rt_axis(_T, _T[:-1], 6)["delta_cq"] == 0.0


def test_rt_3p_shorter_by_two_costs_three_cycles():
    rt = rt_axis(_T, _T[:-2], 6)
    assert rt["delta_cq"] == 3.0 and rt["shift_3p"] == -2


@pytest.mark.parametrize("ext", ["A", "AC"])
def test_rt_3p_longer_is_captured(ext):
    assert rt_axis(_T, _T + ext, 6)["delta_cq"] == 0.0


def test_rt_register_search_catches_the_shift():
    """Compared at fixed positions, the last 6 nt of _T[:-1] differ from _T's at
    most positions; the register search pairs them with no mismatch."""
    fixed_mm = sum(a != b for a, b in zip(_T[-6:], _T[:-1][-6:]))
    assert fixed_mm >= 4
    assert rt_axis(_T, _T[:-1], 6)["mismatch_positions"] == []


# ── RT axis: overhang mismatches [Chen05][Czimmerer13] ───────────

def _rt_variant(pos_from_rt3, base):
    """_T with the window base at `pos_from_rt3` (1 = pairs with the RT primer 3'
    end, i.e. the 5'-most nt of the last 6) replaced by `base`."""
    i = len(_T) - 6 + pos_from_rt3 - 1
    return _T[:i] + base + _T[i + 1:]


def test_rt_single_near_mismatch():
    # window TGTTGA: position 2 = G → C (not a wobble)
    assert rt_axis(_T, _rt_variant(2, "C"), 6)["delta_cq"] == 7.0


def test_rt_single_far_mismatch():
    assert rt_axis(_T, _rt_variant(5, "C"), 6)["delta_cq"] == 3.5


def test_rt_wobble_rg_dt():
    # position 6 of the window is A (primer T); off-target G → rG·dT, far: min(3.5, 4.75)
    rt = rt_axis(_T, _rt_variant(6, "G"), 6)
    assert rt["wobble"] and rt["delta_cq"] == 3.5
    # let-7a vs let-7c: rG·dT at position 3, near: min(7, 4.75)
    rt = rt_axis("TGAGGTAGTAGGTTGTATAGTT", "TGAGGTAGTAGGTTGTATGGTT", 6)
    assert rt["wobble"] and rt["delta_cq"] == 4.75


def test_rt_two_mismatches():
    o = _rt_variant(1, "C")
    o = o[:len(_T) - 2] + "C" + o[len(_T) - 1:]
    assert rt_axis(_T, o, 6)["delta_cq"] == 8.0


# ── FWD axis [Stadhouders10][Kwok90] ─────────────────────────────

_P = _T[:15]                          # specific region TAGCTTATCAGACTG


def _fwd_variant(pos_from_3p, base):
    i = len(_P) - pos_from_3p
    return _T[:i] + base + _T[i + 1:]


def test_fwd_terminal_pair_groups():
    # Primer 3' base G. Off-target sense base X → template = complement(X):
    # sense A → G–T minor (1.0); sense C → G–G severe; sense T → G–A severe.
    assert fwd_axis(_P, _fwd_variant(1, "A"))["delta_cq"] == 1.0
    assert fwd_axis(_P, _fwd_variant(1, "C"))["delta_cq"] == 8.3
    assert fwd_axis(_P, _fwd_variant(1, "T"))["delta_cq"] == 8.3


def test_fwd_position_weights():
    assert fwd_axis(_P, _fwd_variant(2, "A"))["delta_cq"] == 1.9
    assert fwd_axis(_P, _fwd_variant(4, "C"))["delta_cq"] == 0.5
    assert fwd_axis(_P, _fwd_variant(9, "C"))["delta_cq"] == 0.0


def test_fwd_two_mismatches_near_3p_block_unless_terminal_t():
    o = _fwd_variant(1, "A")
    o = o[:len(_P) - 3] + "T" + o[len(_P) - 2:]
    assert fwd_axis(_P, o)["delta_cq"] == 8.3
    # Primer ending in T: terminal T–C (sense G → template C) plus a second mismatch
    # still extends [Kwok90] → the terminal pair's value (intermediate, 3.8).
    p = "TAGCTTATCAGACTGAT"
    t = p + "GTTGA"
    o = t[:16] + "G" + t[17:]
    o = o[:14] + "C" + o[15:]
    assert fwd_axis(p, o)["delta_cq"] == 3.8


def test_fwd_5p_isomir_is_free():
    assert fwd_axis(_P, _T[1:])["delta_cq"] == 0.0
    assert fwd_axis(_P, "A" + _T)["delta_cq"] == 0.0


def test_fwd_stability_term_is_max_and_capped():
    f = fwd_axis(_P, _fwd_variant(9, "C"), tm_gap=lambda r: 6.0)
    assert f["delta_cq"] == pytest.approx(3.96)
    f = fwd_axis(_P, _fwd_variant(9, "C"), tm_gap=lambda r: 60.0)
    assert f["delta_cq"] == 8.3


# ── assay ────────────────────────────────────────────────────────

def test_axes_add_and_labels():
    e = evaluate(_T, _T[:-2], 6, 15)          # RT 3.0 + FWD 0.0
    assert e["delta_cq"] == 3.0 and e["assay_label"] == "CO-AMPLIFIED"
    assert e["category"] == "shifted_3p"
    assert assay_label(3.3) == "PARTIAL" and assay_label(4.3) == "DISCRIMINATED"
    assert cross_reactivity_pct(1.0) == 50.0


def test_let7c_matches_chen2005_cross_signal():
    """let-7a assay on let-7c: one rG·dT pair, forward identical. The model gives the
    3.7 % Chen 2005 measured — it is the calibration point, not an independent check."""
    e = evaluate("TGAGGTAGTAGGTTGTATAGTT", "TGAGGTAGTAGGTTGTATGGTT", 6, 12)
    assert e["cross_reactivity_pct"] == pytest.approx(3.7, abs=0.05)


def test_rt_discriminated_other_skips_forward():
    e = evaluate(_T, _T[:-6] + "CCCCCC", 6, 15)
    assert e["fwd"] is None and e["delta_cq_is_lower_bound"]
    assert e["assay_label"] == "DISCRIMINATED"


# ── end-shift evidence: a point value with a published range ─────

def test_shift_values_carry_their_measured_range():
    """The shift term rests on one study, two miRNAs that differ by up to 4 Ct
    (Schamberger & Orbán 2014). Every shifted register reports that range so the
    point value is never mistaken for a measurement."""
    for other, key, rng in [(_T[:-1], "short1", [0.0, 4.0, 2]),
                            (_T[:-2], "short2", [3.0, 4.0, 1]),
                            (_T + "A", "longer", [0.0, 4.0, 2])]:
        rt = rt_axis(_T, other, 6)
        assert rt["shift_range"] == rng, (key, rt["shift_range"])
        assert rt["delta_cq"] == rng[0]              # the point value is the lower bound
        assert f"n = {rng[2]} miRNA" in rt["basis"]
        assert "Schamberger" in rt["shift_evidence_note"]


def test_unshifted_register_has_no_shift_range():
    rt = rt_axis(_T, _T, 6)
    assert rt["shift_range"] is None and rt["shift_evidence_note"] is None


def test_assay_delta_cq_reports_the_upper_end_of_the_shift_range():
    e = evaluate(_T, _T[:-1], 6, 15)         # RT shift −1: 0 Ct low, 4 Ct high
    assert e["delta_cq"] == 0.0 and e["delta_cq_high"] == 4.0
    assert e["assay_label"] == "CO-AMPLIFIED"      # the label follows the lower bound
    e = evaluate(_T, _T, 6, 15)
    assert e["delta_cq_high"] is None              # nothing shifted, nothing to widen
