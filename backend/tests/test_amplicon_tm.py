"""SPEC_phase5 PART D — predicted_amplicon_tm + dimer proximity (backend)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.thermodynamics import predicted_amplicon_tm, amplicon_dh_cal, calc_dimer_tm  # noqa: E402
from algorithm.constants import P3_HETERODIMER_MAX_BP                                        # noqa: E402

_AMP = "GGCGTAGCAGCACGTAAATATTGGCGGTCGTATCCAGTGCGAATACCTCGGACCCTGCACTGG"  # 63 bp, GC 57.1%


def test_amplicon_tm_in_product_range():
    tm = predicted_amplicon_tm(_AMP, {})
    assert 70 <= tm <= 90            # typical SYBR product melt


def test_amplicon_tm_rises_with_gc():
    at_rich = "AT" * 40
    gc_rich = "GC" * 40
    assert predicted_amplicon_tm(gc_rich, {}) > predicted_amplicon_tm(at_rich, {})


def test_amplicon_tm_rises_with_salt():
    lo = predicted_amplicon_tm(_AMP, {"saltConcentration": 20})
    hi = predicted_amplicon_tm(_AMP, {"saltConcentration": 200})
    assert hi > lo                   # 16.6·log10[Na+] term


def test_amplicon_tm_none_for_too_short():
    assert predicted_amplicon_tm("A", {}) is None


def test_amplicon_dh_none_above_primer3_limit():
    long_seq = "AT" * (P3_HETERODIMER_MAX_BP // 2 + 5)   # > 60 bp
    assert amplicon_dh_cal(long_seq, {}) is None


def test_amplicon_dh_negative_within_limit():
    dh = amplicon_dh_cal("GCGCGCGCGCGCGCGCGCGC", {})     # 20 bp
    assert dh is not None and dh < 0                     # formation ΔH is negative


def test_dimer_tm_returns_value():
    tm = calc_dimer_tm("GGGGCCCCGGGGCCCC", None, {})     # self-complementary → strong dimer
    assert tm is not None
