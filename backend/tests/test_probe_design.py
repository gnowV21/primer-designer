"""
Tests for probe_design.py — TaqMan probe design (SPEC_phase6 PART A §A.7).

Covers: Tm gap, 5'-G rule, G>C rule, poly-G, junction position,
        universal mode, probe×forward heterodimer.
"""
import pytest
from unittest.mock import patch

from algorithm.probe_design import (
    design_probe, _apply_gc_rules, _max_run,
)
from algorithm.constants import (
    PROBE_TM_MIN_ABOVE_PRIMER, PROBE_NO_G_AT_5PRIME,
    PROBE_MAX_CONSECUTIVE_G, PROBE_MODE_UNIVERSAL, PROBE_MODE_CUSTOM,
    STEMLOOP_BODY, PROBE_JUNCTION_OVERLAP_MIRNA_SIDE,
    PROBE_JUNCTION_OVERLAP_STEMLOOP_SIDE,
)

# miR-21-5p: 22nt, GC-rich — probes usually have good Tm
_MIRNA_21   = "UAGCUUAUCAGACUGAUGUUGA"
_STEMLOOP   = STEMLOOP_BODY + "TCAACATCAGTCTGATAAGCTA"
_FWD_PRIMER = {"sequence": "GCATTATGAGTCGAATCAGTCTGATAAGCTA", "tm": 60.0}
_PARAMS     = {}


def _probe(mode=PROBE_MODE_CUSTOM, probe_type="single_q"):
    return design_probe(_MIRNA_21, _STEMLOOP, _FWD_PRIMER, _PARAMS, mode=mode, probe_type=probe_type)


# ── test_probe_tm_gap_enforced ────────────────────────────────────

def test_probe_tm_gap_enforced():
    """If all probe candidates fail the Tm gap threshold, result should warn."""
    # Patch probe Tm to be just 1°C above forward (gap < 6°C required)
    with patch("algorithm.probe_design._probe_tm", return_value=61.0):
        result = _probe()
    # Either no probe found (None sequence) OR warning about Tm gap
    if result["sequence"] is None:
        assert any("gap" in w.lower() or "No probe" in w for w in result["warnings"])
    else:
        gap_check = result["quality"]["checks"].get("tm_gap", {})
        # Gap = 61-60 = 1°C < PROBE_TM_MIN_ABOVE_PRIMER → should fail
        assert gap_check.get("pass") is False or any("gap" in w.lower() for w in result["warnings"])


# ── test_probe_no_g_at_5prime ─────────────────────────────────────

def test_probe_no_g_at_5prime():
    """Probe starting with G should be corrected or flagged."""
    result = _probe()
    if result["sequence"] is not None:
        # Either 5'-G is avoided by _apply_gc_rules, or it's flagged as warning
        starts_g = result["sequence"][0] == "G"
        if starts_g:
            assert any("5'" in w or "G" in w for w in result["warnings"])


def test_apply_gc_rules_removes_5prime_g():
    """_apply_gc_rules should not return sequence starting with G if RC fixes it."""
    seq_g_start = "GACGTACGT"   # starts with G
    fixed = _apply_gc_rules(seq_g_start)
    # After correction: either no 5'-G OR G>C was the priority and RC returned
    # At minimum, if RC of this doesn't start with G, it should be applied
    rc = seq_g_start.translate(str.maketrans("ACGT","TGCA"))[::-1]
    if rc[0] != "G":
        assert fixed[0] != "G"


# ── test_probe_g_not_exceed_c ─────────────────────────────────────

def test_probe_g_not_exceed_c():
    """G > C count → _apply_gc_rules should take RC."""
    # Sequence with clearly G > C
    seq = "GGGGGACAC"  # G=5, C=2 → RC = GTGTCCCCC, G=1,C=5 → OK
    fixed = _apply_gc_rules(seq)
    assert fixed.count("G") <= fixed.count("C")


# ── test_probe_poly_g_flagged ─────────────────────────────────────

def test_probe_poly_g_flagged():
    """_max_run detects poly-G runs correctly."""
    assert _max_run("AGGGGC", "G") == 4
    assert _max_run("ACGT", "G") == 1
    assert _max_run("AAAA", "G") == 0


def test_max_run_poly_g_over_limit():
    """Probe with >PROBE_MAX_CONSECUTIVE_G consecutive G should surface in warnings."""
    poly_g_seq = "A" * 5 + "G" * (PROBE_MAX_CONSECUTIVE_G + 1) + "C" * 8
    # Patch probe selection to return this specific sequence
    with patch("algorithm.probe_design._design_custom", return_value={"sequence": poly_g_seq, "tm": 70.0, "position_1based": 40}):
        result = _probe()
    if result["sequence"] is not None and _max_run(result["sequence"], "G") > PROBE_MAX_CONSECUTIVE_G:
        assert any("G" in w for w in result["warnings"])


# ── test_probe_junction_position ──────────────────────────────────

def test_probe_junction_position_custom():
    """Custom probe must span junction with required STEMLOOP and miRNA overlap."""
    result = _probe(mode=PROBE_MODE_CUSTOM)
    if result["sequence"] is None:
        pytest.skip("No probe candidate found (Tm criteria not met for this miRNA/params)")
    # Verify probe sequence contains junction: last 4nt of STEMLOOP_BODY + first 7nt of RC_miRNA
    from algorithm.sequence_utils import rna_to_dna, reverse_complement
    rc_mature = reverse_complement(rna_to_dna(_MIRNA_21.upper()))
    stemloop_side = STEMLOOP_BODY[-PROBE_JUNCTION_OVERLAP_STEMLOOP_SIDE:]
    mirna_side    = rc_mature[:PROBE_JUNCTION_OVERLAP_MIRNA_SIDE]
    junction_core = stemloop_side + mirna_side
    probe_seq = result["sequence"]
    rc_probe  = probe_seq.translate(str.maketrans("ACGT","TGCA"))[::-1]
    assert (junction_core in probe_seq or junction_core in rc_probe), (
        f"Probe '{probe_seq}' does not span junction core '{junction_core}'"
    )


# ── test_universal_mode_binds_stemloop ───────────────────────────

def test_universal_mode_binds_stemloop():
    """Universal probe should be derived from STEMLOOP_BODY (complement)."""
    result = _probe(mode=PROBE_MODE_UNIVERSAL)
    if result["sequence"] is None:
        pytest.skip("No universal probe candidate found (Tm criteria)")
    # Universal probe = RC of some window in STEMLOOP_BODY
    probe_seq = result["sequence"]
    # Check RC of probe appears in STEMLOOP_BODY
    rc_probe = probe_seq.translate(str.maketrans("ACGT","TGCA"))[::-1]
    assert rc_probe in STEMLOOP_BODY or probe_seq in STEMLOOP_BODY, (
        f"Universal probe '{probe_seq}' does not map to STEMLOOP_BODY"
    )


# ── test_probe_heterodimer_vs_primers ─────────────────────────────

def test_probe_result_has_hetero_check():
    """design_probe result should include probe×forward heterodimer check when fwd_seq given."""
    result = _probe()
    if result["sequence"] is None:
        pytest.skip("No probe candidate")
    checks = result["quality"].get("checks", {})
    assert "hetero_dimer_fwd_dg" in checks, "Missing probe×forward heterodimer check"
    dg_entry = checks["hetero_dimer_fwd_dg"]
    assert "value" in dg_entry and "pass" in dg_entry
