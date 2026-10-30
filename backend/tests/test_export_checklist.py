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

    def test_csv_has_miqe2_checklist_items(self, client, sample_results):
        resp = client.post("/api/export", json={
            "format": "csv", "results": sample_results, "include_checklist": True,
        })
        body = resp.data.decode("utf-8")
        # Find the checklist block (the design block above it uses its own markers)
        checklist_start = body.find("# VALIDATION CHECKLIST")
        assert checklist_start != -1
        checklist_block = body[checklist_start:]
        # Count data rows (not header/comment lines)
        rows = [
            line for line in checklist_block.splitlines()
            if line and not line.startswith("#") and not line.startswith("Item,")
        ]
        # MIQE 2.0 checklist: original 8 + LOD/LLOQ, efficiency-corrected,
        # reference-gene, reproducibility, raw-fluorescence = 13
        assert len(rows) == 13, f"Expected 13 checklist rows, got {len(rows)}: {rows}"
        # New MIQE 2.0 items are present
        for token in ("LOD", "geometric-mean", "RDML", "Reproducibility", "prediction intervals"):
            assert token in checklist_block, f"missing MIQE 2.0 item: {token}"

    def test_csv_has_miqe_design_block(self, client, sample_results):
        # MIQE 2.0 §1: the tool self-reports itself + settings
        sample_results["metadata"] = {
            **sample_results["metadata"],
            "species": "Homo sapiens",
            "mirna_accession": "MIMAT0000076",
            "design_settings": {
                "detection_method": "taqman", "rt_overhang_nt": 6,
                "tm_target_c": [58, 62], "gc_percent": [40, 60],
                "primer_length_nt": [20, 27], "amplicon_bp": [60, 120],
                "na_mm": 50, "k_mm": 50, "mg_mm": 1.5, "dntp_mm": 0.8,
                "primer_nm": 200, "buffer_ph": 8.4,
            },
        }
        resp = client.post("/api/export", json={
            "format": "csv", "results": sample_results, "include_checklist": True,
        })
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "ASSAY DESIGN (MIQE 2.0" in body
        assert "Design tool + version + settings" in body
        assert "MIMAT0000076" in body          # accession surfaced
        assert "Homo sapiens" in body           # species surfaced

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


@pytest.fixture
def results_with_overhang(sample_results):
    r = dict(sample_results)
    r["specificity_warnings"] = {
        **sample_results["specificity_warnings"],
        "overhang_collision": {
            "axis_model": "delta_cq",
            "worst_assay_label": "CO-AMPLIFIED",
            "summary": {"CO-AMPLIFIED": 1, "PARTIAL": 1, "rt_identical": 0, "shifted_5p": 0,
                        "shifted_3p": 1, "same_sequence": 0, "n_reported": 2, "truncated": False},
            "collisions": [
                {"mirna": "hsa-let-7d-5p", "assay_label": "CO-AMPLIFIED", "delta_cq": 0.09,
                 "cross_reactivity_pct": 93.95},
                {"mirna": "hsa-let-7f-5p", "assay_label": "PARTIAL", "delta_cq": 3.65,
                 "cross_reactivity_pct": 7.97},
            ],
            "interpretation": "ΔCq_assay ≈ ΔCq_RT + ΔCq_FWD.",
        },
    }
    return r


class TestDualAxisExport:
    _COLS = [
        "assay_worst_label", "n_co_amplified", "n_partial",
        "top_off_target", "n_same_molecule_entries",
    ]

    def test_csv_has_dual_axis_columns(self, client, results_with_overhang):
        resp = client.post("/api/export", json={
            "format": "csv", "results": results_with_overhang, "include_checklist": True,
        })
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        for col in self._COLS:
            assert col in body, f"CSV missing dual-axis column '{col}'"
        assert "hsa-let-7d-5p" in body   # top_off_target value
        assert "CO-AMPLIFIED" in body

    def test_csv_dual_axis_absent_when_no_overhang(self, client, sample_results):
        resp = client.post("/api/export", json={
            "format": "csv", "results": sample_results, "include_checklist": True,
        })
        body = resp.data.decode("utf-8")
        assert "assay_worst_label" not in body   # no overhang_collision → no rows

    def test_pdf_ok_with_overhang(self, client, results_with_overhang):
        try:
            import reportlab  # noqa: F401
        except ImportError:
            pytest.skip("reportlab not installed")
        resp = client.post("/api/export", json={
            "format": "pdf", "results": results_with_overhang, "include_checklist": True,
        })
        assert resp.status_code == 200
        assert resp.data[:4] == b"%PDF"


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
