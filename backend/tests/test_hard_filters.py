# ================================================================
# tests/test_hard_filters.py — Unit tests for hard_filters.py
# (PROMPT 3). Each rule has 1 pass + 1 reject case.
# Toggle: HARD_FILTER_ENABLED=False → no rejections.
# ================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import algorithm.hard_filters as hf_module
from algorithm.hard_filters import apply_hard_filters
from algorithm.constants import DIMER_FULL_DG_CRITICAL, HAIRPIN_TM_HARD_MAX


def _candidate(sd_full=0.0, hd_full=0.0, has_critical_flag=False, hairpin_severity="safe",
               hairpin_tm=0.0):
    """Build a minimal candidate dict with the required structure_checks keys."""
    # No dg_cofold key → full_dimer_dg() uses the primer3 dg_overall fallback
    # (ViennaRNA unavailable). The RNAcofold path is in test_dimer_cofold.py.
    return {
        "sequence": "ATCGATCGATCGATCGATCGACG",
        "structure_checks": {
            "self_dimer":   {"dg_overall": sd_full,  "dg_3prime": -2.0},
            "hetero_dimer": {"dg_overall": hd_full,  "dg_3prime": -2.0},
            "has_critical_flag": has_critical_flag,
            "hairpin": {"severity": hairpin_severity, "tm": hairpin_tm,
                        "dg": -7.0 if hairpin_severity == "critical" else -1.0},
        },
    }


# ── Rule 1: Full-structure dimer ΔG < DIMER_FULL_DG_CRITICAL ─────

def test_rule1_reject_sd_full():
    c = _candidate(sd_full=DIMER_FULL_DG_CRITICAL - 0.5)  # e.g. -9.5
    reasons = apply_hard_filters(c)
    assert any("hard_dimer_full_dg" in r for r in reasons)


def test_rule1_reject_hd_full():
    c = _candidate(hd_full=DIMER_FULL_DG_CRITICAL - 1.0)  # -10.0
    reasons = apply_hard_filters(c)
    assert any("hard_dimer_full_dg" in r for r in reasons)


def test_rule1_pass():
    c = _candidate(sd_full=-8.0, hd_full=-5.0)  # both > -9
    reasons = apply_hard_filters(c)
    assert not any("hard_dimer_full_dg" in r for r in reasons)


# ── Rule 2: 3'-end critical (has_critical_flag) ───────────────────

def test_rule2_reject_3prime_critical():
    c = _candidate(has_critical_flag=True)
    reasons = apply_hard_filters(c)
    assert "hard_dimer_3prime_critical" in reasons


def test_rule2_pass():
    c = _candidate(has_critical_flag=False)
    reasons = apply_hard_filters(c)
    assert "hard_dimer_3prime_critical" not in reasons


# ── Rule 3: hairpin Tm ≥ HAIRPIN_TM_HARD_MAX (47 °C, Primer3 default) — since 3.7.0 ──

def test_rule3_reject_hairpin_tm_at_limit():
    reasons = apply_hard_filters(_candidate(hairpin_tm=HAIRPIN_TM_HARD_MAX))
    assert any(r.startswith("hard_hairpin_tm") for r in reasons)


def test_rule3_reject_hairpin_tm_above_limit():
    reasons = apply_hard_filters(_candidate(hairpin_tm=72.0))   # ebv-miR-BART15 primer of 3.6.0
    assert any(r.startswith("hard_hairpin_tm") for r in reasons)


def test_rule3_pass_hairpin_tm_below_limit():
    reasons = apply_hard_filters(_candidate(hairpin_tm=HAIRPIN_TM_HARD_MAX - 0.1))
    assert not any(r.startswith("hard_hairpin") for r in reasons)


def test_rule3_ignores_dg_severity():
    """The old ΔG rule (severity 'critical', ΔG ≤ −6 at Ta) no longer rejects on its own."""
    reasons = apply_hard_filters(_candidate(hairpin_severity="critical", hairpin_tm=30.0))
    assert not any(r.startswith("hard_hairpin") for r in reasons)


def test_rule3_no_structure():
    """primer3 reports Tm 0 when no hairpin forms."""
    assert apply_hard_filters(_candidate(hairpin_tm=0.0)) == []


# ── Multiple rules can fire simultaneously ────────────────────────

def test_multiple_rules():
    c = _candidate(sd_full=-10.0, has_critical_flag=True, hairpin_tm=60.0)
    reasons = apply_hard_filters(c)
    assert len(reasons) == 3


# ── Toggle: HARD_FILTER_ENABLED = False → no rejections ──────────

def test_toggle_disabled_no_rejections(monkeypatch):
    monkeypatch.setattr(hf_module, "HARD_FILTER_ENABLED", False)
    c = _candidate(sd_full=-15.0, has_critical_flag=True, hairpin_tm=60.0)
    reasons = apply_hard_filters(c)
    assert reasons == []


# ── Clean candidate passes all rules ─────────────────────────────

def test_all_pass():
    c = _candidate(sd_full=-5.0, hd_full=-4.0, has_critical_flag=False, hairpin_severity="safe")
    assert apply_hard_filters(c) == []


if __name__ == "__main__":
    test_rule1_reject_sd_full()
    test_rule1_reject_hd_full()
    test_rule1_pass()
    test_rule2_reject_3prime_critical()
    test_rule2_pass()
    test_rule3_reject_hairpin_critical()
    test_rule3_pass_hairpin_warning()
    test_rule3_pass_hairpin_safe()
    test_multiple_rules()
    test_all_pass()
    print("\nAll hard_filters tests passed (toggle requires monkeypatch).")


# ── Real primer3 Tm and the scoring side ──────────────────────────

def test_real_hairpin_tm_from_structure_checks():
    """ebv-miR-BART15 forward primer chosen by 3.6.0 has a hairpin Tm ≈ 72 °C (primer3)."""
    from algorithm.constants import UNIVERSAL_REVERSE
    from algorithm.structure_check import run_all_structure_checks
    sc = run_all_structure_checks("ACCACCGTCAGTGGTTTTGTT", UNIVERSAL_REVERSE, {})
    assert sc["hairpin"]["tm"] >= HAIRPIN_TM_HARD_MAX
    assert sc["hairpin"]["severity"] in ("safe", "acceptable")   # the ΔG tiers missed it
    reasons = apply_hard_filters({"structure_checks": sc})
    assert any(r.startswith("hard_hairpin_tm") for r in reasons)


def test_hairpin_score_zero_when_tm_at_limit():
    from algorithm.scoring import score_candidate
    seq = "ATCGATCGATCGATCGATCGACG"
    def fwd(tm):
        return {
            "sequence": seq, "tm_full": 60.0, "tm_binding": 45.0, "gc_percent": 50.0,
            "length": len(seq), "specific_length": 14, "specific_sequence": seq[-14:],
            "tail_length": len(seq) - 14, "amplicon_size": 80,
            "structure_checks": {
                "hairpin": {"dg": -1.0, "severity": "safe", "pass": True, "tm": tm},
                "self_dimer": {"dg_overall": -2.0, "dg_3prime": -2.0, "pass_overall": True,
                               "pass_3prime": True, "critical_3prime": False},
                "hetero_dimer": {"dg_overall": -2.0, "dg_3prime": -2.0, "pass_overall": True,
                                 "pass_3prime": True, "critical_3prime": False},
                "end_stability": {"stability_kcal_mol": 5.0, "last_5_bases": seq[-5:], "pass": True},
                "overall_pass": True, "has_critical_flag": False,
            },
        }
    args = ({"mfe": -11.5, "mfe_method": "primer3-py", "gc_percent": 55, "tm_full": 70.0}, {"tm": 60.4}, {})
    hot = score_candidate(fwd(HAIRPIN_TM_HARD_MAX), *args, cross_reactivity=None, use_v4=False)
    cold = score_candidate(fwd(40.0), *args, cross_reactivity=None, use_v4=False)
    assert hot["scores"]["hairpin_penalty"] == 0
    assert cold["scores"]["hairpin_penalty"] == 100
    assert "CRITICAL" in hot["explanations"]["hairpin_penalty"]
