"""PART A tests — coordinate model (SPEC_visualization §A.6, §A.7).

Run from backend/:  python -m pytest visualization/test_coordinates.py -q
"""
import os
import sys

import pytest

# Make backend/ importable so `algorithm.*` and `visualization.*` resolve.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.constants import STEMLOOP_BODY, UNIVERSAL_REVERSE  # noqa: E402
from algorithm.sequence_utils import reverse_complement as rc      # noqa: E402
from visualization.coordinates import (                            # noqa: E402
    build_amplicon_model, VisualizationError,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def make_valid(m: str, k: int = 14, tail: str = "GGCG", o: int = 6) -> dict:
    """Construct a structurally valid /api/visualize input for a DNA miRNA `m`."""
    return dict(
        mirna_sequence=m,
        stemloop_rt=STEMLOOP_BODY + rc(m[-o:]),
        forward=tail + m[:k],
        forward_binding_length=k,
        universal_reverse=UNIVERSAL_REVERSE,
    )


# ── §A.6 golden test — hsa-miR-16-5p ────────────────────────────────────────────

def test_golden_mir16():
    model = build_amplicon_model(
        mirna_sequence="UAGCAGCACGUAAAUAUUGGCG",
        stemloop_rt="GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACCGCCAA",
        forward="GGCGTAGCAGCACGTAAA",
        forward_binding_length=14,
        universal_reverse="CCAGTGCAGGGTCCGAGGTA",
    )

    assert model.mirna_dna == "TAGCAGCACGTAAATATTGGCG"
    assert len(model.stemloop_rt) == 50
    assert model.overhang == "CGCCAA"
    assert model.stemloop_body == STEMLOOP_BODY

    assert len(model.cdna) == 66
    assert model.cdna == "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACCGCCAATATTTACGTGCTGCTA"

    assert len(model.sense_strand) == 70
    assert model.sense_strand == (
        "GGCGTAGCAGCACGTAAATATTGGCGGTCGTATCCAGTGCGAATACCTCGGACCCTGCACTGGATACGAC"
    )

    assert model.universal_offset == 43
    assert len(model.amplicon) == 63
    assert model.amplicon == (
        "GGCGTAGCAGCACGTAAATATTGGCGGTCGTATCCAGTGCGAATACCTCGGACCCTGCACTGG"
    )

    assert model.tail == "GGCG"
    assert model.gc_percent == 57.1
    assert model.size_warning is False

    # Regions (start, end, name) — §A.6
    r = model.regions
    assert (r[0].start, r[0].end, r[0].name) == (0, 4, "F_tail")
    assert (r[1].start, r[1].end, r[1].name) == (4, 26, "miRNA")
    assert (r[2].start, r[2].end, r[2].name) == (26, 43, "stemloop")
    assert (r[3].start, r[3].end, r[3].name) == (43, 63, "universal")

    # Region sequences
    amp = model.amplicon
    assert amp[r[0].start:r[0].end] == "GGCG"
    assert amp[r[1].start:r[1].end] == "TAGCAGCACGTAAATATTGGCG"
    assert amp[r[2].start:r[2].end] == "GTCGTATCCAGTGCGAA"
    assert amp[r[3].start:r[3].end] == "TACCTCGGACCCTGCACTGG"


def test_golden_stages():
    model = build_amplicon_model(**make_valid("TAGCAGCACGTAAATATTGGCG"))
    assert [s.id for s in model.stages] == [0, 1, 2, 3, 4]
    stage1 = model.stages[1]
    assert len(stage1.pairings) == 6            # 6-nt overhang duplex
    assert stage1.synthesis_direction == "left"  # RT extends leftward
    assert model.stages[3].synthesis_direction == "right"


# ── §A.7 — 4 other miRNAs, L = 21..24 ───────────────────────────────────────────

_BASE = "AGCTTGCAACGATCGTAGCATCGATCGTTAGCACGT"  # arbitrary valid DNA, long enough


@pytest.mark.parametrize("L", [21, 22, 23, 24])
def test_other_lengths_region_sum(L):
    m = _BASE[:L]
    model = build_amplicon_model(**make_valid(m))
    total = sum(reg.length for reg in model.regions)
    assert total == len(model.amplicon)       # §A.7 property
    assert model.regions[1].length == L        # R2 == full miRNA


# ── §A.7 property test — regions tile the amplicon exactly ───────────────────────

@pytest.mark.parametrize("k", [12, 13, 14, 15, 16, 17])
def test_regions_partition_amplicon(k):
    m = _BASE[:24]
    model = build_amplicon_model(**make_valid(m, k=k))
    regs = model.regions
    # contiguous, non-overlapping, covering [0, len(amplicon))
    assert regs[0].start == 0
    assert regs[-1].end == len(model.amplicon)
    for a, b in zip(regs, regs[1:]):
        assert a.end == b.start
    assert sum(r.length for r in regs) == len(model.amplicon)


# ── §A.6 trap tests — each must raise the correct error_code ─────────────────────

def test_trap_A1_rt_primer_length():
    v = make_valid("TAGCAGCACGTAAATATTGGCG")
    v["stemloop_rt"] = v["stemloop_rt"][:-2]   # 48 nt — 4-nt overhang, below 5–7
    with pytest.raises(VisualizationError) as e:
        build_amplicon_model(**v)
    assert e.value.error_code == "RT_PRIMER_LENGTH"


@pytest.mark.parametrize("o", [5, 6, 7])
def test_overhang_length_read_from_primer(o):
    """5–7 nt overhangs are supported; the length comes from the primer itself."""
    m = "TAGCAGCACGTAAATATTGGCG"
    model = build_amplicon_model(**make_valid(m, o=o))
    assert model.overhang == rc(m[-o:])
    assert model.stemloop_body == STEMLOOP_BODY
    assert model.cdna == STEMLOOP_BODY + rc(m)          # full miRNA complement either way
    assert len(model.stages[1].pairings) == o


def test_trap_A1_overhang_too_long():
    m = "TAGCAGCACGTAAATATTGGCG"
    with pytest.raises(VisualizationError) as e:
        build_amplicon_model(**make_valid(m, o=8))
    assert e.value.error_code == "RT_PRIMER_LENGTH"


def test_trap_A2_overhang_mismatch():
    v = make_valid("TAGCAGCACGTAAATATTGGCG")
    s = v["stemloop_rt"]
    wrong_last = "A" if s[-1] != "A" else "C"
    v["stemloop_rt"] = s[:-1] + wrong_last     # 50 nt but wrong overhang
    with pytest.raises(VisualizationError) as e:
        build_amplicon_model(**v)
    assert e.value.error_code == "OVERHANG_MISMATCH"


def test_trap_A3_forward_binding_mismatch():
    v = make_valid("TAGCAGCACGTAAATATTGGCG", k=14)
    # Flip the first specific base so F[-k:] != m[:k]
    f = v["forward"]
    flipped = "T" if f[-14] != "T" else "G"
    v["forward"] = f[:-14] + flipped + f[-13:]
    with pytest.raises(VisualizationError) as e:
        build_amplicon_model(**v)
    assert e.value.error_code == "FORWARD_BINDING_MISMATCH"


@pytest.mark.parametrize("bad_k", [11, 18])
def test_trap_A4_forward_binding_range(bad_k):
    m = "TAGCAGCACGTAAATATTGGCG"
    v = dict(
        mirna_sequence=m,
        stemloop_rt=STEMLOOP_BODY + rc(m[-6:]),
        forward="GGCG" + m[:bad_k],
        forward_binding_length=bad_k,
        universal_reverse=UNIVERSAL_REVERSE,
    )
    with pytest.raises(VisualizationError) as e:
        build_amplicon_model(**v)
    assert e.value.error_code == "FORWARD_BINDING_RANGE"


def test_trap_A5_universal_site_ambiguous():
    v = make_valid("TAGCAGCACGTAAATATTGGCG")
    v["universal_reverse"] = "ACGTACGTACGTACGTACGT"   # rc not present in sense
    with pytest.raises(VisualizationError) as e:
        build_amplicon_model(**v)
    assert e.value.error_code == "UNIVERSAL_SITE_AMBIGUOUS"


def test_error_to_dict_carries_expected_actual():
    v = make_valid("TAGCAGCACGTAAATATTGGCG")
    v["stemloop_rt"] = v["stemloop_rt"][:-2]
    with pytest.raises(VisualizationError) as e:
        build_amplicon_model(**v)
    d = e.value.to_dict()
    assert d["error_code"] == "RT_PRIMER_LENGTH"
    assert "expected" in d and "actual" in d
