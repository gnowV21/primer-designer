"""
Tests for Kwok 1990 position-weighted distance in family cross-reactivity.

REWRITTEN for SPEC_week2 C2. The previous version asserted "a mismatch at the 3'-terminal
CHARACTER scores 4.0" — that described the miRNA's 3' end. The corrected geometry indexes
weights from the PRIMER 3' terminus. For the stem-loop RT primer (the reverse complement
of the miRNA 3' overhang) the primer 3' terminus pairs with window[0] — the 5'-MOST
nucleotide of the overhang window. So `_kwok_distance` (RT axis) now weights the FIRST
character of the window highest, not the last. Expected values below are the real let-7a
overhang windows, verified against backend/db/mirbase.db (SPEC_week2 §1.1). Tests are
rewritten, not deleted, per the spec directive.
"""
import pytest

from algorithm.specificity_check.family_crossreactivity import (
    _hamming,
    _kwok_distance,
    _classify_risk,
)
from algorithm.constants import KWOK_POSITION_WEIGHTS, KWOK_DIST_DISCRIMINATING


# ── _kwok_distance — RT axis (weight indexed from window START = primer 3' terminus) ──

def test_kwok_distance_zero_for_perfect_match():
    assert _kwok_distance("ATAGTT", "ATAGTT") == 0.0


def test_kwok_distance_window_start_is_primer_3prime_terminus():
    # RT primer 3' terminus pairs with window[0]; a mismatch there blocks extension → weight 4.0.
    assert _kwok_distance("ATAGTT", "GTAGTT") == KWOK_POSITION_WEIGHTS[0]


def test_kwok_distance_window_end_is_far_from_primer_3prime():
    # window[-1] is the RT primer 5' end → tolerated → weight 1.0.
    assert _kwok_distance("ATAGTT", "ATAGTA") == KWOK_POSITION_WEIGHTS[5]


def test_kwok_distance_two_mismatches_additive():
    # window[0] (4.0) + window[1] (2.0) = 6.0
    assert _kwok_distance("ATAGTT", "GCAGTT") == KWOK_POSITION_WEIGHTS[0] + KWOK_POSITION_WEIGHTS[1]


def test_kwok_distance_unequal_length_returns_zero():
    assert _kwok_distance("ATA", "ATAGTT") == 0.0


def test_kwok_distance_start_higher_than_end():
    assert _kwok_distance("AAAAAA", "XAAAAA") > _kwok_distance("AAAAAA", "AAAAAX")


# ── RT-axis ground truth: real let-7a siblings (target overhang ATAGTT) ──
# SPEC_week2 §1.1 table, verified against mirbase.db.
_LET7A = [
    ("let-7b", "GTGGTT", 5.5),
    ("let-7c", "ATGGTT", 1.5),
    ("let-7g", "ACAGTT", 2.0),
    ("let-7i", "GCTGTT", 7.5),
    ("let-7d", "ATAGTT", 0.0),
]


@pytest.mark.parametrize("name,window,expected", _LET7A)
def test_kwok_distance_let7a_ground_truth(name, window, expected):
    assert _kwok_distance("ATAGTT", window) == expected, f"{name} RT-axis kwok mismatch"


# ── _classify_risk (classification logic unchanged; kwok_dist now primer-anchored) ──

def test_classify_risk_identical():
    assert _classify_risk(0, 10.0, 0.0) == "IDENTICAL"


def test_classify_risk_1mm_at_primer_3prime_is_low_despite_small_delta_tm():
    # kwok_dist ≥ KWOK_DIST_DISCRIMINATING (mismatch at window[0], the RT primer 3' terminus)
    # → LOW even when ΔTm < 5 °C, because a 3'-terminal mismatch blocks extension [Kwok90].
    kwok_dist = KWOK_POSITION_WEIGHTS[0]  # 4.0
    assert kwok_dist >= KWOK_DIST_DISCRIMINATING
    assert _classify_risk(mismatch=1, delta_tm=1.0, kwok_dist=kwok_dist) == "LOW"


def test_classify_risk_1mm_far_from_primer_3prime_small_delta_tm_is_high():
    kwok_dist = KWOK_POSITION_WEIGHTS[5]  # 1.0 (mismatch at window[-1], RT primer 5' end)
    assert kwok_dist < KWOK_DIST_DISCRIMINATING
    assert _classify_risk(mismatch=1, delta_tm=1.0, kwok_dist=kwok_dist) == "HIGH"


def test_classify_risk_1mm_large_delta_tm_is_low():
    kwok_dist = KWOK_POSITION_WEIGHTS[5]  # 1.0
    assert _classify_risk(mismatch=1, delta_tm=7.0, kwok_dist=kwok_dist) == "LOW"


def test_classify_risk_penultimate_mismatch_below_threshold():
    kwok_dist = KWOK_POSITION_WEIGHTS[1]  # 2.0 < 3.0 → ΔTm rule applies
    assert kwok_dist < KWOK_DIST_DISCRIMINATING
    assert _classify_risk(1, 2.0, kwok_dist) == "HIGH"
    assert _classify_risk(1, 6.0, kwok_dist) == "LOW"


def test_classify_risk_2mm_always_low():
    assert _classify_risk(2, 0.0, 0.0) == "LOW"
    assert _classify_risk(2, 10.0, 6.0) == "LOW"


def test_classify_risk_3mm_safe():
    assert _classify_risk(3, 0.0, 0.0) == "SAFE"


def test_classify_risk_no_kwok_dist_backward_compat():
    assert _classify_risk(1, 3.0) == "HIGH"   # ΔTm < 5
    assert _classify_risk(1, 6.0) == "LOW"    # ΔTm ≥ 5
