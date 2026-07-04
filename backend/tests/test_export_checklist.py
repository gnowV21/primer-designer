"""Tests for MIQE validation checklist in export.py (Phase 7 PART E)."""

import io
import sys
import os
import pytest

_BACKEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


@pytest.fixture
def app():
    from app import app as flask_app
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_results():
    return {
        "top3": [{
            "rank": 1,
            "sequence": "ACGTACGTACGT",
            "length": 12,
            "tm_full": 60.0,
            "gc_percent": 50.0,
            "amplicon_size": 90,
            "total_score": 0.85,
            "grade": "A",
            "specific_length": 12,
            "structure_checks": {
                "hairpin": {"dg": -1.5},
                "self_dimer": {"dg": -0.8},
            },
        }],
        "stemloop_rt": {
            "sequence": "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACAAAACT",
            "length": 50,
            "tm_full": 72.0,
            "gc_percent": 52.0,
            "mfe": -11.5,
            "mfe_method": "primer3-py",
        },
        "universal_reverse": {
            "sequence": "CCAGTGCAGGGTCCGAGGTA",
            "length": 20,
            "tm": 68.0,
            "gc_percent": 60.0,
        },
        "metadata": {"mirna_id": "hsa-miR-21-5p", "algorithm_version": "3.0.0"},
        "specificity_warnings": {
            "cross_reactivity": {
                "cross_reactivity": [
                    {"sibling": "hsa-miR-21-3p", "risk": "LOW", "mismatch": 2, "delta_tm": 6.0},
                ],
            }
        },
    }


class TestCSVChecklist:
    def test_csv_contains_checklist_header(self, client, sample_results):
        resp = client.post("/api/export", json={
            "format": "csv", "results": sample_results, "include_checklist": True,
        })
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "VALIDATION CHECKLIST" in body

    def test_csv_has_8_checklist_items(self, client, sample_results):
        resp = client.post("/api/export", json={
            "format": "csv", "results": sample_results, "include_checklist": True,
        })
        body = resp.data.decode("utf-8")
        # Find the checklist block
        checklist_start = body.find("# VALIDATION CHECKLIST")
        assert checklist_start != -1
        checklist_block = body[checklist_start:]
        # Count data rows (not header/comment lines)
        rows = [
            line for line in checklist_block.splitlines()
            if line and not line.startswith("#") and not line.startswith("Item,")
        ]
        assert len(rows) == 8, f"Expected 8 checklist rows, got {len(rows)}: {rows}"

    def test_csv_specificity_autofill(self, client, sample_results):
        resp = client.post("/api/export", json={
            "format": "csv", "results": sample_results, "include_checklist": True,
        })
        body = resp.data.decode("utf-8")
        # Specificity row should mention LOW (worst risk from mock data)
        assert "LOW" in body

    def test_csv_checklist_omitted_when_false(self, client, sample_results):
        resp = client.post("/api/export", json={
            "format": "csv", "results": sample_results, "include_checklist": False,
        })
        body = resp.data.decode("utf-8")
        assert "VALIDATION CHECKLIST" not in body

    def test_format_whitelist_still_enforced(self, client, sample_results):
        resp = client.post("/api/export", json={
            "format": "html", "results": sample_results,
        })
        assert resp.status_code == 400


class TestPDFChecklist:
    def test_pdf_bytes_returned(self, client, sample_results):
        try:
            import reportlab  # noqa: F401
        except ImportError:
            pytest.skip("reportlab not installed")
        resp = client.post("/api/export", json={
            "format": "pdf", "results": sample_results, "include_checklist": True,
        })
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "application/pdf"
        # PDF magic bytes
        assert resp.data[:4] == b"%PDF"

    def test_pdf_without_checklist(self, client, sample_results):
        try:
            import reportlab  # noqa: F401
        except ImportError:
            pytest.skip("reportlab not installed")
        resp = client.post("/api/export", json={
            "format": "pdf", "results": sample_results, "include_checklist": False,
        })
        assert resp.status_code == 200
        assert resp.data[:4] == b"%PDF"
