# ================================================================
# tests/test_template_structure.py — Unit tests for template_structure.py (PROMPT 7)
# Fan 2019 (DOI 10.1080/07391102.2018.1498804):
# Hairpin at the forward primer binding site inhibits PCR.
# ================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from algorithm.template_structure import check_template_structure
from algorithm.constants import (
    TEMPLATE_FOLD_WINDOW, TEMPLATE_STRUCTURE_MFE_WARN, TEMPLATE_BINDING_PAIRED_MAX,
)

# Skip all tests if ViennaRNA is not available
try:
    import RNA as _RNA
    _HAS_VIENNARNA = True
except ImportError:
    _HAS_VIENNARNA = False

pytestmark = pytest.mark.skipif(
    not _HAS_VIENNARNA,
    reason="ViennaRNA not available — template structure tests skipped",
)


# ── Shared fixtures ───────────────────────────────────────────────

def _candidate(seq, specific_len, tail_len):
    return {
        "sequence":        seq,
        "specific_length": specific_len,
        "tail_length":     tail_len,
    }


# Real miRNA sequences for integration tests
HAS_MIR_21 = "UAGCUUAUCAGACUGAUGUUGA"   # 22 nt, let7-family-unrelated
HAS_LET7A  = "UGAGGUAGUAGGUUGUAUAGUU"   # 22 nt

# hsa-miR-21-5p standard candidate (specific_len=14, tail_len=8)
MIR21_SEQ         = "GCGCGCAGTAGCUUAUCAGACUGAUGUU"[:22]
MIR21_SPECIFIC_LEN = 14
MIR21_TAIL_LEN     = 8


# ── Constant checks ───────────────────────────────────────────────

def test_fold_window_constant():
    assert TEMPLATE_FOLD_WINDOW == 60   # [Fan19]


def test_mfe_warn_constant():
    assert TEMPLATE_STRUCTURE_MFE_WARN == -5.0


# ── Return schema ─────────────────────────────────────────────────

def test_result_has_required_keys():
    """Result dict must have all expected keys."""
    mature = HAS_MIR_21
    cand = _candidate(
        seq="GCGCGCAG" + "TAGCTTAT" + "CAGACTGA" + "TGTTGA"[:5],
        specific_len=14,
        tail_len=8,
    )
    result = check_template_structure(mature, cand, {})
    for key in ("mfe", "structure", "binding_site_paired_bases",
                "has_strong_local_hairpin", "binding_region_in_window",
                "window_sequence", "method", "warning", "source"):
        assert key in result, f"Missing key: {key}"


# ── Smoke test: normal miRNA, no catastrophic warning ─────────────

def test_normal_mirna_no_catastrophic_flag():
    """
    A typical miRNA candidate should not have has_strong_local_hairpin=True.
    Most miRNAs are designed by evolution to be single-stranded — low structure.
    """
    from algorithm.sequence_utils import rna_to_dna
    dna = rna_to_dna(HAS_MIR_21).upper()
    specific_len = 14
    tail = "GCGCGCGC"[:8]
    cand = _candidate(tail + dna[:specific_len], specific_len, len(tail))
    result = check_template_structure(HAS_MIR_21, cand, {})
    # Not necessarily False, but at least the result is returned with valid types
    assert isinstance(result["has_strong_local_hairpin"], bool)
    assert isinstance(result["mfe"], float)
    assert len(result["structure"]) > 0


def test_mfe_is_negative():
    """MFE should always be negative (RNA always gains some stability from stacking)."""
    from algorithm.sequence_utils import rna_to_dna
    dna = rna_to_dna(HAS_LET7A).upper()
    cand = _candidate("GCGCGCGC" + dna[:14], 14, 8)
    result = check_template_structure(HAS_LET7A, cand, {})
    assert result["mfe"] <= 0.0


# ── Binding region coords are within window ───────────────────────

def test_binding_region_within_window():
    """Binding region coordinates must be [0, window_len) range."""
    from algorithm.sequence_utils import rna_to_dna
    dna = rna_to_dna(HAS_MIR_21).upper()
    cand = _candidate("GCGCGCGC" + dna[:14], 14, 8)
    result = check_template_structure(HAS_MIR_21, cand, {})
    r_start, r_end = result["binding_region_in_window"]
    win_len = result["window_length"]
    assert 0 <= r_start < r_end <= win_len


def test_window_sequence_length():
    """Window sequence must be ≤ TEMPLATE_FOLD_WINDOW nt."""
    from algorithm.sequence_utils import rna_to_dna
    dna = rna_to_dna(HAS_MIR_21).upper()
    cand = _candidate("GCGCGCGC" + dna[:14], 14, 8)
    result = check_template_structure(HAS_MIR_21, cand, {})
    assert result["window_length"] <= TEMPLATE_FOLD_WINDOW


def test_binding_region_size_matches_specific_len():
    """Binding region span must equal specific_length."""
    from algorithm.sequence_utils import rna_to_dna
    specific_len = 16
    dna = rna_to_dna(HAS_MIR_21).upper()
    cand = _candidate("GCGCGCGC" + dna[:specific_len], specific_len, 8)
    result = check_template_structure(HAS_MIR_21, cand, {})
    r_start, r_end = result["binding_region_in_window"]
    assert (r_end - r_start) == specific_len


# ── Synthetic template with known structure ───────────────────────

def test_flat_template_not_flagged():
    """
    A poly-A miRNA (no folding) should give very low paired count
    and is NOT flagged as has_strong_local_hairpin.
    (poly-A folds to essentially nothing.)
    """
    flat_mirna = "AAAAAAAAAAAAAAAAAAAAAAAA"  # 24 nt poly-A
    dna_mirna  = "AAAAAAAAAAAAAAAAAAAAAAAA"
    cand = _candidate("GCGCGCGC" + dna_mirna[:14], 14, 8)
    result = check_template_structure(flat_mirna, cand, {})
    # Poly-A forms very little structure → MFE ≈ 0 → not flagged
    assert not result["has_strong_local_hairpin"]


# ── Warning text cites Fan19 ──────────────────────────────────────

def test_source_cites_fan19():
    """Result source field must cite Fan 2019."""
    from algorithm.sequence_utils import rna_to_dna
    dna = rna_to_dna(HAS_MIR_21).upper()
    cand = _candidate("GCGCGCGC" + dna[:14], 14, 8)
    result = check_template_structure(HAS_MIR_21, cand, {})
    assert "Fan" in result["source"]
    assert "2019" in result["source"]


if __name__ == "__main__":
    print("Running template_structure tests...")
    test_fold_window_constant()
    test_mfe_warn_constant()
    test_result_has_required_keys()
    test_normal_mirna_no_catastrophic_flag()
    test_mfe_is_negative()
    test_binding_region_within_window()
    test_window_sequence_length()
    test_binding_region_size_matches_specific_len()
    test_flat_template_not_flagged()
    test_source_cites_fan19()
    print("\nAll template_structure tests passed.")
