# ================================================================
# tests/test_forward_selection.py — v3.2.0 forward-primer selection
#
# Score first, diversify after: every usable 3' end reaches the 15-criterion
# score (best FORWARD_TAILS_PER_LENGTH tails each), then select_diverse_top picks
# CANDIDATES_TOP_N by score with relaxing diversity. GC clamp: 0 G/C rejected,
# 1 G/C warned. Locks in the fixes for "one set only" (45 % of miRNAs in v3.1.2)
# and for the 13-nt region of hsa-miR-21-3p being dropped before scoring.
# ================================================================

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import algorithm.forward_primer as fp
from algorithm import design_pipeline
from algorithm.constants import CANDIDATES_TOP_N, FORWARD_TAILS_PER_LENGTH
from algorithm.forward_primer import _candidate_pool, _prefilter, select_diverse_top


def _c(length, score=0.0, seq=None, tm=60.0):
    return {"specific_length": length, "total_score": score, "tm_full": tm,
            "sequence": seq or f"{'A' * length}{score}"}


# ── _candidate_pool ──────────────────────────────────────────────

def test_pool_keeps_best_tails_of_every_length():
    cands = [_c(L, seq=f"S{L}-{i:02d}", tm=60 + i * 0.1) for L in (12, 13, 15) for i in range(6)]
    pool = _candidate_pool(cands, 60.0, per_length=3)
    for L in (12, 13, 15):
        kept = [c["sequence"] for c in pool if c["specific_length"] == L]
        assert kept == [f"S{L}-{i:02d}" for i in range(3)]


def test_pool_default_size():
    cands = [_c(12, seq=f"T{i:03d}", tm=60 + i * 0.01) for i in range(100)]
    assert len(_candidate_pool(cands, 60.0)) == FORWARD_TAILS_PER_LENGTH


def test_pool_ties_do_not_depend_on_generation_order():
    """Equal |Tm − Ta| used to fall back to generation order (12 nt before 13 nt)."""
    cands = [_c(12, seq="ZZZ"), _c(12, seq="AAA"), _c(12, seq="MMM"), _c(12, seq="BBB")]
    a = _candidate_pool(cands, 60.0, per_length=3)
    b = _candidate_pool(list(reversed(cands)), 60.0, per_length=3)
    assert [c["sequence"] for c in a] == [c["sequence"] for c in b] == ["AAA", "BBB", "MMM"]


# ── select_diverse_top ───────────────────────────────────────────

def test_score_decides_and_diversity_relaxes_in_steps():
    ranked = [_c(12, 95), _c(13, 94), _c(12, 93), _c(16, 90)]
    top = select_diverse_top(ranked, 3)
    assert [(c["specific_length"], c["selection"]) for c in top] == [
        (12, "best"), (13, "adjacent_3prime"), (16, "distinct_3prime")]


def test_single_3prime_end_falls_back_to_labelled_tail_variants():
    ranked = [_c(12, 93, "T1"), _c(12, 92.6, "T2"), _c(12, 92.5, "T3"), _c(12, 92.0, "T4")]
    top = select_diverse_top(ranked, 3)
    assert [c["sequence"] for c in top] == ["T1", "T2", "T3"]
    assert [c["selection"] for c in top] == ["best", "tail_variant", "tail_variant"]
    assert [c.get("same_binding_as_rank") for c in top] == [None, 1, 1]


def test_distinct_ends_preferred_over_higher_scoring_tail_variant():
    ranked = [_c(14, 96, "A"), _c(14, 95.9, "B"), _c(12, 90, "C")]
    top = select_diverse_top(ranked, 2)
    assert [c["sequence"] for c in top] == ["A", "C"]


def test_fewer_candidates_than_n():
    assert len(select_diverse_top([_c(12, 90)], 3)) == 1
    assert select_diverse_top([], 3) == []


# ── GC clamp: 0 G/C rejected, 1 G/C warned ──────────────────────

def _pf(seq):
    cand = {"sequence": seq, "tm_full": 60.0, "tm_binding": 45.0, "gc_percent": 50.0,
            "amplicon_size": 68, "length": len(seq)}
    return _prefilter(cand, {})


def test_gc_clamp_levels():
    def clamp(last3):
        hard, warn = _pf("ACGTACGTACGTACGTA" + last3)
        return "gc_clamp_fail" in hard, "gc_clamp_weak_warning" in warn
    assert clamp("CAG") == (False, False)   # 2 G/C: preferred
    assert clamp("ATG") == (False, True)    # 1 G/C: passes, warned (scored 75)
    assert clamp("CAT") == (False, True)    # 1 G/C
    assert clamp("ATA") == (True, False)    # 0 G/C: rejected


# ── End-to-end ───────────────────────────────────────────────────

def test_mir21_3p_gets_three_sets_including_the_13nt_region():
    """sRNAPrimerDB's 13-nt region CAACACCAGTCGA was dropped before scoring in v3.1.2."""
    r = design_pipeline.run("CAACACCAGUCGAUGGGCUGU", {}, "hsa-miR-21-3p")
    regions = [c["specific_region"] for c in r["top3"]]
    assert len(r["top3"]) == CANDIDATES_TOP_N
    assert "CAACACCAGTCGA" in regions
    assert r["top3"][0]["selection"] == "best"


def test_selection_independent_of_generation_order(monkeypatch):
    seq, mid = "UAGCUUAUCAGACUGAUGUUGA", "hsa-miR-21-5p"
    a = [c["sequence"] for c in design_pipeline.run(seq, {}, mid)["top3"]]
    monkeypatch.setattr(fp, "FORWARD_SPECIFIC_LENGTHS", list(reversed(fp.FORWARD_SPECIFIC_LENGTHS)))
    b = [c["sequence"] for c in design_pipeline.run(seq, {}, mid)["top3"]]
    assert a == b


def test_top_is_highest_score_and_ranks_are_sequential():
    r = design_pipeline.run("UAGCAGCACGUAAAUAUUGGCG", {}, "hsa-miR-16-5p")
    top = r["top3"]
    assert [c["rank"] for c in top] == list(range(1, len(top) + 1))
    assert top[0]["total_score"] == max(c["total_score"] for c in top)
