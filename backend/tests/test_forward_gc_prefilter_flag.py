"""
test_forward_gc_prefilter_flag.py — generate_forward_candidates(gc_prefilter=False)
for the tiered system (SPEC_scoring_tiered_4.0.0 QD 15, §5).
"""
from algorithm.forward_primer import generate_forward_candidates

_MIR21 = "UAGCUUAUCAGACUGAUGUUGA"
_MIR326 = "CCUCUGGGCCCUUCCUCCAG"     # GC 70 %: no V4 candidate (D-8)
_MIR1_5P = "ACAUACUUCUUUAUAUGCCCAU"  # AT-rich, 0 G/C at the 3' end of every prefix


def test_default_is_v4_behaviour():
    a, _ = generate_forward_candidates(_MIR21, {})
    b, _ = generate_forward_candidates(_MIR21, {}, gc_prefilter=True)
    assert [c["sequence"] for c in a] == [c["sequence"] for c in b]


def test_v4_rejects_gc_rich_and_at_rich_mirnas():
    assert generate_forward_candidates(_MIR326, {})[0] == []
    assert generate_forward_candidates(_MIR1_5P, {})[0] == []


def test_without_gc_prefilter_the_failed_mirnas_get_candidates():
    for seq in (_MIR326, _MIR1_5P):
        cands, log = generate_forward_candidates(seq, {}, gc_prefilter=False)
        assert cands
        assert not {r["reason"] for r in log} & {"gc_out_of_range", "gc_clamp_fail",
                                                 "gc_end_window_fail"}


def test_other_prefilter_rules_still_apply():
    cands, _ = generate_forward_candidates(_MIR326, {}, gc_prefilter=False)
    for c in cands:
        assert 58.0 <= c["tm_full"] <= 62.0
        assert 18 <= c["length"] <= 27


# hsa-miR-1269a: without the GC pre-filter, GC-unbalanced tails nearest in Tm used to
# push its V4 #1 (3.8.2) out of the 20 tails kept for its specific length.
_MIR1269A = "CUGGACUGAGCCGUGCUACUGG"
_MIR1269A_V4_TOP1 = "GACGTCAACTGGACTGAGCC"


def test_tiered_pool_sorts_gc_level_first_and_keeps_the_v4_primer():
    from algorithm.tiered_scoring import f1_gc
    cands, _ = generate_forward_candidates(_MIR1269A, {}, gc_prefilter=False)
    v4, _ = generate_forward_candidates(_MIR1269A, {})
    assert _MIR1269A_V4_TOP1 in {c["sequence"] for c in cands}
    by_len = {}
    for c in cands:
        by_len.setdefault(c["specific_length"], []).append(f1_gc(c["gc_percent"]))
    for levels in by_len.values():
        assert levels == sorted(levels, reverse=True)
    # where 20 GC-balanced tails exist, the tiered pool of that length is the V4 pool
    for L in {c["specific_length"] for c in v4}:
        t = [c["sequence"] for c in cands if c["specific_length"] == L]
        v = [c["sequence"] for c in v4 if c["specific_length"] == L]
        if len(v) == 20:
            assert sorted(t) == sorted(v)
