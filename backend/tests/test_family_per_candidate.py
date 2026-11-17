"""
test_family_per_candidate.py — REV-23 (4.0.0): family_discrimination is scored on each
candidate's OWN forward specific length.

Before 4.0.0 the assay-level collision was computed once, on the winner's length, so
every candidate of a design got the same family_discrimination value and the criterion
could not influence which primer was chosen.

hsa-miR-100-5p (miRBase 22.1): against hsa-miR-99a-5p the assay is CO-AMPLIFIED at
specific lengths 12–15 and DISCRIMINATED at 16 (benchmark/thesis_freeze_impact.json).
"""
from algorithm.constants import ASSAY_LABEL_SCORE
from algorithm.design_pipeline import run
from algorithm.specificity_check.overhang_collision import check_overhang_collision

_MIR100 = "AACCCGUAGAUCCGAACUUGUG"
_NAME = "hsa-miR-100-5p"


def _label(length):
    oc = check_overhang_collision(mature_seq=_MIR100, mirna_name=_NAME, params={},
                                  overhang_len=6, forward_specific_len=length)
    return oc["worst_assay_label"]


def test_label_depends_on_specific_length():
    assert _label(12) == "CO-AMPLIFIED"
    assert _label(16) == "DISCRIMINATED"


def test_each_returned_set_is_scored_on_its_own_length():
    res = run(_MIR100, {}, mirna_name=_NAME)
    sets = res["top3"]
    assert sets
    for p in sets:
        expected = ASSAY_LABEL_SCORE[_label(p["specific_length"])]
        assert p["scores"]["family_discrimination"] == expected, p["specific_length"]


def test_design_level_collision_is_the_top_set_length():
    res = run(_MIR100, {}, mirna_name=_NAME)
    oc = res["specificity_warnings"]["overhang_collision"]
    assert oc["forward_specific_len"] == res["top3"][0]["specific_length"]
