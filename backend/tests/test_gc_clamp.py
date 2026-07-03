# ================================================================
# tests/test_gc_clamp.py — Unit tests for GC clamp scoring (PROMPT 1)
# Verifies Busk 2014 miRNA-specific GC clamp logic in scoring.py.
# ================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.scoring import score_candidate
from algorithm.constants import (
    GC_CLAMP_SCORE_OPTIMAL, GC_CLAMP_SCORE_WEAK, GC_CLAMP_SCORE_TRIPLE_C,
)


def _score_gc_clamp(seq_suffix: str) -> int:
    """
    Build a minimal candidate whose last 3 nt are seq_suffix and score it.
    We pad the sequence to a realistic length (22 nt) with a fixed ATCG prefix.
    """
    prefix = "ATCGATCGATCGATCGATCG"  # 20 nt
    seq = prefix[:22 - len(seq_suffix)] + seq_suffix
    forward = {
        "sequence": seq,
        "tm_full": 60.0,
        "tm_binding": 45.0,
        "gc_percent": 50.0,
        "length": len(seq),
        "specific_length": 14,
        "specific_sequence": seq[-14:],
        "tail_length": len(seq) - 14,
        "amplicon_size": 80,
        "structure_checks": {
            "hairpin":     {"dg": -1.0, "severity": "safe", "pass": True},
            "self_dimer":  {"dg_overall": -3.0, "dg_3prime": -2.0,
                            "pass_overall": True, "pass_3prime": True, "critical_3prime": False},
            "hetero_dimer":{"dg_overall": -3.0, "dg_3prime": -2.0,
                            "pass_overall": True, "pass_3prime": True, "critical_3prime": False},
            "end_stability":{"stability_kcal_mol": 5.0, "last_5_bases": seq[-5:], "pass": True},
            "overall_pass": True, "has_critical_flag": False,
        },
    }
    stemloop = {"mfe": -11.5, "mfe_method": "primer3-py", "gc_percent": 55, "tm_full": 70.0}
    reverse  = {"tm": 60.4}
    params   = {}
    result = score_candidate(forward, stemloop, reverse, params, cross_reactivity=None, use_v4=False)
    return result["scores"]["gc_clamp"]


# ── Test cases per Busk14 ─────────────────────────────────────────

def test_2gc_optimal():
    """'ACG' → 2 G/C → score 100 (optimal)."""
    assert _score_gc_clamp("ACG") == GC_CLAMP_SCORE_OPTIMAL


def test_1gc_optimal():
    """'AAG' → 1 G/C → score 100 (optimal per Busk14)."""
    assert _score_gc_clamp("AAG") == GC_CLAMP_SCORE_OPTIMAL


def test_3gc_weak():
    """'GCG' → 3 G/C, not 'CCC' → score 50 (weak)."""
    assert _score_gc_clamp("GCG") == GC_CLAMP_SCORE_WEAK


def test_0gc_weak():
    """'ATA' → 0 G/C → score 50 (weak — no anchor)."""
    assert _score_gc_clamp("ATA") == GC_CLAMP_SCORE_WEAK


def test_triple_c_penalty():
    """'CCC' → 3 consecutive C → score 25 (triple-C penalty)."""
    assert _score_gc_clamp("CCC") == GC_CLAMP_SCORE_TRIPLE_C


def test_explanation_cites_busk14():
    """Explanation must mention Busk 2014."""
    prefix = "ATCGATCGATCGATCGATCG"
    seq = prefix[:20] + "ACG"
    forward = {
        "sequence": seq,
        "tm_full": 60.0, "tm_binding": 45.0, "gc_percent": 50.0,
        "length": len(seq), "specific_length": 14,
        "specific_sequence": seq[-14:], "tail_length": len(seq) - 14,
        "amplicon_size": 80,
        "structure_checks": {
            "hairpin":     {"dg": -1.0, "severity": "safe", "pass": True},
            "self_dimer":  {"dg_overall": -3.0, "dg_3prime": -2.0,
                            "pass_overall": True, "pass_3prime": True, "critical_3prime": False},
            "hetero_dimer":{"dg_overall": -3.0, "dg_3prime": -2.0,
                            "pass_overall": True, "pass_3prime": True, "critical_3prime": False},
            "end_stability":{"stability_kcal_mol": 5.0, "last_5_bases": seq[-5:], "pass": True},
            "overall_pass": True, "has_critical_flag": False,
        },
    }
    stemloop = {"mfe": -11.5, "mfe_method": "primer3-py", "gc_percent": 55, "tm_full": 70.0}
    reverse  = {"tm": 60.4}
    result = score_candidate(forward, stemloop, reverse, {}, cross_reactivity=None, use_v4=False)
    assert "Busk" in result["explanations"]["gc_clamp"]


if __name__ == "__main__":
    test_2gc_optimal()
    test_1gc_optimal()
    test_3gc_weak()
    test_0gc_weak()
    test_triple_c_penalty()
    test_explanation_cites_busk14()
    print("\nAll gc_clamp tests passed.")
