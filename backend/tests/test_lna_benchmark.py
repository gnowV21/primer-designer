# ================================================================
# tests/test_lna_benchmark.py — A2 LNA benchmark
#
# Validates algorithm/lna_tm.py against EXPERIMENTALLY-MEASURED melting
# temperatures, per docs/archive/PLAN_GapA_ScientificCompleteness.md §A2 "Benchmark bắt buộc".
#
# Ground truth: McTigue, Peterson & Kahn 2004, Biochemistry 43(18):5388-5405,
# Table 1 — singly LNA-substituted DNA oligonucleotides hybridised to their
# all-DNA complements, measured by UV melting in 1 M Na+, 5 µM total strand.
# The NN parameters themselves are Owczarzy et al. 2011 Table 2 (the full
# LNA·DNA:DNA set derived from McTigue's 32NN differentials).
#
# Two layers:
#   1. SANITY INVARIANTS — cheap physics checks (empty→equal, LNA stabilises,
#      monotonic in count) that catch a sign/transcription error immediately.
#   2. EMPIRICAL — against McTigue Table 1:
#        · ΔTm (LNA effect, isolates the LNA parameters): RMSD ≤ 1.0 °C and
#          each |ΔTm_pred − ΔTm_meas| ≤ 2.5 °C.  Paper reports RMSD(ΔTm)=0.85 °C.
#        · Absolute Tm: RMSD ≤ 2.0 °C.  Paper reports RMSD(Tm)=1.47 °C (method 4).
#          Per-oligo absolute error is limited by the DNA-baseline NN model
#          (SantaLucia 1998), not the LNA parameters, so absolute is gated on
#          RMSD rather than per-oligo, matching the paper's own headline.
# ================================================================

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.lna_tm import calc_lna_tm

# McTigue 2004 Table 1 conditions: 1 M Na+, total strand C_T = 5 µM.
_MCTIGUE_PARAMS = {
    "saltConcentration":      1000.0,   # mM Na+
    "magnesiumConcentration":    0.0,
    "dntpTotal":                 0.0,
    "primerConcentration":    5000.0,   # nM (5 µM total strand)
}

_PARAMS = {
    "saltConcentration":      50.0,
    "magnesiumConcentration":  1.5,
    "dntpTotal":               0.8,
    "primerConcentration":   200.0,
}


# ── Layer 1: sanity invariants ────────────────────────────────────

def test_empty_positions_equal_dna_exactly():
    """No LNA → tm_lna must equal tm_dna exactly (delta_tm == 0)."""
    res = calc_lna_tm("ACGTACGTACGT", [], _PARAMS)
    assert res["tm_dna"] == res["tm_lna"]
    assert res["delta_tm"] == 0.0


@pytest.mark.parametrize("seq,pos", [
    ("GGACCTCGAC", [4]),    # LNA-C (strongly stabilising base)
    ("CGCTGTTACGC", [4]),   # LNA-T
    ("GCAGGTCTGC", [3]),    # LNA-G, GCAG|G context
    ("ATCTATCCGGC", [7]),   # LNA-C
])
def test_single_lna_raises_tm(seq, pos):
    """A stabilising LNA substitution increases Tm (delta_tm > 0)."""
    res = calc_lna_tm(seq, pos, _PARAMS)
    assert res["tm_lna"] is not None
    assert res["delta_tm"] > 0.0, f"LNA at {pos} in {seq} did not raise Tm"


def test_tm_monotonic_in_lna_count():
    """More (non-adjacent) LNA substitutions must not lower Tm."""
    seq = "ACGTACGTACGTACGT"
    steps = [[], [2], [2, 6], [2, 6, 10]]
    tms = [calc_lna_tm(seq, p, _PARAMS)["tm_lna"] for p in steps]
    for earlier, later in zip(tms, tms[1:]):
        assert later >= earlier - 1e-9, f"Tm dropped when adding LNA: {tms}"


# ── Layer 2: empirical ground truth (McTigue 2004, Table 1) ───────
# Each row: (name, LNA-marked sequence, measured_Tm, dna_ref_measured_Tm).
# The 'L' is placed immediately AFTER the LNA base (paper notation), so the
# 0-based LNA index is (position of 'L') − 1 and the DNA sequence is the string
# with 'L' removed. Parsing at runtime avoids hand-transcription errors.
_G = MCTIGUE_GROUND_TRUTH_RAW = [
    ("L1a",  "GTCGLAACAGC",   51.2, 51.8),
    ("L1b",  "GTCGALACAGC",   53.8, 51.8),
    ("L1c",  "GTCGAALCAGC",   53.9, 51.8),
    ("L1d",  "GTCGAACLAGC",   56.1, 51.8),
    ("L2a",  "ATCTLATCCGGC",  57.3, 52.7),
    ("L2b",  "ATCTALTCCGGC",  54.5, 52.7),
    ("L2c",  "ATCTATLCCGGC",  55.4, 52.7),
    ("L2d",  "ATCTATCLCGGC",  56.1, 52.7),
    ("L2e",  "ATCTATCCLGGC",  55.9, 52.7),
    ("L3a",  "CGCTLGTTACGC",  60.5, 56.1),
    ("L3b",  "CGCTGLTTACGC",  58.4, 56.1),
    ("L3c",  "CGCTGTLTACGC",  59.2, 56.1),
    ("L3d",  "CGCTGTTLACGC",  59.2, 56.1),
    ("L3e",  "CGCTGTTALCGC",  57.6, 56.1),
    ("L4a",  "GGACLCTCGAC",   58.7, 53.6),
    ("L4b",  "GGACCLTCGAC",   57.9, 53.6),
    ("L4c",  "GGACCTLCGAC",   55.5, 53.6),
    ("L4d",  "GGACCTCLGAC",   57.8, 53.6),
    ("L5a1", "CCALTTGCTACC",  50.6, 50.9),
    ("L5a",  "CCATLTGCTACC",  53.7, 50.9),
    ("L5b",  "CCATTLGCTACC",  54.4, 50.9),
    ("L5c",  "CCATTGLCTACC",  52.5, 50.9),
    ("L5d",  "CCATTGCLTACC",  56.0, 50.9),
    ("L7a",  "GGAACALAGATGC", 55.8, 54.9),
    ("L7b",  "GGAACAALGATGC", 57.6, 54.9),
    ("L7c",  "GGAACAAGLATGC", 58.6, 54.9),
    ("L7d",  "GGAACAAGALTGC", 57.6, 54.9),
    ("L9a",  "GCALGGTCTGC",   57.7, 54.6),
    ("L9b",  "GCAGLGTCTGC",   61.5, 54.6),
    ("L9c",  "GCAGGLTCTGC",   58.4, 54.6),
    ("L10a", "GTAGLCGATGTA",  53.9, 51.9),
    ("L10b", "GTAGCLGATGTA",  56.6, 51.9),
    ("L10c", "GTAGCGLATGTA",  53.6, 51.9),
    ("L13d", "TTGGGALGTAGC",  56.9, 51.1),
    ("L13e", "TTGGGAGLTAGC",  54.8, 51.1),
    ("L14d", "CTAAATLAGCG",   44.9, 40.6),
    ("L16c", "ATTTGALCTCAG",  49.5, 46.5),
    ("L16d", "ATTTGACLTCAG",  51.1, 46.5),
]


def _parse(raw):
    """('...L...') → (dna_sequence, lna_index_0based)."""
    idx = raw.index("L") - 1
    return raw.replace("L", ""), idx


def _rms(xs):
    return (sum(x * x for x in xs) / len(xs)) ** 0.5


@pytest.mark.parametrize("name,raw,meas_tm,dna_tm", _G)
def test_delta_tm_per_oligo_within_2_5C(name, raw, meas_tm, dna_tm):
    """
    Per-oligo LNA effect (ΔTm) prediction vs McTigue 2004 measured ΔTm.
    ΔTm isolates the LNA parameters from the DNA-baseline NN error.
    """
    seq, idx = _parse(raw)
    res = calc_lna_tm(seq, [idx], _MCTIGUE_PARAMS)
    assert res["tm_lna"] is not None, f"{name}: prediction failed"
    meas_delta = meas_tm - dna_tm
    err = abs(res["delta_tm"] - meas_delta)
    assert err <= 2.5, (
        f"{name}: ΔTm pred {res['delta_tm']} vs meas {meas_delta:.1f} "
        f"(err {err:.1f} °C > 2.5)"
    )


def test_delta_tm_rmsd_within_1C():
    """Aggregate ΔTm accuracy must match the paper (RMSD(ΔTm)=0.85 °C)."""
    errs = []
    for _name, raw, meas_tm, dna_tm in _G:
        seq, idx = _parse(raw)
        res = calc_lna_tm(seq, [idx], _MCTIGUE_PARAMS)
        errs.append(res["delta_tm"] - (meas_tm - dna_tm))
    rmsd = _rms(errs)
    assert rmsd <= 1.0, f"ΔTm RMSD {rmsd:.2f} °C exceeds 1.0 °C"


def test_absolute_tm_rmsd_within_2C():
    """
    Absolute Tm accuracy vs McTigue measured Tm (paper method 4: RMSD 1.47 °C).
    Gated on RMSD, not per-oligo, because absolute error is bounded by the
    SantaLucia 1998 DNA-baseline model rather than the LNA parameters.
    """
    errs = []
    for _name, raw, meas_tm, _dna_tm in _G:
        seq, idx = _parse(raw)
        res = calc_lna_tm(seq, [idx], _MCTIGUE_PARAMS)
        errs.append(res["tm_lna"] - meas_tm)
    rmsd = _rms(errs)
    assert rmsd <= 2.0, f"absolute Tm RMSD {rmsd:.2f} °C exceeds 2.0 °C"
