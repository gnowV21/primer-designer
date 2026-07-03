# ================================================================
# tests/test_gc_clamp.py — Unit tests for GC clamp scoring (PROMPT 1)
# Verifies Busk 2014 miRNA-specific GC clamp logic in scoring.py.
# ================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import algorithm.constants as consts
from algorithm.scoring import score_candidate
from algorithm.constants import (
    GC_CLAMP_SCORE_OPTIMAL, GC_CLAMP_SCORE_1GC_CONSERVATIVE,
    GC_CLAMP_SCORE_WEAK, GC_CLAMP_SCORE_TRIPLE_C,
)


def _make_forward(seq_suffix: str) -> dict:
    prefix = "ATCGATCGATCGATCGATCG"  # 20 nt
    seq = prefix[:22 - len(seq_suffix)] + seq_suffix
    return {
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


def _score_gc_clamp(seq_suffix: str) -> int:
    fwd = _make_forward(seq_suffix)
    stemloop = {"mfe": -11.5, "mfe_method": "primer3-py", "gc_percent": 55, "tm_full": 70.0}
    reverse  = {"tm": 60.4}
    result = score_candidate(fwd, stemloop, reverse, {}, cross_reactivity=None, use_v4=False)
    return result["scores"]["gc_clamp"]


# ── (a) LOCKED cases — no flag dependency ────────────────────────

def test_2gc_optimal():
    """'ACG' → 2 G/C → score 100 (locked, multi-source)."""
    assert _score_gc_clamp("ACG") == GC_CLAMP_SCORE_OPTIMAL


def test_3gc_weak():
    """'GCG' → 3 G/C, not 'CCC' → score 50 (locked)."""
    assert _score_gc_clamp("GCG") == GC_CLAMP_SCORE_WEAK


def test_triple_c_penalty():
    """'CCC' → 3 consecutive C → score 25 (locked, most severe)."""
    assert _score_gc_clamp("CCC") == GC_CLAMP_SCORE_TRIPLE_C


def test_0gc_weak():
    """'ATA' → 0 G/C → score 50 (locked — no anchor)."""
    assert _score_gc_clamp("ATA") == GC_CLAMP_SCORE_WEAK


# ── (b) PENDING cases — GC_CLAMP_1GC_AS_OPTIMAL flag ────────────

def test_1gc_conservative_default():
    """'AAG' → 1 G/C, GC_CLAMP_1GC_AS_OPTIMAL=False → score 75 (conservative default)."""
    original = consts.GC_CLAMP_1GC_AS_OPTIMAL
    consts.GC_CLAMP_1GC_AS_OPTIMAL = False
    import algorithm.scoring as scoring_mod
    scoring_mod.GC_CLAMP_1GC_AS_OPTIMAL = False
    try:
        assert _score_gc_clamp("AAG") == GC_CLAMP_SCORE_1GC_CONSERVATIVE
    finally:
        consts.GC_CLAMP_1GC_AS_OPTIMAL = original
        scoring_mod.GC_CLAMP_1GC_AS_OPTIMAL = original


def test_1gc_busk_style_when_flag_true():
    """'AAG' → 1 G/C, GC_CLAMP_1GC_AS_OPTIMAL=True → score 100 (Busk14-style, monkeypatch)."""
    import algorithm.scoring as scoring_mod
    original = scoring_mod.GC_CLAMP_1GC_AS_OPTIMAL
    scoring_mod.GC_CLAMP_1GC_AS_OPTIMAL = True
    try:
        assert _score_gc_clamp("AAG") == GC_CLAMP_SCORE_OPTIMAL
    finally:
        scoring_mod.GC_CLAMP_1GC_AS_OPTIMAL = original


def test_explanation_cites_busk14_and_idt():
    """Explanation must mention both Busk 2014 and IDT."""
    fwd = _make_forward("ACG")
    stemloop = {"mfe": -11.5, "mfe_method": "primer3-py", "gc_percent": 55, "tm_full": 70.0}
    reverse  = {"tm": 60.4}
    result = score_candidate(fwd, stemloop, reverse, {}, cross_reactivity=None, use_v4=False)
    expl = result["explanations"]["gc_clamp"]
    assert "Busk" in expl
    assert "IDT" in expl


if __name__ == "__main__":
    test_2gc_optimal()
    test_3gc_weak()
    test_triple_c_penalty()
    test_0gc_weak()
    test_1gc_conservative_default()
    test_1gc_busk_style_when_flag_true()
    test_explanation_cites_busk14_and_idt()
    print("\nAll gc_clamp tests passed.")
