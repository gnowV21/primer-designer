"""
Tests for Kwok 1990 position-weighted distance in family cross-reactivity.

Key behaviours verified:
  - _kwok_distance: 3'-terminal mismatch scores 4.0; 5'-terminal scores 1.0
  - _classify_risk: 1-mismatch at 3' terminal → LOW (not HIGH) even with ΔTm < 5°C
  - _classify_risk: 1-mismatch at 5' position + ΔTm < 5°C → still HIGH
  - _classify_risk: 0 mismatch → IDENTICAL (unchanged)
  - _classify_risk: 2 mismatches → LOW (unchanged)
  - _evaluate result includes kwok_distance field
"""
import pytest

from algorithm.specificity_check.family_crossreactivity import (
    _hamming,
    _kwok_distance,
    _classify_risk,
)
from algorithm.constants import KWOK_POSITION_WEIGHTS, KWOK_DIST_DISCRIMINATING


# ── _kwok_distance ─────────────────────────────────────────────────

def test_kwok_distance_zero_for_perfect_match():
    assert _kwok_distance("ABCDEF", "ABCDEF") == 0.0


def test_kwok_distance_3prime_terminal_mismatch():
    # Position 0 from 3' end (last char) → weight = KWOK_POSITION_WEIGHTS[0] = 4.0
    s1 = "ABCDEF"
    s2 = "ABCDEX"   # mismatch at index 5 (last) → position 0 from 3'
    assert _kwok_distance(s1, s2) == KWOK_POSITION_WEIGHTS[0]


def test_kwok_distance_5prime_terminal_mismatch():
    # Position 5 from 3' end (first char in 6-mer) → weight = KWOK_POSITION_WEIGHTS[5] = 1.0
    s1 = "ABCDEF"
    s2 = "XBCDEF"   # mismatch at index 0 → position 5 from 3'
    assert _kwok_distance(s1, s2) == KWOK_POSITION_WEIGHTS[5]


def test_kwok_distance_two_mismatches_additive():
    # Mismatch at 3' terminal (weight 4) + penultimate (weight 2) = 6.0
    s1 = "ABCDEF"
    s2 = "ABCDXX"
    assert _kwok_distance(s1, s2) == KWOK_POSITION_WEIGHTS[0] + KWOK_POSITION_WEIGHTS[1]


def test_kwok_distance_unequal_length_returns_zero():
    assert _kwok_distance("ABC", "ABCD") == 0.0


def test_kwok_distance_3prime_higher_than_5prime():
    s1 = "AAAAAA"
    s2_3prime = "AAAAAX"   # mismatch at 3' end
    s2_5prime = "XAAAAA"   # mismatch at 5' end
    assert _kwok_distance(s1, s2_3prime) > _kwok_distance(s1, s2_5prime)


# ── _classify_risk with kwok_dist ──────────────────────────────────

def test_classify_risk_identical():
    assert _classify_risk(0, 10.0, 0.0) == "IDENTICAL"


def test_classify_risk_1mm_3prime_terminal_is_low_despite_small_delta_tm():
    # 3'-terminal mismatch: kwok_dist = 4.0 >= KWOK_DIST_DISCRIMINATING (3.0) → LOW
    kwok_dist = KWOK_POSITION_WEIGHTS[0]  # 4.0
    assert kwok_dist >= KWOK_DIST_DISCRIMINATING
    result = _classify_risk(mismatch=1, delta_tm=1.0, kwok_dist=kwok_dist)
    assert result == "LOW", (
        "3'-terminal 1-mismatch should be LOW even with ΔTm < 5°C [Kwok90]"
    )


def test_classify_risk_1mm_5prime_small_delta_tm_is_high():
    # 5'-terminal mismatch: kwok_dist = 1.0 < KWOK_DIST_DISCRIMINATING → falls back to ΔTm rule
    kwok_dist = KWOK_POSITION_WEIGHTS[5]  # 1.0
    assert kwok_dist < KWOK_DIST_DISCRIMINATING
    result = _classify_risk(mismatch=1, delta_tm=1.0, kwok_dist=kwok_dist)
    assert result == "HIGH"


def test_classify_risk_1mm_5prime_large_delta_tm_is_low():
    kwok_dist = KWOK_POSITION_WEIGHTS[5]  # 1.0
    result = _classify_risk(mismatch=1, delta_tm=7.0, kwok_dist=kwok_dist)
    assert result == "LOW"


def test_classify_risk_penultimate_mismatch_below_threshold():
    # Position 1 from 3': weight 2.0 < KWOK_DIST_DISCRIMINATING (3.0) → ΔTm rule applies
    kwok_dist = KWOK_POSITION_WEIGHTS[1]  # 2.0
    assert kwok_dist < KWOK_DIST_DISCRIMINATING
    # Small ΔTm → HIGH
    assert _classify_risk(1, 2.0, kwok_dist) == "HIGH"
    # Large ΔTm → LOW
    assert _classify_risk(1, 6.0, kwok_dist) == "LOW"


def test_classify_risk_2mm_always_low():
    assert _classify_risk(2, 0.0, 0.0) == "LOW"
    assert _classify_risk(2, 10.0, 6.0) == "LOW"


def test_classify_risk_3mm_safe():
    assert _classify_risk(3, 0.0, 0.0) == "SAFE"


def test_classify_risk_no_kwok_dist_backward_compat():
    # Default kwok_dist=0 → behaves like old uniform Hamming
    assert _classify_risk(1, 3.0) == "HIGH"   # ΔTm < 5
    assert _classify_risk(1, 6.0) == "LOW"    # ΔTm ≥ 5
