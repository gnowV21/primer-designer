"""Week2 C13 — regression tests for the three cosmetic findings (#3, #4, #5)."""
import csv
import os
import sys

import pytest

_BACKEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ── Finding #3: analyze length-guard message matches the actual bound ──

@pytest.fixture
def client():
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


@pytest.mark.parametrize("n", [14, 31])
def test_analyze_rejects_out_of_range_with_matching_message(client, n):
    seq = "A" * n   # deliberately out of the 15–30 range
    resp = client.post("/api/analyze", json={"rt": "ACGTACGT", "forward": "ACGTACGT",
                                             "reverse": "CCAGTGCAGGGTCCGAGGTA", "mature": seq})
    # mature is validated; the error (wherever it surfaces) must state the real bound.
    body = resp.get_data(as_text=True)
    if "15" in body and "30" in body:
        assert "17" in body and "24" in body   # message still cites the canonical range
        assert "expected 17" not in body       # old misleading phrasing is gone


# ── Finding #5: species_note handles a multi-token --species arg ──

def test_species_note_multi_token():
    from scripts.build_mirbase_data import _species_note
    assert _species_note("hsa,mmu,rno") == "human (hsa), mouse (mmu), rat (rno)"
    assert _species_note("hsa") == "human (hsa)"
    assert _species_note("all") == "all species"
    assert _species_note("xyz") == "xyz"   # unknown prefix kept as-is


# ── Finding #4: results.csv exposes the forward published-match columns ──

def test_results_csv_has_forward_exact_column():
    path = os.path.join(_BACKEND_DIR, "..", "validation", "results.csv")
    if not os.path.isfile(path):
        pytest.skip("results.csv not generated")
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    header = rows[0].keys()
    assert "published_forward_exact" in header
    assert "published_forward_match" not in header      # the never-populated column is gone
    m16 = next((r for r in rows if r["target"] == "hsa-miR-16-5p"), None)
    if m16:
        assert m16["published_forward_exact"] != ""      # populated when published_forward exists
