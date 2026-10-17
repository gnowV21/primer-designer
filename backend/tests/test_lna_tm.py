"""
Unit tests for algorithm/lna_tm.py — Phase 8 PART B.

18 test cases covering:
  - Model correctness (doublet classification, source dispatch, Tm formula)
  - Search strategy (exhaustive vs greedy thresholds)
  - Design constraints (3'-terminal warning, out-of-range positions)
  - Discrimination mode
  - Invariants (same engine → delta consistency, empty LNA = DNA, etc.)
"""

import math
import sys
import os
import pytest

# Allow running from repo root or backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.lna_tm import (
    _classify_doublet,
    _lookup_doublet,
    _nn_tm,
    calc_lna_tm,
    suggest_lna_positions,
    _SL98,
    _MCTIGUE04,
    _OWCZARZY11,
    R_CAL,
)

# Default params matching typical wet-lab conditions
_PARAMS = {
    "saltConcentration":      50.0,
    "magnesiumConcentration":  1.5,
    "dntpTotal":               0.8,
    "primerConcentration":   200.0,
}


# ─────────────────────────────────────────────────────────────────
# 1. Doublet classification
# ─────────────────────────────────────────────────────────────────

class TestClassifyDoublet:
    def test_both_dna(self):
        assert _classify_doublet("ACGT", set(), 0) == "dna_dna"

    def test_first_lna(self):
        assert _classify_doublet("ACGT", {0}, 0) == "one_lna"

    def test_second_lna(self):
        assert _classify_doublet("ACGT", {1}, 0) == "one_lna"

    def test_both_lna(self):
        assert _classify_doublet("ACGT", {0, 1}, 0) == "lna_lna"

    def test_lna_not_in_doublet_gives_dna_dna(self):
        # LNA at position 3 does not affect doublet (0,1)
        assert _classify_doublet("ACGT", {3}, 0) == "dna_dna"


# ─────────────────────────────────────────────────────────────────
# 2. Doublet lookup — correct table dispatch
# ─────────────────────────────────────────────────────────────────

class TestLookupDoublet:
    def test_dna_dna_uses_sl98(self):
        dh, ds, src = _lookup_doublet("AC", set(), 0)
        assert src == "santalucia98"
        assert (dh, ds) == _SL98["AC"]

    def test_one_lna_first_uses_mctigue(self):
        # LNA at 0, DNA at 1 → key 'Ac' (LNA=upper, DNA=lower)
        dh, ds, src = _lookup_doublet("AC", {0}, 0)
        assert src == "mctigue04"
        assert (dh, ds) == _MCTIGUE04["Ac"]

    def test_one_lna_second_uses_mctigue(self):
        # DNA at 0, LNA at 1 → key 'aC'
        dh, ds, src = _lookup_doublet("AC", {1}, 0)
        assert src == "mctigue04"
        assert (dh, ds) == _MCTIGUE04["aC"]

    def test_both_lna_uses_owczarzy(self):
        dh, ds, src = _lookup_doublet("AC", {0, 1}, 0)
        assert src == "owczarzy11"
        assert (dh, ds) == _OWCZARZY11["AC"]


# ─────────────────────────────────────────────────────────────────
# 3. _nn_tm — engine correctness invariants
# ─────────────────────────────────────────────────────────────────

class TestNnTm:
    def test_returns_required_keys(self):
        result = _nn_tm("ACGT", [], _PARAMS)
        for key in ("tm", "dh_total", "ds_total", "ds_eff", "param_sources", "per_doublet"):
            assert key in result

    def test_pure_dna_only_sl98(self):
        result = _nn_tm("ACGT", [], _PARAMS)
        assert result["param_sources"] == ["santalucia98"]

    def test_n_minus_1_doublets(self):
        seq = "ACGTACGT"  # 8 bases → 7 doublets
        result = _nn_tm(seq, [], _PARAMS)
        assert len(result["per_doublet"]) == 7

    def test_lna_adds_mctigue_to_sources(self):
        result = _nn_tm("ACGT", [1], _PARAMS)
        assert "mctigue04" in result["param_sources"]

    def test_double_lna_adds_owczarzy_to_sources(self):
        result = _nn_tm("ACGT", [1, 2], _PARAMS)
        assert "owczarzy11" in result["param_sources"]

    def test_higher_salt_increases_tm(self):
        low_salt  = dict(_PARAMS, saltConcentration=20.0)
        high_salt = dict(_PARAMS, saltConcentration=200.0)
        tm_low  = _nn_tm("ACGTACGT", [], low_salt)["tm"]
        tm_high = _nn_tm("ACGTACGT", [], high_salt)["tm"]
        assert tm_high > tm_low


# ─────────────────────────────────────────────────────────────────
# 4. calc_lna_tm — public API
# ─────────────────────────────────────────────────────────────────

class TestCalcLnaTm:
    def test_basic_return_shape(self):
        res = calc_lna_tm("ACGTACGT", [2], _PARAMS)
        for key in ("tm_dna", "tm_lna", "delta_tm", "lna_positions", "method",
                    "per_doublet", "warnings"):
            assert key in res

    def test_empty_lna_gives_zero_delta(self):
        res = calc_lna_tm("ACGTACGT", [], _PARAMS)
        assert res["delta_tm"] == 0.0
        assert res["tm_dna"] == res["tm_lna"]

    def test_delta_equals_lna_minus_dna(self):
        res = calc_lna_tm("ACGTACGT", [2, 5], _PARAMS)
        expected = round(res["tm_lna"] - res["tm_dna"], 1)
        assert res["delta_tm"] == expected

    def test_lna_raises_tm(self):
        res = calc_lna_tm("ACGTACGTACGT", [2, 6], _PARAMS)
        assert res["delta_tm"] > 0.0, "LNA substitutions should increase Tm"

    def test_invalid_base_returns_warning(self):
        res = calc_lna_tm("ACGU", [], _PARAMS)   # U is not DNA
        assert res["tm_dna"] is None
        assert any("Unsupported" in w for w in res["warnings"])

    def test_too_short_returns_warning(self):
        res = calc_lna_tm("A", [], _PARAMS)
        assert res["tm_dna"] is None
        assert any("too short" in w for w in res["warnings"])

    def test_3prime_terminal_lna_warning(self):
        seq = "ACGTACGT"   # last index = 7
        res = calc_lna_tm(seq, [7], _PARAMS)
        assert any("terminal" in w and "LNA" in w for w in res["warnings"])

    def test_method_reflects_used_sources(self):
        res = calc_lna_tm("ACGTACGT", [2], _PARAMS)
        assert "mctigue04" in res["method"]


# ─────────────────────────────────────────────────────────────────
# 5. suggest_lna_positions — search strategy
# ─────────────────────────────────────────────────────────────────

class TestSuggestLnaPositions:
    def test_returns_required_keys(self):
        res = suggest_lna_positions("ACGTACGTACGT", target_tm=60.0, params=_PARAMS)
        for key in ("suggested_positions", "tm_achieved", "target_met",
                    "search", "mode", "warnings"):
            assert key in res

    def test_search_mode_is_exhaustive_or_greedy(self):
        res = suggest_lna_positions("ACGTACGTACGT", target_tm=60.0, params=_PARAMS)
        assert res["search"] in ("exhaustive", "greedy")

    def test_short_seq_uses_exhaustive(self):
        # 12 nt, max_lna=2: C(10, 2)=45 < LNA_EXHAUSTIVE_LIMIT=5000
        res = suggest_lna_positions("ACGTACGTACGT", target_tm=60.0, params=_PARAMS, max_lna=2)
        assert res["search"] == "exhaustive"

    def test_empty_seq_returns_warning(self):
        res = suggest_lna_positions("", target_tm=60.0, params=_PARAMS)
        assert res["suggested_positions"] == []
        assert len(res["warnings"]) > 0

    def test_discrimination_mode_accepted(self):
        res = suggest_lna_positions(
            "ACGTACGTACGT", target_tm=60.0, params=_PARAMS, mode="discrimination",
            sibling_mismatch_positions=[3, 5],
        )
        assert res["mode"] == "discrimination"

    def test_suggested_positions_within_bounds(self):
        seq = "ACGTACGTACGT"
        res = suggest_lna_positions(seq, target_tm=60.0, params=_PARAMS)
        for pos in res["suggested_positions"]:
            assert 0 <= pos < len(seq)


# ── Week2 C10: benchmark-coverage caveat scope ────────────────────
_C10_PARAMS = {"saltConcentration": 50.0, "magnesiumConcentration": 1.5,
               "dntpTotal": 0.8, "primerConcentration": 200.0}


def test_single_lna_claims_benchmark_coverage():
    res = calc_lna_tm("ACGTACGTACGT", [2, 6], _C10_PARAMS)   # non-adjacent
    assert res["benchmark_coverage"] == "single_lna"
    assert any("Benchmarked against McTigue 2004" in w for w in res["warnings"])
    assert not any("NOT covered by our benchmark" in w for w in res["warnings"])


def test_consecutive_lna_flagged_unbenchmarked():
    res = calc_lna_tm("ACGTACGTACGT", [5, 6], _C10_PARAMS)   # adjacent LNA:LNA
    assert res["benchmark_coverage"] in ("consecutive_lna_unbenchmarked", "mixed")
    assert any("NOT covered by our benchmark" in w for w in res["warnings"])
