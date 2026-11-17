"""
test_mirbase_source.py — one miRBase release behind lookup, BLAST DB and overhang index
(algorithm 3.8.2, PROMPT_thesis_freeze_4.0.0 §3.3).
"""
import os

import pytest

import routes.mirbase as mirbase_route
from algorithm.design_pipeline import run
from algorithm.mirbase_source import release_info, sequence_warning
from algorithm.specificity_check.overhang_collision import _load_index
from app import app
from db import local_db

_MIR21 = "UAGCUUAUCAGACUGAUGUUGA"


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_release_info_from_index_metadata():
    info = release_info()
    assert info["mirbase_release"] == "22.1"
    assert info["mature_fa_sha256"].startswith("3c521fc9")


def test_known_sequence_has_no_warning():
    assert sequence_warning(_MIR21, "hsa-miR-21-5p") is None
    assert sequence_warning(_MIR21, "") is None


def test_sequence_outside_release_warns():
    w = sequence_warning("UAGCUUAUCAGACUGAUGUUGAAAAA", "")
    assert w and w["field"] == "sequence_not_in_mirbase_release"
    assert "22.1" in w["message"]


def test_name_with_other_sequence_warns():
    # the 23-nt miR-155-5p of miRBase ≤ 21; Release 22.1 annotates 24 nt
    w = sequence_warning("UUAAUGCUAAUCGUGAUAGGGGU", "hsa-miR-155-5p")
    assert w and "hsa-miR-155-5p" in w["message"] and "24 nt" in w["message"]


def test_design_carries_warning_and_provenance():
    res = run("UAGCUUAUCAGACUGAUGUUGAAAAA", {}, mirna_name="")
    fields = [w["field"] for w in res.get("global_warnings", [])]
    assert "sequence_not_in_mirbase_release" in fields
    ok = run(_MIR21, {}, mirna_name="hsa-miR-21-5p")
    assert "sequence_not_in_mirbase_release" not in [w["field"] for w in ok["global_warnings"]]
    prov = ok["metadata"]["provenance"]
    assert prov["mirbase_release"] == "22.1"
    assert prov["mature_fa_sha256"].startswith("3c521fc9")


@pytest.mark.skipif(not local_db.exists(), reason="local miRBase database not built")
def test_route_local_reports_release(client):
    d = client.get("/api/mirbase/hsa-miR-21-5p").get_json()
    assert d["source"] == "local"
    assert d["sequence"] == _MIR21
    assert d["mirbase_release"] == "22.1"


def test_route_online_fallback_is_labelled_and_not_cached(client, monkeypatch):
    fetched = {"id": "hsa-miR-test-1", "accession": "MIMAT9999999", "sequence": "ACGUACGUACGUACGUACGU",
               "family": "", "species": "Homo sapiens", "length": 20}
    monkeypatch.setattr(mirbase_route.local_db, "lookup", lambda _id: None)
    monkeypatch.setattr(mirbase_route, "_fetch_mirbase", lambda _id: dict(fetched))
    written = []
    monkeypatch.setattr(mirbase_route.local_db, "upsert", lambda data: written.append(data))
    d = client.get("/api/mirbase/hsa-miR-test-1").get_json()
    assert d["source"] == "online"
    assert d["mirbase_release"] == "unknown"
    assert "release unknown" in d["note"]
    assert written == []


@pytest.mark.skipif(not local_db.exists(), reason="local miRBase database not built")
def test_local_database_matches_index_for_hsa():
    hsa = _load_index()["mature"]["hsa"]
    with local_db._conn() as c:
        db = {r["name"]: r["sequence"] for r in c.execute(
            "SELECT name, sequence FROM mirna WHERE name LIKE 'hsa-%'")}
    assert {n: s for n, s in hsa.items() if db.get(n) != s} == {}
    assert set(db) == set(hsa)   # no extra, unversioned rows (e.g. cached online hits)
