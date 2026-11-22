"""One container serves the API and the built frontend (deploy/vercel, steps 2–3).

- Non-/api paths: a file of frontend/dist, else index.html (BrowserRouter reloads).
- Files come ONLY from the dist directory: internal files (specs, backend source,
  .git) are never returned, whatever the path spelling.
- Unknown /api/* is a JSON 404; an /api route keeps its own 404/405.
- CORS origins from CORS_ORIGINS; debug only with FLASK_DEBUG=1; port from PORT.
"""
import os

import pytest

import app as app_module
from app import app

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(BACKEND)
INDEX = b"<!doctype html><title>spa-index</title><div id=root></div>"


@pytest.fixture(scope="module")
def spa(tmp_path_factory):
    """The real app with a frontend: the built one when frontend/dist exists,
    otherwise a stand-in dist registered the same way."""
    if "frontend" in app.view_functions:
        with open(os.path.join(app_module._DIST, "index.html"), "rb") as f:
            index = f.read()
        return app.test_client(), index, app_module._DIST
    dist = tmp_path_factory.mktemp("dist")
    (dist / "index.html").write_bytes(INDEX)
    (dist / "assets").mkdir()
    (dist / "assets" / "index-abc123.js").write_bytes(b"console.log('spa')")
    (dist / ".env").write_text("SECRET=1")
    app_module._register_frontend(app, os.path.realpath(str(dist)))
    return app.test_client(), INDEX, str(dist)


# ── SPA fallback ─────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/", "/design", "/results", "/design/advanced",
                                  "/history", "/no/such/page"])
def test_spa_routes_get_index(spa, path):
    client, index, _ = spa
    r = client.get(path)
    assert r.status_code == 200 and r.data == index
    assert "no-cache" in r.headers.get("Cache-Control", "")


def test_built_asset_served_with_long_cache(spa):
    client, _, dist = spa
    assets = sorted(os.listdir(os.path.join(dist, "assets")))
    r = client.get(f"/assets/{assets[0]}")
    assert r.status_code == 200 and r.data != spa[1]
    assert "immutable" in r.headers["Cache-Control"]


# ── /api stays the API ───────────────────────────────────────────

@pytest.mark.parametrize("path", ["/api/khong-ton-tai", "/api", "/api/", "/api/design/x"])
def test_unknown_api_is_json_404(spa, path):
    client, index, _ = spa
    r = client.get(path)
    assert r.status_code == 404 and r.is_json and r.get_json()["error"] == "Not found"
    assert index not in r.data


def test_unknown_api_post_is_json_404(spa):
    r = spa[0].post("/api/khong-ton-tai", json={})
    assert r.status_code == 404 and r.is_json


def test_api_routes_unchanged(spa):
    client = spa[0]
    assert client.get("/api/health").get_json()["status"] == "ok"
    assert client.get("/api/design").status_code == 405       # POST-only route keeps 405


# ── internal files are never served ──────────────────────────────

LEAK_PATHS = [
    "/SPEC_algorithm.md", "/backend/app.py", "/HANDOFF_THESIS_STATUS.md", "/.git/config",
    "/../backend/app.py", "/..%2fbackend%2fapp.py", "/%2e%2e/backend/app.py",
    "/..\\backend\\app.py", "/app.py", "/static/openapi.yaml", "/requirements.txt",
    "/backend/db/mirbase.db", "/CLAUDE.md", "/.env", "/assets/../../backend/app.py",
    "/frontend/package.json", "/docs/THESIS_FREEZE_4.0.0.md",
]


def _internal_snippets():
    out = []
    for rel in ("backend/app.py", "SPEC_algorithm.md", "HANDOFF_THESIS_STATUS.md",
                "backend/requirements.txt", "backend/static/openapi.yaml", "CLAUDE.md"):
        p = os.path.join(REPO, rel)
        if os.path.exists(p):
            with open(p, "rb") as f:
                out.append((rel, f.read()[:200]))
    return out


@pytest.mark.parametrize("path", LEAK_PATHS)
def test_internal_files_never_served(spa, path):
    client, index, _ = spa
    r = client.get(path)
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert r.data == index, f"{path} returned something other than index.html"
    for rel, head in _internal_snippets():
        assert head not in r.data, f"{path} leaked {rel}"
    assert b"SECRET=1" not in r.data and b"[core]" not in r.data


def test_dist_must_not_contain_source(monkeypatch):
    for d in (REPO, BACKEND):
        monkeypatch.setenv("FRONTEND_DIST", d)
        assert app_module._frontend_dist() is None


def test_safe_dist_file_rejects_escapes(tmp_path):
    (tmp_path / "a.js").write_text("x")
    (tmp_path / ".hidden").write_text("x")
    d = os.path.realpath(str(tmp_path))
    assert app_module._safe_dist_file(d, "a.js") == "a.js"
    for bad in ("../a.js", ".hidden", "x/../../a.js", "", "/etc/passwd", "a.js/"):
        assert app_module._safe_dist_file(d, bad) is None


# ── configuration from the environment ───────────────────────────

def test_cors_origins_from_env(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert "http://localhost:5173" in app_module._cors_origins()
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    assert app_module._cors_origins() == ["https://a.example", "https://b.example"]


def test_debug_and_port_from_env():
    src = open(os.path.join(BACKEND, "app.py"), encoding="utf-8").read()
    assert "debug=True" not in src
    assert 'os.environ.get("FLASK_DEBUG", "").strip() == "1"' in src
    assert 'os.environ.get("PORT", "5000")' in src


def test_read_only_lookup_db_does_not_break_startup(tmp_path, monkeypatch):
    from db import local_db
    from scripts import build_db
    db = tmp_path / "mirbase.db"
    assert build_db.main(["--out", str(db)]) == 0
    os.chmod(db, 0o444)
    try:
        monkeypatch.setattr(local_db, "DB_PATH", str(db))
        local_db.init_schema()                          # no exception
        assert local_db.lookup("hsa-miR-21-5p")["sequence"] == "UAGCUUAUCAGACUGAUGUUGA"
    finally:
        os.chmod(db, 0o644)


def test_visualize_cache_path_from_env_and_failure_tolerated(monkeypatch, tmp_path):
    import routes.visualize as rv
    monkeypatch.setattr(rv, "_CACHE", None)
    monkeypatch.setenv("VISUALIZE_CACHE_PATH", str(tmp_path / "v.sqlite"))
    rv._cache_set("k", "{}")
    assert rv._cache_get("k")["value"] == "{}" and (tmp_path / "v.sqlite").exists()
    # an unusable cache only skips caching
    monkeypatch.setattr(rv, "_CACHE", None)
    (tmp_path / "a-file").write_text("")               # parent is a file: cannot be created
    monkeypatch.setenv("VISUALIZE_CACHE_PATH", str(tmp_path / "a-file" / "v.sqlite"))
    rv._cache_set("k", "{}")
    assert rv._cache_get("k") is None

