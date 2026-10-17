"""Week2 P4: the 6-nt RT overhang must NOT be presented as a point Tm."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.stemloop_rt import design_stemloop_rt
from algorithm.constants import SHORT_DUPLEX_NT_THRESHOLD, USE_HYBRID_TM


def test_six_nt_overhang_not_reportable_as_point_tm():
    s = design_stemloop_rt("UGAGGUAGUAGGUUGUAUAGUU", {}, "hsa-let-7a-5p")
    assert s["reportable_as_tm"] is False           # 6 < 8 bp
    assert s["tm_hybrid_c"] is None                  # no point Tm
    if USE_HYBRID_TM:
        assert s["dg37_kcal_mol"] is not None        # dG37 reported instead
        assert isinstance(s["tm_hybrid_band_c"], list) and len(s["tm_hybrid_band_c"]) == 2
        assert "not reportable" in s["tm_note"]


def test_threshold_is_eight():
    assert SHORT_DUPLEX_NT_THRESHOLD == 8
