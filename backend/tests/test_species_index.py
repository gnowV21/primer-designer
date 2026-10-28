# ================================================================
# tests/test_species_index.py — all-species overhang index (v3.4.0)
#
# The assay-level screen and BLAST read the same miRBase release; a viral
# target is screened together with its host's miRNAs; species prefixes of
# 3–5 characters (kshv, mdv1) are recognised.
# ================================================================

import json
import os

import pytest

from algorithm.constants import VIRUS_HOST_SPECIES
from algorithm.specificity_check import blast_offtarget as bo
from algorithm.specificity_check.overhang_collision import check_overhang_collision, _load_index

_BACKEND = os.path.join(os.path.dirname(__file__), "..")


def test_index_matches_blast_db_release():
    meta = _load_index()["_metadata"]
    with open(os.path.join(_BACKEND, "data", "blast_db", "metadata.json"), encoding="utf-8") as f:
        blast = json.load(f)
    assert meta["mirbase_release"] == blast["mirbase_version"] == "22.1"
    assert meta["n_total"] == blast["sequences_count"]["mirbase_multi"] == 48885
    assert len(meta["mature_fa_sha256"]) == 64
    assert len(meta["species"]) == 271


def test_every_virus_host_is_in_the_index():
    species = set(_load_index()["mature"])
    for virus, host in VIRUS_HOST_SPECIES.items():
        assert virus in species, virus
        assert host in species, f"{virus} → {host}"


@pytest.mark.parametrize("mirna_id,prefix", [
    ("hsa-miR-21-5p", "hsa-"), ("kshv-miR-K12-1", "kshv-"),
    ("mdv1-miR-M4-5p", "mdv1-"), ("hhv6b-miR-Ro6-1", "hhv6b-"),
])
def test_species_prefixes_of_three_to_five_chars(mirna_id, prefix):
    assert bo._extract_species_prefix(mirna_id) == prefix


def test_viral_target_screens_host_mirnas():
    r = check_overhang_collision("CCUGGACCUUGACUAUGAAACA", "ebv-miR-BART7-5p", {},
                                 forward_specific_len=15)
    assert r["screened_species"] == ["ebv", "hsa"]
    assert r["n_screened"] > 2600
    assert "host (hsa)" in r["annotation_note"]


def test_annotation_note_only_outside_reference_species():
    assert check_overhang_collision("UAGCUUAUCAGACUGAUGUUGA", "hsa-miR-21-5p", {},
                                    forward_specific_len=15)["annotation_note"] is None
    note = check_overhang_collision("UAGCUUAUCAGACUGAUGUUGA", "ssc-miR-21", {},
                                    forward_specific_len=15)["annotation_note"]
    assert "457 mature miRNAs for ssc" in note


def test_species_without_index_entries_is_no_index_data():
    r = check_overhang_collision("UAGCUUAUCAGACUGAUGUUGA", "", {}, forward_specific_len=15,
                                 species="zzz")
    assert r["worst_assay_label"] == "no_index_data"


def test_blast_keeps_host_hits_for_viral_target(monkeypatch):
    hit = {"subject_id": "hsa-miR-x", "identity_pct": 100.0, "length": 14, "mismatches": 0,
           "gap_opens": 0, "q_start": 9, "q_end": 22, "s_start": 1, "s_end": 14,
           "evalue": 1.0, "bitscore": 30.0, "subject_seq": "CCTGGACCTTGACT",
           "query_seq": "CCTGGACCTTGACT"}
    monkeypatch.setattr(bo, "_db_exists", lambda p: True)
    monkeypatch.setattr(bo, "run_blastn", lambda *a, **k: [hit])
    monkeypatch.setattr(bo, "fetch_sequences",
                        lambda ids, *a, **k: {"hsa-miR-x": "CCTGGACCTTGACTAAAAAAAA"})
    r = bo.check_offtarget("ACGTACGTCCTGGACCTTGACT", None, "ebv-miR-BART7-5p",
                           target_sequence="CCTGGACCTTGACTATGAAACA")
    assert r["classification"]["host_species"] == "hsa"
    assert r["summary"]["cross_species_excluded"] == 0


def test_route_accepts_long_species_codes(monkeypatch):
    from app import app
    import routes.blast_check as rb
    seen = {}
    monkeypatch.setattr(rb, "check_offtarget",
                        lambda **kw: seen.update(kw) or {"summary": {"overall_risk": "SAFE"}})
    monkeypatch.setattr(rb._cache, "get_result", lambda *a, **k: None)
    monkeypatch.setattr(rb._cache, "set_result", lambda *a, **k: None)
    with app.test_client() as c:
        r = c.post("/api/blast-check", json={"forward_primer": "ACGTACGTCCTGGACCTTGACT",
                                             "species": "kshv"})
    assert r.status_code == 200 and seen["species"] == "kshv"
