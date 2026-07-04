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
