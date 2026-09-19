"""PART E tests — /api/visualize route (SPEC §E.8, §F PART E)."""
import os
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app  # noqa: E402


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def _golden(**over):
    req = {
        "mirna_sequence": "UAGCAGCACGUAAAUAUUGGCG",
        "mirna_id": "hsa-miR-16-5p",
        "stemloop_rt": "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACCGCCAA",
        "forward": "GGCGTAGCAGCACGTAAA",
        "forward_binding_length": 14,
        "universal_reverse": "CCAGTGCAGGGTCCGAGGTA",
        "predicted_amplicon_tm": 79.4,
        "dimer_tm_warning": None,
        "panels": ["reaction", "melting", "gel"],
        "theme": "light",
    }
    req.update(over)
    return req


def test_golden_200_and_meta(client):
    r = client.post("/api/visualize", json=_golden())
    assert r.status_code == 200
    body = r.get_json()
    assert set(body["panels"]) == {"reaction", "melting", "gel"}
    for svg in body["panels"].values():
        ET.fromstring(svg)                       # every panel is well-formed
    meta = body["meta"]
    assert meta["amplicon_length"] == 63
    assert meta["gc_percent"] == 57.1
    assert meta["peak_temperature"] == 79.4
    assert [reg["name"] for reg in meta["regions"]] == ["F_tail", "miRNA", "stemloop", "universal"]
    assert meta["size_warning"] is False


def test_theme_excluded_from_cache(client):
    a = client.post("/api/visualize", json=_golden(theme="light")).get_json()
    b = client.post("/api/visualize", json=_golden(theme="dark")).get_json()
    assert a == b                                # theme not in key → identical SVG


def test_determinism(client):
    a = client.post("/api/visualize", json=_golden()).get_json()
    b = client.post("/api/visualize", json=_golden()).get_json()
    assert a["panels"]["reaction"] == b["panels"]["reaction"]


# ── six error paths → correct error_code (SPEC §E.8) ────────────────────────────

def test_error_rt_primer_length(client):
    r = client.post("/api/visualize", json=_golden(stemloop_rt="GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACCGCC"))
    assert r.status_code == 422 and r.get_json()["error_code"] == "RT_PRIMER_LENGTH"


def test_five_nt_overhang_renders(client):
    """A 5-nt overhang (49-nt RT primer) is supported since 2026-09-18 (SCI-08)."""
    r = client.post("/api/visualize", json=_golden(stemloop_rt="GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACCGCCA"))
    assert r.status_code == 200, r.get_json()


def test_error_overhang_mismatch(client):
    bad = "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACCGCCAT"  # 50 nt, wrong last base
    r = client.post("/api/visualize", json=_golden(stemloop_rt=bad))
    assert r.status_code == 422 and r.get_json()["error_code"] == "OVERHANG_MISMATCH"


def test_error_forward_binding_mismatch(client):
    r = client.post("/api/visualize", json=_golden(forward="GGCGTTGCAGCACGTAAA"))
    assert r.status_code == 422 and r.get_json()["error_code"] == "FORWARD_BINDING_MISMATCH"


def test_error_forward_binding_range(client):
    r = client.post("/api/visualize", json=_golden(forward="GGCGTAGCAGCA", forward_binding_length=11))
    assert r.status_code == 422 and r.get_json()["error_code"] == "FORWARD_BINDING_RANGE"


def test_error_universal_site_ambiguous(client):
    r = client.post("/api/visualize", json=_golden(universal_reverse="ACGTACGTACGTACGTACGT"))
    assert r.status_code == 422 and r.get_json()["error_code"] == "UNIVERSAL_SITE_AMBIGUOUS"


def test_error_invalid_mirna_id_blocks_xss(client):
    r = client.post("/api/visualize", json=_golden(mirna_id='"><script>alert(1)</script>'))
    assert r.status_code == 422 and r.get_json()["error_code"] == "INVALID_MIRNA_ID"


def test_missing_amplicon_tm_for_melting(client):
    r = client.post("/api/visualize", json=_golden(predicted_amplicon_tm=None))
    assert r.status_code == 422 and r.get_json()["error_code"] == "MISSING_AMPLICON_TM"


def test_reaction_only_no_tm_needed(client):
    r = client.post("/api/visualize", json=_golden(panels=["reaction"], predicted_amplicon_tm=None))
    assert r.status_code == 200
    assert set(r.get_json()["panels"]) == {"reaction"}
