# ================================================================
# tests/test_isomir_flag.py
# Unit tests for specificity_check/isomir_flag.py
#
# Case 1: miRNA with known 5' isomiR, forward primer 3' end in risk window
# Case 2: miRNA with known 5' isomiR, forward primer 3' end beyond risk window
# ================================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.specificity_check.isomir_flag import check_isomir_flag


# ── Case 1: Risk window hit ───────────────────────────────────────

def test_isomir_risk_when_primer_in_window():
    """
    hsa-miR-21-5p has a known 5' isomiR (±1 nt), risk_window_nt=2.
    A forward primer with specific_length=2 has its 3' end at position 2
    → within the risk window → flag should be True.
    """
    result = check_isomir_flag(
        mirna_name="hsa-miR-21-5p",
        forward_3prime_position=2,
    )
    assert result["isomir_discrimination_risk"] is True
    assert result["mirna_name"] == "hsa-miR-21-5p"
    assert result["forward_3prime_position"] == 2
    assert result["risk_window_nt"] is not None
    assert "Forward primer 3' end is at position" in result["note"]


def test_isomir_risk_at_boundary():
    """
    Position exactly at risk_window_nt (2 for miR-21) → still in window → True.
    """
    result = check_isomir_flag(
        mirna_name="hsa-miR-21-5p",
        forward_3prime_position=2,
    )
    assert result["isomir_discrimination_risk"] is True


# ── Case 2: Beyond risk window ────────────────────────────────────

def test_no_isomir_risk_when_primer_beyond_window():
    """
    hsa-miR-21-5p, risk_window=2.
    Forward primer with specific_length=12 has 3' end at position 12
    → beyond the 2-nt risk window → flag should be False.
    """
    result = check_isomir_flag(
        mirna_name="hsa-miR-21-5p",
        forward_3prime_position=12,
    )
    assert result["isomir_discrimination_risk"] is False
    assert "beyond the" in result["note"]


def test_no_isomir_risk_for_long_primer():
    """Standard primer (specific_length=15) should be well beyond any risk window."""
    result = check_isomir_flag(
        mirna_name="hsa-miR-21-5p",
        forward_3prime_position=15,
    )
    assert result["isomir_discrimination_risk"] is False


# ── Case 3: Unknown miRNA ─────────────────────────────────────────

def test_unknown_mirna_no_risk():
    """A miRNA not in the DB should return risk=False with informational note."""
    result = check_isomir_flag(
        mirna_name="hsa-miR-UNKNOWN-5p",
        forward_3prime_position=12,
    )
    assert result["isomir_discrimination_risk"] is False
    assert result["risk_window_nt"] is None
    assert "No known 5' isomiR" in result["note"]


# ── Output structure ──────────────────────────────────────────────

def test_output_has_required_keys():
    """All required keys must be present regardless of outcome."""
    for position in [1, 5, 15]:
        result = check_isomir_flag(
            mirna_name="hsa-miR-21-5p",
            forward_3prime_position=position,
        )
        for key in ("isomir_discrimination_risk", "mirna_name", "forward_3prime_position",
                    "risk_window_nt", "note", "co_amplification_warning"):
            assert key in result, f"Missing key: {key} at position {position}"

def test_output_boolean_type():
    result = check_isomir_flag("hsa-miR-21-5p", 3)
    assert isinstance(result["isomir_discrimination_risk"], bool)

def test_miR10a_higher_risk_window():
    """
    hsa-miR-10a-5p has risk_window_nt=3 (5' +2 isomir).
    Position 3 → in risk window → True.
    Position 4 → beyond → False.
    """
    in_window = check_isomir_flag("hsa-miR-10a-5p", forward_3prime_position=3)
    out_window = check_isomir_flag("hsa-miR-10a-5p", forward_3prime_position=4)
    assert in_window["isomir_discrimination_risk"] is True
    assert out_window["isomir_discrimination_risk"] is False


if __name__ == "__main__":
    test_isomir_risk_when_primer_in_window()
    test_isomir_risk_at_boundary()
    test_no_isomir_risk_when_primer_beyond_window()
    test_no_isomir_risk_for_long_primer()
    test_unknown_mirna_no_risk()
    test_output_has_required_keys()
    test_output_boolean_type()
    test_miR10a_higher_risk_window()
    print("\nAll isomir_flag tests passed.")
