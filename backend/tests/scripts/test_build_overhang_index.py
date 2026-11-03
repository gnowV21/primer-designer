# ================================================================
# tests/scripts/test_build_overhang_index.py — SPEC_week2 C3
# Tests the overhang-index builder on a mock FASTA (no download).
# ================================================================

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.build_overhang_index import build_index, _bucket_report, _dna
from scripts.build_mirbase_data import parse_mature_fa

FIXTURES = Path(os.path.dirname(__file__)) / ".." / "fixtures"
MATURE_MOCK = FIXTURES / "mature_mock.fa"


def test_species_filter_hsa_only():
    parsed = parse_mature_fa(MATURE_MOCK, "hsa")
    mature = build_index(parsed, ["hsa"])
    assert set(mature) == {"hsa"}
    # fixture hsa entries: let-7a-5p, let-7a-3p, let-7b-5p, let-7c-5p, miR-17/18a/19a/21
    assert len(mature["hsa"]) == 8
    assert "mmu-let-7a-5p" not in mature["hsa"]


def test_species_filter_multi():
    parsed = parse_mature_fa(MATURE_MOCK, "hsa,mmu")
    mature = build_index(parsed, ["hsa", "mmu"])
    assert set(mature) == {"hsa", "mmu"}
    assert len(mature["hsa"]) == 8
    assert mature["mmu"] == {"mmu-let-7a-5p": "UGAGGUAGUAGGUUGUAUAGUU"}


def test_rt_overhang_bucketing_groups_identical_3prime():
    # hsa-let-7a-5p and mmu-let-7a-5p share the exact sequence -> same 3'-6mer bucket.
    parsed = parse_mature_fa(MATURE_MOCK, "hsa,mmu")
    combined = {**build_index(parsed, ["hsa"])["hsa"], **build_index(parsed, ["mmu"])["mmu"]}
    # let-7a 3'-6mer = ATAGTT (dna); let-7c = ATGGTT -> different bucket
    assert _dna(combined["hsa-let-7a-5p"][-6:]) == "ATAGTT"
    assert _dna(combined["hsa-let-7c-5p"][-6:]) == "ATGGTT"
    rep = _bucket_report(combined)
    assert rep["n_buckets"] >= 1
    assert rep["largest_size"] >= 2   # the ATAGTT bucket has let-7a (hsa) + let-7a (mmu)


def test_full_build_writes_expected_schema(tmp_path):
    parsed = parse_mature_fa(MATURE_MOCK, "hsa,mmu")
    mature = build_index(parsed, ["hsa", "mmu"])
    out = {"_metadata": {"species": ["hsa", "mmu"], "n_mirnas": {k: len(v) for k, v in mature.items()}},
           "mature": mature}
    p = tmp_path / "idx.json"
    p.write_text(json.dumps(out), encoding="utf-8")
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert set(loaded) == {"_metadata", "mature"}
    assert loaded["_metadata"]["n_mirnas"]["hsa"] == 8
    assert loaded["mature"]["hsa"]["hsa-miR-21-5p"] == "UAGCUUAUCAGACUGAUGUUGA"
