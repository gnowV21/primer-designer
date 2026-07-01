# ================================================================
# tests/test_bound_fraction.py — Unit tests for Module 7 (Phase 3)
# ================================================================

import math
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import primer3
from algorithm.bound_fraction import (
    calculate_bound_fraction_binding,
    calculate_bound_fraction_full,
    score_bound_fraction,
    _get_dh_ds,
    _calculate_bound_fraction,
)

DEFAULT_PARAMS = {}   # uses module defaults (P3_DEFAULT_* constants)


# ── primer3-py workaround verification ───────────────────────────

def test_calc_heterodimer_returns_thermodynamics():
    """calc_heterodimer(seq, revcomp(seq)) exposes dH/dS/dG/tm. [spec §4.4]"""
    r = primer3.calc_heterodimer("ATCGATCGATCGATCG", "CGATCGATCGATCGAT")
    assert r.dh < 0,  "dH must be negative (exothermic binding)"
    assert r.ds < 0,  "dS must be negative (entropy decrease)"
    assert r.dg < 0,  "dG must be negative (binding favorable)"
    assert 40 < r.tm < 60, f"Tm {r.tm}°C out of range for 16 nt duplex"


def test_get_dh_ds_returns_negative_values():
    dH, dS = _get_dh_ds("ATCGATCGATCGATCG", DEFAULT_PARAMS)
    assert dH < 0
    assert dS < 0


# ── bound fraction values ─────────────────────────────────────────

def test_bound_fraction_binding_in_range():
    specific = "TAGCTTATCAGACTGA"   # 16 nt, hsa-miR-21-5p region
    f = calculate_bound_fraction_binding(specific, DEFAULT_PARAMS)
    assert 0 <= f <= 100, f"fraction {f}% out of range"


def test_bound_fraction_full_in_range():
    specific = "TAGCTTATCAGACTGA"
    full = "GCGCGCGCGC" + specific   # full primer with tail
    f = calculate_bound_fraction_full(full, DEFAULT_PARAMS)
    assert 0 <= f <= 100, f"fraction {f}% out of range"


def test_binding_vs_full_independent():
    """binding and full primers compute independently."""
    specific = "ATCGATGCATCGATGC"
    full     = "GCGCGCGCGC" + specific
    fb = calculate_bound_fraction_binding(specific, DEFAULT_PARAMS)
    ff = calculate_bound_fraction_full(full, DEFAULT_PARAMS)
    assert 0 <= fb <= 100
    assert 0 <= ff <= 100


def test_longer_primer_higher_or_equal_fraction():
    """Longer primer (more stable duplex) → fraction ≥ shorter."""
    short = "TAGCTTATCAG"      # 11 nt
    long  = "TAGCTTATCAGACTGA" # 16 nt
    fs = calculate_bound_fraction_binding(short, DEFAULT_PARAMS)
    fl = calculate_bound_fraction_binding(long, DEFAULT_PARAMS)
    # Longer primer has more negative dG → higher K → higher fraction
    assert fl >= fs, f"Longer primer fraction {fl}% < shorter {fs}%"


# ── scoring ───────────────────────────────────────────────────────

def test_score_at_opt_is_100():
    result = score_bound_fraction(97.0)
    assert result["score"] == 100
    assert result["band"] == "optimal"


def test_score_above_opt_still_100():
    result = score_bound_fraction(99.5)
    assert result["score"] == 100
    assert result["band"] == "optimal"


def test_score_at_min_boundary():
    result = score_bound_fraction(90.0)
    assert result["score"] == 70.0
    assert result["band"] == "acceptable"


def test_score_midpoint_acceptable():
    result = score_bound_fraction(93.5)
    assert 70 < result["score"] < 100
    assert result["band"] == "acceptable"


def test_score_below_min_suboptimal():
    result = score_bound_fraction(85.0)
    assert result["score"] < 70
    assert result["band"] == "suboptimal"


def test_score_floor_at_zero():
    result = score_bound_fraction(0.0)
    assert result["score"] == 0.0


def test_score_at_50_is_zero():
    result = score_bound_fraction(50.0)
    assert result["score"] == 0.0


def test_score_fraction_preserved():
    result = score_bound_fraction(88.5)
    assert result["fraction_pct"] == 88.5
