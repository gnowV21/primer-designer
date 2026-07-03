# ================================================================
# tests/test_hard_filters.py — Unit tests for hard_filters.py
# (PROMPT 3). Each rule has 1 pass + 1 reject case.
# Toggle: HARD_FILTER_ENABLED=False → no rejections.
# ================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import algorithm.hard_filters as hf_module
from algorithm.hard_filters import apply_hard_filters
from algorithm.constants import DIMER_FULL_DG_CRITICAL


def _candidate(sd_full=0.0, hd_full=0.0, has_critical_flag=False, hairpin_severity="safe"):
    """Build a minimal candidate dict with the required structure_checks keys."""
    return {
        "sequence": "ATCGATCGATCGATCGATCGACG",
        "structure_checks": {
            "self_dimer":   {"dg_overall": sd_full,  "dg_3prime": -2.0},
            "hetero_dimer": {"dg_overall": hd_full,  "dg_3prime": -2.0},
            "has_critical_flag": has_critical_flag,
            "hairpin": {"severity": hairpin_severity, "dg": -7.0 if hairpin_severity == "critical" else -1.0},
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


# ── Rule 3: Hairpin severity == 'critical' ────────────────────────

def test_rule3_reject_hairpin_critical():
    c = _candidate(hairpin_severity="critical")
    reasons = apply_hard_filters(c)
    assert any("hard_hairpin_critical" in r for r in reasons)


def test_rule3_pass_hairpin_warning():
    c = _candidate(hairpin_severity="warning")
    reasons = apply_hard_filters(c)
    assert not any("hard_hairpin_critical" in r for r in reasons)


def test_rule3_pass_hairpin_safe():
    c = _candidate(hairpin_severity="safe")
    reasons = apply_hard_filters(c)
    assert not any("hard_hairpin_critical" in r for r in reasons)


# ── Multiple rules can fire simultaneously ────────────────────────

def test_multiple_rules():
    c = _candidate(sd_full=-10.0, has_critical_flag=True, hairpin_severity="critical")
    reasons = apply_hard_filters(c)
    assert len(reasons) == 3


# ── Toggle: HARD_FILTER_ENABLED = False → no rejections ──────────

def test_toggle_disabled_no_rejections(monkeypatch):
    monkeypatch.setattr(hf_module, "HARD_FILTER_ENABLED", False)
    c = _candidate(sd_full=-15.0, has_critical_flag=True, hairpin_severity="critical")
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
