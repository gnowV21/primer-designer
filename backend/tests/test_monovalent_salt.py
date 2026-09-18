"""Effective-monovalent salt model: Na+ + K+ + protonated Tris (Tris+)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.thermodynamics import effective_monovalent_mM, calculate_tm_nn


def test_absent_ions_keep_na_only_baseline():
    # Callers that omit K+/pH (validator, API {}) must NOT gain invented ions.
    assert effective_monovalent_mM({}) == 50.0                       # Na+ default only
    assert effective_monovalent_mM({"saltConcentration": 50}) == 50.0


def test_kplus_adds_to_monovalent():
    base = effective_monovalent_mM({"saltConcentration": 50})
    withk = effective_monovalent_mM({"saltConcentration": 50, "kPlusConc": 50})
    assert withk == base + 50.0                                      # K+ summed 1:1


def test_tris_contributes_protonated_fraction_only_with_ph():
    # No pH → no Tris term.
    assert effective_monovalent_mM({"saltConcentration": 50, "kPlusConc": 0}) == 50.0
    # With pH 8.06 (= pKa) → exactly half of 10 mM Tris = 5 mM Tris+.
    mono = effective_monovalent_mM({"saltConcentration": 50, "kPlusConc": 0, "bufferPH": 8.06})
    assert abs(mono - 55.0) < 1e-6
    # Higher pH → less protonated Tris → smaller contribution.
    hi = effective_monovalent_mM({"saltConcentration": 50, "bufferPH": 9.0})
    lo = effective_monovalent_mM({"saltConcentration": 50, "bufferPH": 8.06})
    assert hi < lo


def test_full_buffer_raises_tm_vs_na_only():
    seq = "GCGGCGTAGCTTATCAGACTGA"
    na_only = calculate_tm_nn(seq, {"saltConcentration": 50, "magnesiumConcentration": 1.5, "dntpTotal": 0.8})
    full    = calculate_tm_nn(seq, {"saltConcentration": 50, "kPlusConc": 50, "bufferPH": 8.4,
                                    "magnesiumConcentration": 1.5, "dntpTotal": 0.8})
    # Adding 50 mM K+ + Tris raises the effective monovalent → higher Tm (~1–2 °C).
    assert full > na_only
    assert 0.5 < (full - na_only) < 4.0
