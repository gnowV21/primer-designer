# ================================================================
# tests/test_design_speed.py — perf/design-speed (docs/REVIEW_panel_4.0.0.md §8)
#
# Bước 2: the memoised duplex Tm and table-only forward ΔCq return exactly what the
# direct computation returns, and BLAST_CACHE_PATH moves the cache file only.
# ================================================================

import os

import algorithm.primer3_safe as primer3
from algorithm.specificity_check import overhang_collision as oc
from algorithm.specificity_check.assay_model import fwd_axis
from algorithm.specificity_check.blast_cache import BlastCache
from algorithm.thermodynamics import _get_p3_params

_P3 = _get_p3_params({})
_PAIRS = [("TAGCTTATCAGACTG", "TAGCTTATCAGACTGA"), ("TGAGGTAGTAGGTTG", "AGAGGTAGTAGGTTGC"),
          ("TAATTTTATGTATAA", "TAATTTTATGTATAAG")]


def test_duplex_tm_memo_equals_direct():
    for region, window in _PAIRS:
        direct = float(primer3.calc_heterodimer(region, oc._revcomp(window), **_P3).tm)
        assert oc._duplex_tm(region, window, _P3) == direct
        assert oc._duplex_tm(region, window, dict(_P3)) == direct      # cached path


def test_fwd_table_memo_equals_direct():
    for region, other in _PAIRS:
        assert oc._fwd_table_dcq(region, other) == fwd_axis(region, other, None)["delta_cq"]
        assert oc._fwd_table_dcq(region, other) == fwd_axis(region, other, None)["delta_cq"]


def test_memo_is_bounded():
    assert oc._duplex_tm_memo.cache_info().maxsize == oc._MEMO_SIZE
    assert oc._fwd_table_dcq.cache_info().maxsize == oc._MEMO_SIZE


def test_blast_cache_path_env(monkeypatch, tmp_path):
    p = tmp_path / "other.sqlite"
    monkeypatch.setenv("BLAST_CACHE_PATH", str(p))
    bc = BlastCache()
    assert os.path.abspath(bc.db_path) == os.path.abspath(str(p))
    key = BlastCache._compute_key("ACGT", "CCAGT", "v", "hsa-miR-1", "ctx")
    monkeypatch.delenv("BLAST_CACHE_PATH")
    assert BlastCache._compute_key("ACGT", "CCAGT", "v", "hsa-miR-1", "ctx") == key   # key unchanged
    assert os.path.abspath(BlastCache().db_path) != os.path.abspath(str(p))
