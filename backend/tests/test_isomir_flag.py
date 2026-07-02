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
