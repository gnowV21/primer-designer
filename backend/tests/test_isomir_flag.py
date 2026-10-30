import pytest
# ================================================================
# tests/test_isomir_flag.py
# Unit tests for specificity_check/isomir_flag.py
#
# v2.1 (2026-07-02): isoMiR flag simplified to DB lookup only (spec §6.3).
#   Known miRNA → isomir_discrimination_risk = True (always, regardless of position)
#   Unknown miRNA → isomir_discrimination_risk = False
#
# Removed: geometric risk_window check (was never True for 12–17 nt primers).
# ================================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.specificity_check.isomir_flag import check_isomir_flag


# ── Case 1: Known isomiR miRNA — always flags True ────────────────

def test_isomir_flag_triggers_for_known_mirna():
    """hsa-miR-21-5p is in the DB → risk=True regardless of primer position."""
    result = check_isomir_flag(
        mirna_name="hsa-miR-21-5p",
        forward_3prime_position=15,
    )
    assert result["isomir_discrimination_risk"] is True
    assert result["mirna_name"] == "hsa-miR-21-5p"


def test_known_mirna_short_position_still_true():
    """Position within old risk_window — still True under new DB-only logic."""
    result = check_isomir_flag(
        mirna_name="hsa-miR-21-5p",
        forward_3prime_position=2,
    )
    assert result["isomir_discrimination_risk"] is True


def test_known_mirna_long_position_still_true():
    """Typical specific_length=15 → still True (geometric check removed)."""
    result = check_isomir_flag(
        mirna_name="hsa-miR-21-5p",
        forward_3prime_position=15,
    )
    assert result["isomir_discrimination_risk"] is True


def test_miR10a_known_flags_true():
    """hsa-miR-10a-5p is in the DB → True for any position."""
    for pos in [3, 4, 12, 17]:
        r = check_isomir_flag("hsa-miR-10a-5p", forward_3prime_position=pos)
        assert r["isomir_discrimination_risk"] is True, f"Expected True at pos {pos}"


# ── Case 2: Unknown miRNA ─────────────────────────────────────────

def test_unknown_mirna_no_risk():
    """A miRNA not in the DB → risk=False with informational note."""
    result = check_isomir_flag(
        mirna_name="hsa-miR-UNKNOWN-5p",
        forward_3prime_position=12,
    )
    assert result["isomir_discrimination_risk"] is False
    assert result["risk_window_nt"] is None
    assert "No known 5' isomiR" in result["note"]


# ── Output structure ──────────────────────────────────────────────

def test_output_has_required_keys_known():
    """All required keys present for a known miRNA."""
    result = check_isomir_flag("hsa-miR-21-5p", forward_3prime_position=12)
    for key in ("isomir_discrimination_risk", "mirna_name", "forward_3prime_position",
                "known_5prime_shift_nt", "risk_window_nt", "note", "co_amplification_warning"):
        assert key in result, f"Missing key: {key}"


def test_output_has_required_keys_unknown():
    """All required keys present for an unknown miRNA."""
    result = check_isomir_flag("hsa-miR-UNKNOWN-5p", forward_3prime_position=12)
    for key in ("isomir_discrimination_risk", "mirna_name", "forward_3prime_position",
                "risk_window_nt", "note", "data_warning"):
        assert key in result, f"Missing key: {key}"


def test_output_boolean_type():
    result = check_isomir_flag("hsa-miR-21-5p", 3)
    assert isinstance(result["isomir_discrimination_risk"], bool)


def test_co_amplification_warning_present_for_known():
    """co_amplification_warning must be a non-empty string for known miRNAs."""
    result = check_isomir_flag("hsa-miR-21-5p", 12)
    assert isinstance(result.get("co_amplification_warning"), str)
    assert len(result["co_amplification_warning"]) > 0


if __name__ == "__main__":
    test_isomir_flag_triggers_for_known_mirna()
    test_known_mirna_short_position_still_true()
    test_known_mirna_long_position_still_true()
    test_miR10a_known_flags_true()
    test_unknown_mirna_no_risk()
    test_output_has_required_keys_known()
    test_output_has_required_keys_unknown()
    test_output_boolean_type()
    test_co_amplification_warning_present_for_known()
    print("\nAll isomir_flag tests passed.")


# ── Week2 C11: 3' isomiR flag ─────────────────────────────────────
from algorithm.specificity_check import isomir_flag as _iso3


_FAKE_META = {"coverage_warning": "Human only.", "source": {"name": "isomiRdb", "pmid": "36243964"}}


def _entry(f):
    return {"median_3prime_fraction": f, "iqr_3prime_fraction": [f - 0.05, f + 0.05],
            "pooled_3prime_fraction": f, "n_samples_expressed": 1000,
            "top_3prime_variants": [{"sequence_dna": "ACGT", "label": "lv3p|lv3pT|lv3p#-1",
                                     "pooled_share": 0.3}]}


def test_3prime_no_entry_returns_false(monkeypatch):
    monkeypatch.setattr(_iso3, "_DB3_CACHE", {"_metadata": _FAKE_META})
    res = _iso3.check_3prime_isomir_flag("hsa-miR-NOPE-5p", overhang_len=6)
    assert res["three_prime_isomir_risk"] is False
    assert res["level"] == "no_data"
    assert "not evidence" in res["note"]


def test_3prime_majority_isoforms_raise_warning(monkeypatch):
    monkeypatch.setattr(_iso3, "_DB3_CACHE", {"_metadata": _FAKE_META, "hsa-miR-T-3p": _entry(0.89)})
    res = _iso3.check_3prime_isomir_flag("hsa-miR-T-3p", overhang_len=6)
    assert res["three_prime_isomir_risk"] is True and res["level"] == "high"
    assert "89%" in res["warning"] and "minority" in res["warning"]
    assert res["source"] == "isomiRdb (PMID 36243964)"


@pytest.mark.parametrize("f, level", [(0.49, "moderate"), (0.20, "moderate"), (0.19, "low")])
def test_3prime_tiers_below_majority_are_informational(monkeypatch, f, level):
    monkeypatch.setattr(_iso3, "_DB3_CACHE", {"_metadata": _FAKE_META, "hsa-miR-T-3p": _entry(f)})
    res = _iso3.check_3prime_isomir_flag("hsa-miR-T-3p")
    assert res["three_prime_isomir_risk"] is False
    assert res["level"] == level and res["warning"] is None and res["summary"]



def test_3prime_abundance_only_entry_is_no_data(monkeypatch):
    monkeypatch.setattr(_iso3, "_DB3_CACHE", {"_metadata": _FAKE_META,
                                              "hsa-miR-A-5p": {"median_total_rpm": 5.0,
                                                               "abundance_percentile": 50.0}})
    res = _iso3.check_3prime_isomir_flag("hsa-miR-A-5p")
    assert res["level"] == "no_data" and res["three_prime_isomir_risk"] is False


# ── fold-change bias warning (Nejad 2018) ────────────────────────

def test_fold_change_bias_fires_on_large_variable_isoform_pool():
    """miR-222-3p is Nejad 2018's own example: a big 3'-isoform pool whose share
    also swings between samples."""
    from algorithm.specificity_check.isomir_flag import check_3prime_isomir_flag
    r = check_3prime_isomir_flag("hsa-miR-222-3p", 6)
    assert r["fold_change_bias_risk"] is True
    w = r["fold_change_bias_warning"]
    assert "Nejad" in w and "fold change" in w
    # Qualitative only — never a numeric bias factor.
    assert "×" not in w and "fold-change of" not in w


def test_fold_change_bias_needs_both_size_and_spread():
    from algorithm.specificity_check.isomir_flag import _fold_change_bias_warning
    assert _fold_change_bias_warning("x", 0.05, 0.0, 0.9) is None    # pool too small
    assert _fold_change_bias_warning("x", 0.80, 0.78, 0.82) is None  # stable share
    assert _fold_change_bias_warning("x", 0.40, 0.25, 0.60) is not None


def test_fold_change_bias_absent_without_data():
    from algorithm.specificity_check.isomir_flag import check_3prime_isomir_flag
    r = check_3prime_isomir_flag("mmu-miR-99999-5p", 6)
    assert r["level"] == "no_data"
    assert r.get("fold_change_bias_risk") in (None, False)
