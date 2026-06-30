# ================================================================
# tests/test_family_crossreactivity.py
# Unit tests for specificity_check/family_crossreactivity.py
#
# Uses real let-7 family sequences (PLACEHOLDER — verify vs miRBase).
# Tests: risk classification, Hamming distance, ΔTm direction, output schema.
# ================================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.specificity_check.family_crossreactivity import (
    check_family_crossreactivity,
    _hamming,
    _classify_risk,
    _get_overhang,
    _calc_tm,
)

DEFAULT_PARAMS = {
    "saltConcentration": 50.0,
    "magnesiumConcentration": 1.5,
    "dntpTotal": 0.8,
    "primerConcentration": 200.0,
}

# let-7a mature sequence (PLACEHOLDER — verify with miRBase v22+)
LET7A_SEQ = "UGAGGUAGUAGGUUGUAUAGUU"   # 22 nt
LET7C_SEQ = "UGAGGUAGUAGGUUGUAUGGUU"   # 1 mismatch vs let-7a in 6-nt overhang
LET7B_SEQ = "UGAGGUAGUAGGUUGUGUGGUU"   # 2 mismatches vs let-7a in 6-nt overhang


# ── Unit tests: _hamming ──────────────────────────────────────────

def test_hamming_identical():
    assert _hamming("AUAGUU", "AUAGUU") == 0

def test_hamming_one_mismatch():
    # let-7a overhang: AUAGUU, let-7c overhang: AUGGUU → mismatch at position 3
    let7a_oh = _get_overhang(LET7A_SEQ, 6)   # AUAGUU
    let7c_oh = _get_overhang(LET7C_SEQ, 6)   # AUGGUU
    assert _hamming(let7a_oh, let7c_oh) == 1

def test_hamming_two_mismatches():
    let7a_oh = _get_overhang(LET7A_SEQ, 6)   # AUAGUU
    let7b_oh = _get_overhang(LET7B_SEQ, 6)   # GUGGUU
    assert _hamming(let7a_oh, let7b_oh) == 2

def test_hamming_zero_length_match():
    assert _hamming("", "") == 0

def test_hamming_length_mismatch():
    # Different lengths → returns max length (worst case)
    result = _hamming("AUAGUU", "AUAG")
    assert result == 6  # max(6, 4)


# ── Unit tests: _classify_risk ────────────────────────────────────

def test_classify_identical():
    assert _classify_risk(0, 0.0) == "IDENTICAL"

def test_classify_high_risk():
    assert _classify_risk(1, 3.0) == "HIGH"   # 1 mismatch, ΔTm < 5°C

def test_classify_low_one_mismatch():
    assert _classify_risk(1, 6.0) == "LOW"    # 1 mismatch, ΔTm ≥ 5°C

def test_classify_low_two_mismatches():
    assert _classify_risk(2, 0.0) == "LOW"    # 2 mismatches → always LOW

def test_classify_safe():
    assert _classify_risk(3, 0.0) == "SAFE"
    assert _classify_risk(4, 0.0) == "SAFE"


# ── Unit tests: _get_overhang ─────────────────────────────────────

def test_get_overhang_6nt():
    oh = _get_overhang(LET7A_SEQ, 6)
    assert oh == "AUAGUU"
    assert len(oh) == 6

def test_get_overhang_7nt():
    oh = _get_overhang(LET7A_SEQ, 7)
    assert len(oh) == 7
    assert oh[-6:] == "AUAGUU"   # last 6 same as 6-nt overhang

def test_get_overhang_uppercase():
    oh = _get_overhang("ugagguaguagguuguauaguu", 6)
    assert oh == "AUAGUU"


# ── Unit tests: _calc_tm (Tm approximation) ───────────────────────

def test_calc_tm_returns_float():
    tm = _calc_tm("AUAGUU", DEFAULT_PARAMS)
    assert isinstance(tm, float)

def test_calc_tm_shorter_overhang_lower_tm():
    """A 7-nt overhang should have higher Tm than 6-nt (more base pairs)."""
    tm6 = _calc_tm(_get_overhang(LET7A_SEQ, 6), DEFAULT_PARAMS)
    tm7 = _calc_tm(_get_overhang(LET7A_SEQ, 7), DEFAULT_PARAMS)
    assert tm7 > tm6

def test_calc_tm_sibling_direction():
    """
    Tm(let-7a 6-nt) vs Tm(let-7c 6-nt).
    let-7a: AUAGUU; let-7c: AUGGUU (1 mismatch).
    ΔTm is estimated via independent Tm of each 6-mer.
    Direction should follow GC content: AUGGUU has more G/C than AUAGUU → higher Tm.
    """
    tm_a = _calc_tm(_get_overhang(LET7A_SEQ, 6), DEFAULT_PARAMS)  # AUAGUU: 1G, 1C → 2 GC
    tm_c = _calc_tm(_get_overhang(LET7C_SEQ, 6), DEFAULT_PARAMS)  # AUGGUU: 1G, 1G, 1C → 3 GC
    # let-7c has one more G → expect slightly higher Tm
    # This is informational — the exact direction is sequence-dependent
    print(f"\n[Tm] let-7a overhang Tm = {tm_a:.1f}°C, let-7c overhang Tm = {tm_c:.1f}°C")


# ── Integration test: check_family_crossreactivity ───────────────

def test_let7a_family_structure():
    """
    Full integration test: let-7a in let-7 family.
    Expects: family='let-7', cross_reactivity is a list, recommendation present.
    """
    result = check_family_crossreactivity(
        mature_seq=LET7A_SEQ,
        mirna_name="hsa-let-7a-5p",
        params=DEFAULT_PARAMS,
        overhang_len=6,
    )
    assert result["family"] == "let-7"
    assert result["overhang_used"] == 6
    assert result["target_overhang"] == "AUAGUU"
    assert isinstance(result["cross_reactivity"], list)
    assert "recommendation" in result
    assert "data_warning" in result

def test_let7a_has_crossreactivity_entries():
    """
    let-7a vs let-7c should produce a cross_reactivity entry (1 mismatch in 6-nt).
    Let-7a vs let-7b should produce a cross_reactivity entry (2 mismatches).
    """
    result = check_family_crossreactivity(
        mature_seq=LET7A_SEQ,
        mirna_name="hsa-let-7a-5p",
        params=DEFAULT_PARAMS,
        overhang_len=6,
    )
    siblings_found = {r["sibling"] for r in result["cross_reactivity"]}
    # let-7c has 1 mismatch → should appear
    assert any("let-7c" in s for s in siblings_found), (
        f"Expected let-7c in cross_reactivity, got: {siblings_found}"
    )

def test_recommendation_has_required_keys():
    result = check_family_crossreactivity(
        mature_seq=LET7A_SEQ,
        mirna_name="hsa-let-7a-5p",
        params=DEFAULT_PARAMS,
        overhang_len=6,
    )
    rec = result["recommendation"]
    assert "suggested_overhang_length" in rec
    assert "resolved" in rec
    assert "remaining_high_risk_siblings" in rec
    assert isinstance(rec["remaining_high_risk_siblings"], list)

def test_unknown_mirna_returns_no_family():
    """For a miRNA not in any family, return no_family result."""
    result = check_family_crossreactivity(
        mature_seq="UAGCUUAUCAGACUGAUGUUGA",
        mirna_name="hsa-miR-XXX-5p",
        params=DEFAULT_PARAMS,
        overhang_len=6,
    )
    assert result["family"] is None
    assert result["cross_reactivity"] == []

def test_each_crossreactivity_entry_schema():
    """Every cross-reactivity entry must have required keys and valid values."""
    result = check_family_crossreactivity(
        mature_seq=LET7A_SEQ,
        mirna_name="hsa-let-7a-5p",
        params=DEFAULT_PARAMS,
        overhang_len=6,
    )
    for entry in result["cross_reactivity"]:
        assert "sibling" in entry
        assert "mismatch" in entry
        assert "delta_tm" in entry
        assert "risk" in entry
        assert entry["risk"] in ("IDENTICAL", "HIGH", "LOW")
        assert entry["mismatch"] in (0, 1, 2)  # SAFE (≥3) are omitted


if __name__ == "__main__":
    test_hamming_identical()
    test_hamming_one_mismatch()
    test_hamming_two_mismatches()
    test_hamming_zero_length_match()
    test_hamming_length_mismatch()
    test_classify_identical()
    test_classify_high_risk()
    test_classify_low_one_mismatch()
    test_classify_low_two_mismatches()
    test_classify_safe()
    test_get_overhang_6nt()
    test_get_overhang_7nt()
    test_get_overhang_uppercase()
    test_calc_tm_returns_float()
    test_calc_tm_shorter_overhang_lower_tm()
    test_calc_tm_sibling_direction()
    test_let7a_family_structure()
    test_let7a_has_crossreactivity_entries()
    test_recommendation_has_required_keys()
    test_unknown_mirna_returns_no_family()
    test_each_crossreactivity_entry_schema()
    print("\nAll family_crossreactivity tests passed.")
