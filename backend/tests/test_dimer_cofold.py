# ================================================================
# tests/test_dimer_cofold.py — full-structure dimer ΔG by RNAcofold (DNA)
# Algorithm 3.6.0, AUDIT REV-19: hard-filter rule 1 and the dimer_penalty
# full-structure check use Kang 2017's method (RNAcofold, DNA parameters)
# instead of primer3 thal at Ta.
# ================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from algorithm import vienna_dna
from algorithm.constants import DIMER_FULL_DG_CRITICAL, UNIVERSAL_REVERSE
from algorithm.hard_filters import apply_hard_filters
from algorithm.scoring import score_candidate
from algorithm.structure_check import (
    run_all_structure_checks, full_dimer_dg, FULL_DIMER_FALLBACK_METHOD,
)

needs_vienna = pytest.mark.skipif(not vienna_dna.AVAILABLE, reason="ViennaRNA bindings not installed")

# hsa-miR-4757-5p forward primer chosen by 3.5.0: primer3 at 60 °C gave −9.00
# (passed rule 1 by 0.00), RNAcofold gives −19.6 (benchmark/dimer_dg_method_compare.json).
PALINDROMIC_F = "GACAACAGAGGCCTCTGTGAC"
# hsa-miR-10401-5p forward primer: no strong dimer on either scale.
CLEAN_F = "GACTCAACCGTGTGGGAAGG"


# ── vienna_dna ────────────────────────────────────────────────────

@needs_vienna
def test_cofold_matches_benchmark_value():
    dg, structure = vienna_dna.cofold_dg(PALINDROMIC_F, PALINDROMIC_F)
    assert dg == pytest.approx(-19.6, abs=0.05)
    assert len(structure) == 2 * len(PALINDROMIC_F)


@needs_vienna
def test_cofold_uses_dna_parameters_not_rna():
    import RNA
    rna_dg = RNA.fold_compound(PALINDROMIC_F + "&" + PALINDROMIC_F).mfe_dimer()[1]
    dna_dg, _ = vienna_dna.cofold_dg(PALINDROMIC_F, PALINDROMIC_F)
    assert dna_dg > rna_dg + 5          # RNA params ≈ −28.9: clearly a different set


@needs_vienna
def test_global_rna_parameters_left_unchanged():
    """template_structure.py folds RNA with the library default; vienna_dna must not change it."""
    import RNA
    seq = "UGAGGUAGUAGGUUGUAUAGUU"
    before = RNA.fold(seq)[1]
    vienna_dna.cofold_dg(PALINDROMIC_F, CLEAN_F)
    RNA.params_load_RNA_Turner2004()
    reference = RNA.fold(seq)[1]
    assert before == pytest.approx(reference)


def test_intermolecular_pair_detection():
    # strand 1 = 4 nt; "((..))" closing inside strand 1 only → no dimer
    assert not vienna_dna._has_intermolecular_pair("((..))....", 6)
    assert vienna_dna._has_intermolecular_pair("..((....))", 5)
    assert not vienna_dna._has_intermolecular_pair("..........", 5)


# ── structure checks expose the value ─────────────────────────────

@needs_vienna
def test_structure_checks_carry_cofold_dg():
    sc = run_all_structure_checks(PALINDROMIC_F, UNIVERSAL_REVERSE, {})
    for key in ("self_dimer", "hetero_dimer"):
        assert isinstance(sc[key]["dg_cofold"], float)
        assert sc[key]["dg_cofold_structure"]
    dg, method = full_dimer_dg(sc)
    assert dg == pytest.approx(-19.6, abs=0.05)
    assert "RNAcofold" in method and "DNA" in method


# ── full_dimer_dg: preference and fallback ────────────────────────

def _sc(sd_p3, hd_p3, sd_cof=None, hd_cof=None):
    return {
        "self_dimer":   {"dg_overall": sd_p3, "dg_3prime": -2.0, "dg_cofold": sd_cof},
        "hetero_dimer": {"dg_overall": hd_p3, "dg_3prime": -2.0, "dg_cofold": hd_cof},
        "has_critical_flag": False,
        "hairpin": {"severity": "safe", "dg": -1.0},
    }


def test_full_dimer_dg_prefers_cofold():
    dg, method = full_dimer_dg(_sc(-2.0, -3.0, sd_cof=-12.0, hd_cof=-6.0))
    assert dg == -12.0
    assert "RNAcofold" in method


def test_full_dimer_dg_falls_back_to_primer3_and_says_so():
    dg, method = full_dimer_dg(_sc(-9.5, -3.0))
    assert dg == -9.5
    assert method == FULL_DIMER_FALLBACK_METHOD


# ── hard filter rule 1 follows the RNAcofold value ────────────────

def test_rule1_rejects_on_cofold_even_when_primer3_passes():
    reasons = apply_hard_filters({"structure_checks": _sc(-2.0, -3.0, sd_cof=-12.0, hd_cof=-5.0)})
    assert any("hard_dimer_full_dg" in r for r in reasons)


def test_rule1_passes_on_cofold_even_when_primer3_fails():
    reasons = apply_hard_filters({"structure_checks": _sc(-10.0, -3.0, sd_cof=-8.0, hd_cof=-5.0)})
    assert not any("hard_dimer_full_dg" in r for r in reasons)


def test_rule1_boundary_is_strict():
    at = apply_hard_filters({"structure_checks": _sc(0, 0, DIMER_FULL_DG_CRITICAL, -1.0)})
    below = apply_hard_filters({"structure_checks": _sc(0, 0, DIMER_FULL_DG_CRITICAL - 0.01, -1.0)})
    assert not any("hard_dimer_full_dg" in r for r in at)
    assert any("hard_dimer_full_dg" in r for r in below)


# ── dimer_penalty explanation names the method ────────────────────

def test_dimer_penalty_uses_cofold_and_names_it():
    seq = "ATCGATCGATCGATCGATCGACG"
    fwd = {
        "sequence": seq, "tm_full": 60.0, "tm_binding": 45.0, "gc_percent": 50.0,
        "length": len(seq), "specific_length": 14, "specific_sequence": seq[-14:],
        "tail_length": len(seq) - 14, "amplicon_size": 80,
        "structure_checks": {
            **_sc(-2.0, -2.0, sd_cof=-11.0, hd_cof=-4.0),
            "end_stability": {"stability_kcal_mol": 5.0, "last_5_bases": seq[-5:], "pass": True},
            "overall_pass": True,
        },
    }
    fwd["structure_checks"]["self_dimer"].update(pass_overall=True, pass_3prime=True, critical_3prime=False)
    fwd["structure_checks"]["hetero_dimer"].update(pass_overall=True, pass_3prime=True, critical_3prime=False)
    res = score_candidate(fwd, {"mfe": -11.5, "mfe_method": "primer3-py", "gc_percent": 55, "tm_full": 70.0},
                          {"tm": 60.4}, {}, cross_reactivity=None, use_v4=False)
    assert res["scores"]["dimer_penalty"] == 0
    assert "RNAcofold" in res["explanations"]["dimer_penalty"]
    assert "-11.00" in res["explanations"]["dimer_penalty"]
