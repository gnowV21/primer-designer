# ================================================================
# test_hybrid_tm.py — Unit tests for Sugimoto 1995 DNA:RNA hybrid Tm
# All reference Tm values computed from the NN table implemented in
# hybrid_tm.py at 1M NaCl, 4 μM total strand (Sugimoto 1995 conditions).
# For independent validation: run same sequences through MELTING 5.1.1
# (Le Novère, EBI) or IDT OligoAnalyzer in DNA:RNA hybrid mode.
# ================================================================

import pytest
import primer3
from algorithm.hybrid_tm import predict_hybrid_tm, _NN, _INIT_AT, _INIT_GC, R_CAL
from algorithm.constants import USE_HYBRID_TM


# ── Reference Tm values ────────────────────────────────────────────
# Hand-computed from Sugimoto 1995 NN table (1M NaCl, 4 μM strand):
#   Tm = ΔH / (ΔS_eff + R·ln(Ct/4)) − 273.15
#   Ct = 4e-6 M, [Na+] = 1.0 M → salt correction = 0
#   ln(1e-6) = -13.8155
# Tolerance ±0.5°C for floating-point rounding.
CASES_1M_4uM = [
    # (sequence, expected_tm_c, description)
    ("AAAAAA", 3.1,  "poly-A 6-mer: 5×AA/UU steps, AT initiation [Sugimoto95 Table 2]"),
    ("GCGCGC", 40.7, "alternating GC 6-mer: 3×GC + 2×CG steps, GC initiation [Sugimoto95 Table 2]"),
    ("ACGTAC", 11.0, "mixed 6-mer: AC+CG+GT+TA+AC steps, AT initiation [Sugimoto95 Table 2]"),
]


class TestNNTable:
    """Verify the NN table has all 16 required entries."""

    def test_all_16_dinucleotides_present(self):
        expected = {
            a + b for a in "ACGT" for b in "ACGT"
        }
        assert set(_NN.keys()) == expected, f"Missing: {expected - set(_NN.keys())}"

    def test_all_delta_h_negative(self):
        for dinuc, (dH, _) in _NN.items():
            assert dH < 0, f"{dinuc}: ΔH must be negative (stacking stabilises), got {dH}"

    def test_all_delta_s_nonzero(self):
        for dinuc, (_, dS) in _NN.items():
            assert dS != 0, f"{dinuc}: ΔS must be non-zero, got {dS}"


class TestPredictHybridTm:
    """Functional tests for predict_hybrid_tm."""

    # ── Structure ────────────────────────────────────────────────

    def test_returns_expected_keys(self):
        r = predict_hybrid_tm("ACGTAC")
        for key in ("tm_c", "dH", "dS", "method", "chemistry", "accuracy", "caveats"):
            assert key in r, f"Missing key: {key}"

    def test_chemistry_is_dna_rna(self):
        r = predict_hybrid_tm("ACGTAC")
        assert r["chemistry"] == "DNA:RNA"

    def test_method_cites_sugimoto(self):
        r = predict_hybrid_tm("ACGTAC")
        assert "Sugimoto" in r["method"]

    def test_caveats_list_not_empty(self):
        r = predict_hybrid_tm("ACGTAC")
        assert isinstance(r["caveats"], list) and len(r["caveats"]) > 0

    def test_short_duplex_caveat_present(self):
        r = predict_hybrid_tm("ACGTAC")
        assert any("short-duplex" in c for c in r["caveats"])

    # ── Reference Tm values (Sugimoto 1995 conditions: 1M NaCl, 4 μM) ──
    # Tolerance ±0.5°C for floating-point rounding differences.
    # Source: hand-computed from Sugimoto 1995 Table 2 NN parameters.
    # Independent verification: MELTING 5.1.1 (EBI) or IDT OligoAnalyzer DNA:RNA mode.

    @pytest.mark.parametrize("seq,expected,desc", CASES_1M_4uM)
    def test_reference_tm_1M_NaCl_4uM(self, seq, expected, desc):
        result = predict_hybrid_tm(
            seq,
            dna_conc_nM=4000.0,   # 4 μM — Sugimoto 1995 measurement conditions
            mv_conc_mM=1000.0,    # 1 M NaCl — Sugimoto 1995 measurement conditions
        )
        assert result["tm_c"] is not None, f"Failed for {seq}: {result['caveats']}"
        assert abs(result["tm_c"] - expected) < 0.5, (
            f"{desc}\n  Expected {expected}°C, got {result['tm_c']}°C"
        )

    # ── Thermodynamic ordering ────────────────────────────────────

    def test_gc_rich_higher_tm_than_at_rich(self):
        """GC-rich duplex must have higher Tm than AT-rich duplex [Sugimoto95]."""
        at_rich = predict_hybrid_tm("AAAAAA", dna_conc_nM=4000.0, mv_conc_mM=1000.0)
        gc_rich = predict_hybrid_tm("GCGCGC", dna_conc_nM=4000.0, mv_conc_mM=1000.0)
        assert at_rich["tm_c"] < gc_rich["tm_c"], (
            f"AT-rich Tm ({at_rich['tm_c']}) should be < GC-rich Tm ({gc_rich['tm_c']})"
        )

    def test_longer_duplex_higher_tm(self):
        """Longer duplex of same composition should have higher Tm."""
        short = predict_hybrid_tm("GCGC",   dna_conc_nM=4000.0, mv_conc_mM=1000.0)
        long  = predict_hybrid_tm("GCGCGCGC", dna_conc_nM=4000.0, mv_conc_mM=1000.0)
        assert short["tm_c"] < long["tm_c"], (
            f"4-mer Tm ({short['tm_c']}) should be < 8-mer Tm ({long['tm_c']})"
        )

    def test_higher_salt_increases_tm(self):
        """Higher monovalent salt stabilises duplex → higher Tm [SL98]."""
        low_salt  = predict_hybrid_tm("ACGTAC", dna_conc_nM=4000.0, mv_conc_mM=50.0)
        high_salt = predict_hybrid_tm("ACGTAC", dna_conc_nM=4000.0, mv_conc_mM=500.0)
        assert low_salt["tm_c"] < high_salt["tm_c"], (
            f"Low salt Tm ({low_salt['tm_c']}) should be < high salt Tm ({high_salt['tm_c']})"
        )

    # ── Ct convention ────────────────────────────────────────────

    def test_lower_concentration_lower_tm(self):
        """Lower strand concentration → lower Tm (more unfavorable entropy effect)."""
        high_ct = predict_hybrid_tm("ACGTAC", dna_conc_nM=4000.0, mv_conc_mM=1000.0)
        low_ct  = predict_hybrid_tm("ACGTAC", dna_conc_nM=100.0,  mv_conc_mM=1000.0)
        assert low_ct["tm_c"] < high_ct["tm_c"], (
            f"Low Ct Tm ({low_ct['tm_c']}) should be < High Ct Tm ({high_ct['tm_c']})"
        )

    # ── Different from primer3 DNA:DNA ─────────────────────────────

    def test_hybrid_tm_differs_from_primer3_dnadna(self):
        """
        Sugimoto DNA:RNA Tm must differ from primer3 DNA:DNA Tm for the same sequence.
        This verifies the two engines use different NN tables.
        """
        seq = "ACGTAC"
        hybrid_result = predict_hybrid_tm(seq, dna_conc_nM=4000.0, mv_conc_mM=50.0)

        p3_tm = primer3.calc_tm(
            seq=seq,
            mv_conc=50.0,
            dv_conc=1.5,
            dntp_conc=0.8,
            dna_conc=200.0,  # primer3 uses 200 nM by default; different Ct convention
        )

        assert hybrid_result["tm_c"] != pytest.approx(p3_tm, abs=0.1), (
            f"Hybrid Tm ({hybrid_result['tm_c']}) should differ from primer3 DNA:DNA Tm ({p3_tm:.1f}); "
            "same result would indicate the wrong NN table is being used"
        )

    # ── USE_HYBRID_TM flag ────────────────────────────────────────

    def test_use_hybrid_tm_flag_is_boolean(self):
        """USE_HYBRID_TM constant must be a boolean."""
        assert isinstance(USE_HYBRID_TM, bool)

    def test_function_available_when_flag_is_true(self):
        """predict_hybrid_tm must be callable regardless of USE_HYBRID_TM flag."""
        result = predict_hybrid_tm("GCGCGC")
        assert result["tm_c"] is not None

    # ── Edge cases ────────────────────────────────────────────────

    def test_single_base_returns_failure(self):
        r = predict_hybrid_tm("A")
        assert r["tm_c"] is None, "Single-base input should return failure (too short for NN)"

    def test_invalid_base_returns_failure(self):
        r = predict_hybrid_tm("ACGN")
        assert r["tm_c"] is None, "Sequence with 'N' should return failure"

    def test_empty_string_returns_failure(self):
        r = predict_hybrid_tm("")
        assert r["tm_c"] is None
