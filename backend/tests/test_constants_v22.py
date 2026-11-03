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
    MFE_STEMLOOP_MIN_DNA,
    MFE_STEMLOOP_MAX_DNA,
    OVERHANG_LENGTH_DEFAULT,
    SCORING_WEIGHTS_V3,
    SCORING_WEIGHTS_V4,
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


def test_mfe_dna_vienna_range_brackets_real_primers():
    """ViennaRNA DNA window (SCI-04) must contain the S fold for every 5–7-nt overhang."""
    from algorithm.stemloop_rt import _compute_mfe
    from algorithm.constants import STEMLOOP_BODY
    for tail in ("CGCCA", "CGCCAA", "TCAACAT", "AAAAAA", "GGGGGGG"):
        mfe, _, method = _compute_mfe(STEMLOOP_BODY + tail, {})
        assert "DNA" in method
        assert MFE_STEMLOOP_MIN_DNA <= mfe <= MFE_STEMLOOP_MAX_DNA, (tail, mfe)


def test_rt_primer_folded_as_dna_not_rna():
    """Regression SCI-04: the DNA fold is far weaker than the old RNA-parameter −27 kcal/mol."""
    from algorithm.stemloop_rt import _compute_mfe
    mfe, _, _ = _compute_mfe("GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACCGCCAA", {})
    assert -16.0 < mfe < -14.0, mfe


# ── Overhang length — critical Chen 2005 parameter ─────────────────

def test_overhang_length_default():
    """Stemloop binding region must default to 6 nt (Chen et al. 2005)."""
    assert OVERHANG_LENGTH_DEFAULT == 6


# ── Phase 3: SCORING_WEIGHTS_V4 (15 criteria) ──────────────────────

def test_scoring_weights_v3_sum_to_1():
    """SCORING_WEIGHTS_V3: 12 criteria must sum to 1.00."""
    assert abs(sum(SCORING_WEIGHTS_V3.values()) - 1.00) < 0.001
    assert len(SCORING_WEIGHTS_V3) == 12


def test_scoring_weights_v4_sum_to_1():
    """SCORING_WEIGHTS_V4: 15 criteria must sum to 1.00."""
    assert abs(sum(SCORING_WEIGHTS_V4.values()) - 1.00) < 0.001


def test_scoring_weights_v4_has_15_criteria():
    assert len(SCORING_WEIGHTS_V4) == 15


def test_scoring_weights_v4_bound_fraction_ratio():
    """bound_fraction_binding (0.05) > bound_fraction_full (0.03) — round 1 more important."""
    assert SCORING_WEIGHTS_V4["bound_fraction_binding"] > SCORING_WEIGHTS_V4["bound_fraction_full"]
    assert SCORING_WEIGHTS_V4["bound_fraction_binding"] == 0.05
    assert SCORING_WEIGHTS_V4["bound_fraction_full"] == 0.03


def test_scoring_weights_v4_family_discrimination():
    assert SCORING_WEIGHTS_V4["family_discrimination"] == 0.05


def test_scoring_weights_v4_no_isomir_flag():
    """isomir_flag is warning-only — must NOT be in weights."""
    assert "isomir_flag" not in SCORING_WEIGHTS_V4
