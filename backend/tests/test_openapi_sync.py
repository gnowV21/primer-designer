# ================================================================
# tests/test_openapi_sync.py — B3 route-sync guard (PLAN Gap B §2)
#
# The most valuable B3 deliverable: turn silent API/spec drift into a CI failure.
# Every registered /api/* route must appear in static/openapi.yaml, and every
# documented path must be a real route. Adding a route without documenting it (or
# vice-versa) fails here.
# ================================================================

import os
import re
import sys

import pytest

_BACKEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

yaml = pytest.importorskip("yaml", reason="PyYAML needed to parse the OpenAPI contract")

_OPENAPI_PATH = os.path.join(_BACKEND_DIR, "static", "openapi.yaml")

# Flask rule → OpenAPI path: "<int:id>" / "<mirna_id>" → "{id}" / "{mirna_id}".
_CONVERTER = re.compile(r"<(?:[^:>]+:)?([^>]+)>")


def _flask_to_openapi(rule: str) -> str:
    return _CONVERTER.sub(r"{\1}", rule)


@pytest.fixture(scope="module")
def app():
    from app import app as flask_app
    return flask_app


@pytest.fixture(scope="module")
def spec():
    with open(_OPENAPI_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _registered_api_paths(flask_app) -> set:
    return {
        _flask_to_openapi(r.rule)
        for r in flask_app.url_map.iter_rules()
        if r.rule.startswith("/api")
    }


# ── The core drift guard ─────────────────────────────────────────

def test_openapi_matches_registered_routes(app, spec):
    """Registered /api routes and documented paths must be exactly equal."""
    registered = _registered_api_paths(app)
    documented = set(spec.get("paths", {}))

    undocumented = registered - documented
    phantom = documented - registered
    assert not undocumented and not phantom, (
        f"\nOpenAPI drift detected:"
        f"\n  routes missing from openapi.yaml: {sorted(undocumented)}"
        f"\n  paths in openapi.yaml with no route: {sorted(phantom)}"
        f"\n  → document new routes in static/openapi.yaml in the same commit."
    )


# ── Contract sanity ──────────────────────────────────────────────

def test_openapi_is_valid_3_1(spec):
    assert spec.get("openapi", "").startswith("3.1")
    assert "info" in spec and "version" in spec["info"]
    assert isinstance(spec.get("paths"), dict) and spec["paths"]


def test_every_path_has_a_method(spec):
    verbs = {"get", "post", "put", "patch", "delete"}
    for path, item in spec["paths"].items():
        assert verbs & set(item), f"{path} documents no HTTP method"


# ── Live docs routes ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def client(app):
    app.config["TESTING"] = True
    return app.test_client()


def test_docs_page_served(client):
    resp = client.get("/api/docs")
    assert resp.status_code == 200
    assert "text/html" in resp.content_type
    assert b"swagger-ui" in resp.data.lower()


def test_openapi_yaml_served_and_parses(client):
    resp = client.get("/api/openapi.yaml")
    assert resp.status_code == 200
    parsed = yaml.safe_load(resp.data)
    assert parsed["openapi"].startswith("3.1")
