# ================================================================
# tests/test_constants_v22.py
# Unit tests for Section 16 checklist — v2.1 + v2.2 constant verification.
#
# Checklist tests required:
#   test_max_poly_x_updated_to_5
#   test_thermodynamic_alignment_constants_exist
#   test_homopolymer_5_not_flagged
# ================================================================

from algorithm.constants import (
    MAX_HOMOPOLYMER_RUN,
    GC_MAX_IN_3PRIME_WINDOW,
    GC_CLAMP_MIN_IN_LAST3,
    P3_THERMODYNAMIC_OLIGO_ALIGNMENT,
    P3_THERMODYNAMIC_TEMPLATE_ALIGNMENT,
    P3_TM_FORMULA,
    P3_SALT_CORRECTIONS,
    P3_DEFAULT_DNTP_CONC,
    P3_DEFAULT_DNA_CONC,
    FORWARD_MAX_LENGTH,
    MFE_STEMLOOP_MIN,
    MFE_STEMLOOP_MAX,
    MFE_STEMLOOP_MIN_RNA,
    MFE_STEMLOOP_MAX_RNA,
    OVERHANG_LENGTH_DEFAULT,
)
from algorithm.sequence_utils import check_homopolymer


# ── Section 16 — explicitly named checklist tests ──────────────────

def test_max_poly_x_updated_to_5():
    """v2.2: MAX_HOMOPOLYMER_RUN must be 5 (P3P Advanced Settings Max Poly-X=5)."""
    assert MAX_HOMOPOLYMER_RUN == 5


def test_thermodynamic_alignment_constants_exist():
    """v2.2: Thermodynamic alignment flags must match P3P Advanced Settings."""
    assert P3_THERMODYNAMIC_OLIGO_ALIGNMENT is True
    assert P3_THERMODYNAMIC_TEMPLATE_ALIGNMENT is False


def test_homopolymer_5_not_flagged():
    """
    A homopolymer run of exactly 5 identical bases must NOT be flagged.
    P3P 'Max Poly-X = 5' means runs of length > 5 are rejected, not == 5.
    check_homopolymer(seq, 5) returns True only when run length > 5.
    """
    seq = "GCGCGCAAAAAGCGCGC"  # 5 A's — should pass
    assert not check_homopolymer(seq, MAX_HOMOPOLYMER_RUN)


# ── Complementary correctness tests ────────────────────────────────

def test_homopolymer_6_is_flagged():
    """A run of 6+ must be flagged."""
    seq = "GCGCGCAAAAAAGCGCG"  # 6 A's
    assert check_homopolymer(seq, MAX_HOMOPOLYMER_RUN)


def test_gc_end_window_is_5():
    """v2.2: GC_MAX_IN_3PRIME_WINDOW must be 5 (P3P Max End GC=5)."""
    assert GC_MAX_IN_3PRIME_WINDOW == 5


def test_gc_clamp_min_in_last3():
    """v2.1: GC clamp requires ≥ 2 G/C in last 3 bases (IDT PrimerQuest)."""
    assert GC_CLAMP_MIN_IN_LAST3 == 2


def test_tm_formula_santalucia():
    """v2.2: Tm formula must be SantaLucia 1998 (P3_TM_FORMULA = 1)."""
    assert P3_TM_FORMULA == 1
    assert P3_SALT_CORRECTIONS == 1


# ── v2.1 BUG FIX constants ─────────────────────────────────────────

def test_dntp_bug_fix_v21():
    """v2.1 BUG FIX: dNTP must be 0.8 mM total (4 × 0.2 mM per dNTP)."""
    assert P3_DEFAULT_DNTP_CONC == 0.8


def test_dna_conc_v21():
    """v2.1: DNA concentration must be 200 nM (IDT PrimerQuest default)."""
    assert P3_DEFAULT_DNA_CONC == 200.0


def test_forward_max_length_v21():
    """v2.1: FORWARD_MAX_LENGTH must be 27 nt (P3P General Settings Max:27)."""
    assert FORWARD_MAX_LENGTH == 27


# ── MFE range constants — both DNA proxy and RNA calibrated ────────

def test_mfe_dna_proxy_range():
    """DNA proxy MFE thresholds must be [-13, -10] kcal/mol (primer3-py proxy)."""
    assert MFE_STEMLOOP_MIN == -13.0
    assert MFE_STEMLOOP_MAX == -10.0


def test_mfe_rna_range():
    """ViennaRNA RNA MFE thresholds must be [-35, -20] kcal/mol."""
    assert MFE_STEMLOOP_MIN_RNA == -35.0
    assert MFE_STEMLOOP_MAX_RNA == -20.0


# ── Overhang length — critical Chen 2005 parameter ─────────────────

def test_overhang_length_default():
    """Stemloop binding region must default to 6 nt (Chen et al. 2005)."""
    assert OVERHANG_LENGTH_DEFAULT == 6
