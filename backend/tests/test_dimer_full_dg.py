# ================================================================
# tests/test_dimer_full_dg.py — Unit tests for full-structure dimer
# threshold in scoring.py (PROMPT 2).
# Kang 2017 (DOI 10.1261/rna.061150.117): ΔG_total < -9 → critical.
# ================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.scoring import score_candidate
from algorithm.constants import DIMER_FULL_DG_CRITICAL


def _build_forward(seq: str, sd_full: float, hd_full: float,
                   sd_3prime: float = -2.0, hd_3prime: float = -2.0,
                   has_critical_flag: bool = False) -> dict:
    return {
        "sequence": seq,
        "tm_full": 60.0, "tm_binding": 45.0, "gc_percent": 50.0,
        "length": len(seq), "specific_length": 14,
        "specific_sequence": seq[-14:], "tail_length": len(seq) - 14,
        "amplicon_size": 80,
        "structure_checks": {
            "hairpin":     {"dg": -1.0, "severity": "safe", "pass": True},
            "self_dimer":  {
                "dg_overall": sd_full, "dg_3prime": sd_3prime,
                "pass_overall": sd_full > -6.0, "pass_3prime": sd_3prime > -5.0,
                "critical_3prime": sd_3prime <= -5.0,
            },
            "hetero_dimer":{
                "dg_overall": hd_full, "dg_3prime": hd_3prime,
                "pass_overall": hd_full > -6.0, "pass_3prime": hd_3prime > -5.0,
                "critical_3prime": hd_3prime <= -5.0,
            },
            "end_stability":{"stability_kcal_mol": 5.0, "last_5_bases": seq[-5:], "pass": True},
            "overall_pass": not has_critical_flag, "has_critical_flag": has_critical_flag,
        },
    }


SEQ  = "ATCGATCGATCGATCGATCGACG"  # 23 nt, last3="ACG" (2 G/C → optimal clamp)
SL   = {"mfe": -11.5, "mfe_method": "primer3-py", "gc_percent": 55, "tm_full": 70.0}
REV  = {"tm": 60.4}
PAR  = {}


def _dimer_score(sd_full, hd_full, **kw):
    fwd = _build_forward(SEQ, sd_full, hd_full, **kw)
    result = score_candidate(fwd, SL, REV, PAR, cross_reactivity=None, use_v4=False)
    return result["scores"]["dimer_penalty"]


# ── Full-structure ΔG = -10 → below -9 threshold → score 0 ──────

def test_full_dg_minus10_sd_critical():
    """Self-dimer full ΔG = -10 → below DIMER_FULL_DG_CRITICAL → score 0."""
    assert _dimer_score(-10.0, -3.0) == 0


def test_full_dg_minus10_hd_critical():
    """Hetero-dimer full ΔG = -10 → score 0."""
    assert _dimer_score(-3.0, -10.0) == 0


def test_both_full_dg_minus10_critical():
    """Both full ΔG = -10 → score 0."""
    assert _dimer_score(-10.0, -10.0) == 0


# ── Full-structure ΔG = -8 → ABOVE threshold → not critical by full rule ─

def test_full_dg_minus8_not_critical_by_full():
    """Full ΔG = -8 (> -9) with safe 3'-end → NOT forced to 0 by full-structure rule."""
    score = _dimer_score(-8.0, -3.0)
    assert score > 0, f"Expected score > 0, got {score}"


# ── 3'-end critical still forces score 0 regardless of full ΔG ──

def test_3prime_critical_overrides():
    """has_critical_flag=True still forces dimer_score = 0 even with benign full ΔG."""
    assert _dimer_score(-3.0, -3.0, has_critical_flag=True) == 0


# ── 3'-end OK + full ΔG benign → normal scoring ──────────────────

def test_benign_both():
    """sd_full=-3, hd_full=-3, 3'-end safe → score 100 (worst 3'-end > -4)."""
    assert _dimer_score(-3.0, -3.0) == 100


# ── DIMER_FULL_DG_CRITICAL constant is -9.0 ──────────────────────

def test_critical_constant_value():
    assert DIMER_FULL_DG_CRITICAL == -9.0


# ── Explanation mentions Kang17 ───────────────────────────────────

def test_explanation_cites_kang17():
    fwd = _build_forward(SEQ, -10.0, -3.0)
    result = score_candidate(fwd, SL, REV, PAR, cross_reactivity=None, use_v4=False)
    assert "Kang" in result["explanations"]["dimer_penalty"]


if __name__ == "__main__":
    test_full_dg_minus10_sd_critical()
    test_full_dg_minus10_hd_critical()
    test_both_full_dg_minus10_critical()
    test_full_dg_minus8_not_critical_by_full()
    test_3prime_critical_overrides()
    test_benign_both()
    test_critical_constant_value()
    test_explanation_cites_kang17()
    print("\nAll dimer_full_dg tests passed.")
