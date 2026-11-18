"""
test_assay_screen.py — overhang_collision.assay_screen, the S2/S3 input of the tiered
system (SPEC_scoring_tiered_4.0.0 §3.1). Must agree with check_overhang_collision
wherever that function reports an exact ΔCq.
"""
from algorithm.specificity_check.overhang_collision import assay_screen, check_overhang_collision

_LET7A = "UGAGGUAGUAGGUUGUAUAGUU"
_MIR21 = "UAGCUUAUCAGACUGAUGUUGA"


def test_min_delta_cq_matches_the_collision_screen():
    scr = assay_screen(_LET7A, "hsa-let-7a-5p", {}, 6, [12, 16])
    for L in (12, 16):
        oc = check_overhang_collision(mature_seq=_LET7A, mirna_name="hsa-let-7a-5p",
                                      params={}, overhang_len=6, forward_specific_len=L)
        worst = oc["collisions"][0]
        assert scr[L]["worst"] == worst["mirna"] == "hsa-let-7d-5p"
        assert scr[L]["min_delta_cq"] == worst["delta_cq"]


def test_tm_margin_is_small_for_a_co_amplified_paralog():
    scr = assay_screen(_LET7A, "hsa-let-7a-5p", {}, 6, [16])[16]
    assert scr["tm_margin_worst"] == "hsa-let-7d-5p"
    assert scr["tm_margin"] < 5.0


def test_specific_mirna_is_resolved():
    scr = assay_screen(_MIR21, "hsa-miR-21-5p", {}, 6, [16])[16]
    assert scr["min_delta_cq"] is None or scr["min_delta_cq"] >= 7.0
    assert scr["tm_margin"] is None or scr["tm_margin"] >= 10.0
