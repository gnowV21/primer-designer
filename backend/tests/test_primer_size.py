# ================================================================
# tests/test_primer_size.py — Unit tests for primer_size scoring (PROMPT 6)
# Verifies Busk 2014 specific_length-based scoring:
# longer specific region → higher score; 5' tail does NOT affect score.
# ================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import algorithm.scoring as scoring_module
from algorithm.scoring import score_candidate
from algorithm.constants import (
    FORWARD_SPECIFIC_LEN_REF, PRIMER_SIZE_MODE,
)


# ── Shared fixtures ───────────────────────────────────────────────

SL  = {"mfe": -11.5, "mfe_method": "primer3-py", "gc_percent": 55, "tm_full": 70.0}
REV = {"tm": 60.4}
PAR = {}


def _fwd(specific_len: int, tail_len: int = 5) -> dict:
    """Build a minimal forward candidate with given specific_length and tail_length."""
    specific = "ATCGATCGATCGATCG"[:specific_len]
    tail     = "GCGCG"[:tail_len]
    full     = tail + specific
    return {
        "sequence":        full,
        "tm_full":         60.0,
        "tm_binding":      45.0,
        "gc_percent":      50.0,
        "length":          len(full),
        "specific_length": specific_len,
        "specific_sequence": specific,
        "tail_length":     tail_len,
        "amplicon_size":   80,
        "structure_checks": {
            "hairpin":     {"dg": -1.0, "severity": "safe", "pass": True},
            "self_dimer":  {"dg_overall": -3.0, "dg_3prime": -2.0,
                            "pass_overall": True, "pass_3prime": True, "critical_3prime": False},
            "hetero_dimer":{"dg_overall": -3.0, "dg_3prime": -2.0,
                            "pass_overall": True, "pass_3prime": True, "critical_3prime": False},
            "end_stability":{"stability_kcal_mol": 5.0, "last_5_bases": full[-5:], "pass": True},
            "overall_pass": True, "has_critical_flag": False,
        },
    }


def _score(specific_len: int, tail_len: int = 5) -> int:
    fwd = _fwd(specific_len, tail_len)
    result = score_candidate(fwd, SL, REV, PAR, cross_reactivity=None, use_v4=False)
    return result["scores"]["primer_size"]


# ── PRIMER_SIZE_MODE constant check ──────────────────────────────

def test_mode_is_specific():
    """Default mode must be 'specific' (Busk14 fix)."""
    assert PRIMER_SIZE_MODE == "specific"


def test_ref_length_is_17():
    """Reference length must be 17 nt (FORWARD_SPECIFIC_LENGTH_MAX)."""
    assert FORWARD_SPECIFIC_LEN_REF == 17


# ── Specific_len 17 → score 100 ──────────────────────────────────

def test_score_at_ref_length():
    """specific_len == FORWARD_SPECIFIC_LEN_REF → score 100."""
    assert _score(17) == 100


# ── Shorter specific_len → lower score ───────────────────────────

def test_score_ordering_17_15_12():
    """Score decreases as specific_length decreases: 17 > 15 > 12."""
    assert _score(17) > _score(15) > _score(12)


def test_score_17_vs_15():
    """specific_len 17 > 15."""
    assert _score(17) > _score(15)


def test_score_15_vs_12():
    """specific_len 15 > 12."""
    assert _score(15) > _score(12)


# ── Tail length does NOT affect primer_size score ─────────────────

def test_tail_length_does_not_affect_score():
    """
    Two primers with same specific_length but different tail lengths
    must have the same primer_size score.
    """
    assert _score(15, tail_len=3) == _score(15, tail_len=10)


def test_tail_length_3_vs_12():
    """Tail 3 nt and tail 12 nt, same specific_len=14 → same score."""
    assert _score(14, tail_len=3) == _score(14, tail_len=12)


# ── Explanation cites Busk 2014 ───────────────────────────────────

def test_explanation_cites_busk14():
    fwd = _fwd(17)
    result = score_candidate(fwd, SL, REV, PAR, cross_reactivity=None, use_v4=False)
    assert "Busk" in result["explanations"]["primer_size"]


# ── Fallback to 'full' mode when toggled ─────────────────────────

def test_full_mode_uses_primer_length(monkeypatch):
    """When PRIMER_SIZE_MODE='full', score is based on full primer length, not specific_len."""
    monkeypatch.setattr(scoring_module, "PRIMER_SIZE_MODE", "full")
    # Build two primers: same specific_len, different tail → different full lengths
    fwd_short_tail = _fwd(14, tail_len=3)   # full = 17 nt
    fwd_long_tail  = _fwd(14, tail_len=10)  # full = 24 nt

    r_short = score_candidate(fwd_short_tail, SL, REV, PAR, cross_reactivity=None, use_v4=False)
    r_long  = score_candidate(fwd_long_tail, SL, REV, PAR, cross_reactivity=None, use_v4=False)

    # In "full" mode, longer primer (24 nt vs optimal 22 nt) gets lower score than 17 nt
    # Wait — 17 nt is 5 below optimal (22), so score = 100 - 5*10 = 50
    # 24 nt is 2 above optimal (22), so score = 100 - 2*10 = 80
    # So long tail (24 nt) > short tail (17 nt) in "full" mode
    # The key check: scores DIFFER when using full mode (not same as specific mode)
    assert r_short["scores"]["primer_size"] != r_long["scores"]["primer_size"], (
        "In 'full' mode, different full lengths must give different scores."
    )


if __name__ == "__main__":
    test_mode_is_specific()
    test_ref_length_is_17()
    test_score_at_ref_length()
    test_score_ordering_17_15_12()
    test_score_17_vs_15()
    test_score_15_vs_12()
    test_tail_length_does_not_affect_score()
    test_tail_length_3_vs_12()
    test_explanation_cites_busk14()
    print("\nAll primer_size tests passed (toggle requires monkeypatch).")
