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
