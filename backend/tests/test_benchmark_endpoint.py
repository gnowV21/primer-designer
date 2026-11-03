"""Tests for GET /api/benchmark (Phase 7 PART F)."""

import json
import os
import sys
import pytest
from unittest.mock import patch, mock_open

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


SAMPLE_RESULTS = {
    "_metadata": {
        "run_date": "2026-07-04",
        "panel_size": 10,
        "tool_version": "algo-v3.0.0",
        "comparison_note": "Design-characteristic comparison only.",
        "verified": False,
    },
    "metrics": {
        "forward_tm": {"this_tool": 60.5, "mirprimer": 58.2, "miprimer": None},
    },
    "per_assay": [],
}


class TestBenchmarkEndpoint:
    def test_file_present_returns_metrics(self, client):
        with patch("routes.benchmark.os.path.isfile", return_value=True):
            with patch(
                "builtins.open",
                mock_open(read_data=json.dumps(SAMPLE_RESULTS)),
            ):
                resp = client.get("/api/benchmark")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["_metadata"]["panel_size"] == 10
        assert data["metrics"] is not None

    def test_file_missing_returns_available_false(self, client):
        with patch("routes.benchmark.os.path.isfile", return_value=False):
            resp = client.get("/api/benchmark")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["available"] is False
        assert "message" in data

    def test_metadata_has_comparison_note(self, client):
        with patch("routes.benchmark.os.path.isfile", return_value=True):
            with patch(
                "builtins.open",
                mock_open(read_data=json.dumps(SAMPLE_RESULTS)),
            ):
                resp = client.get("/api/benchmark")
        data = resp.get_json()
        assert "comparison_note" in data["_metadata"]
        assert len(data["_metadata"]["comparison_note"]) > 20

    def test_miprimer_null_handled(self, client):
        with patch("routes.benchmark.os.path.isfile", return_value=True):
            with patch(
                "builtins.open",
                mock_open(read_data=json.dumps(SAMPLE_RESULTS)),
            ):
                resp = client.get("/api/benchmark")
        data = resp.get_json()
        # miPrimer forward_tm should be null (not crash)
        assert data["metrics"]["forward_tm"]["miprimer"] is None


class TestValidationBlock:
    """
    The committed benchmark_results.json must carry the `validation` block
    (real output of validation/validate_primers.py) — it is the scientific
    substitute for the null competitor columns. Guards against accidental loss.
    """

    def _load_real(self):
        path = os.path.normpath(os.path.join(
            _BACKEND_DIR, "..", "benchmark", "benchmark_results.json"))
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_validation_block_present_and_passing(self):
        data = self._load_real()
        v = data.get("validation")
        assert v is not None, "validation block missing from benchmark_results.json"
        assert v["checks_passed"] == v["checks_total"], "not all validation checks passed"
        assert v["checks_total"] > 0

    def test_deterministic_overhangs_match(self):
        data = self._load_real()
        for t in data["validation"]["deterministic_primer_targets"]:
            assert t["rt_overhang_expected"] == t["rt_overhang_actual"], (
                f"{t['id']}: overhang mismatch "
                f"{t['rt_overhang_expected']} != {t['rt_overhang_actual']}"
            )

    def test_published_exact_match_mir16_rt_byte_identical(self):
        data = self._load_real()
        pub = data["validation"].get("published_exact_match", [])
        assert pub, "published_exact_match block missing"
        mir16 = next((p for p in pub if p["id"] == "hsa-miR-16-5p"), None)
        assert mir16 is not None, "miR-16 published exact-match row missing"
        assert mir16["rt_exact_match"] == "PASS", "miR-16 RT primer no longer byte-identical to published"
        assert mir16["rt_overhang_match"] == "PASS"
        assert mir16["forward_shares_specific"] == "PASS"

    def test_validation_block_matches_generator(self):
        """CI gate (Week2 C9): the committed validation block must equal what
        build_benchmark_validation.py regenerates from results.json — no manual drift."""
        import importlib.util
        repo = os.path.normpath(os.path.join(_BACKEND_DIR, ".."))
        gen_path = os.path.join(repo, "validation", "build_benchmark_validation.py")
        results_path = os.path.join(repo, "validation", "results.json")
        if not (os.path.isfile(gen_path) and os.path.isfile(results_path)):
            pytest.skip("generator or results.json not present")
        spec = importlib.util.spec_from_file_location("bbv", gen_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with open(results_path, encoding="utf-8") as f:
            results = json.load(f)
        expected = mod.build_validation_block(results)
        assert self._load_real().get("validation") == expected, (
            "benchmark validation block is stale — run "
            "`python validation/build_benchmark_validation.py --in-place`"
        )

    def test_endpoint_passes_validation_through(self, client):
        # The endpoint is a passthrough; served payload must include validation.
        resp = client.get("/api/benchmark")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "validation" in data
        assert data["validation"]["checks_passed"] == data["validation"]["checks_total"]
