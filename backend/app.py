import logging
import os
import sys

# Ensure BLAST+ binaries are on PATH on Windows (installed but not yet in process env)
_BLAST_WIN = r"C:\Program Files\NCBI\blast-2.17.0+\bin"
if sys.platform.startswith("win") and os.path.isdir(_BLAST_WIN) and _BLAST_WIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _BLAST_WIN + os.pathsep + os.environ.get("PATH", "")

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.routing import PathConverter
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from routes.mirbase import mirbase_bp
from routes.design import design_bp
from routes.blast_check import blast_check_bp
from routes.export import export_bp
from routes.benchmark import benchmark_bp
from routes.lna_suggest import lna_suggest_bp
from routes.analyze import analyze_bp
from routes.docs import docs_bp
from routes.visualize import visualize_bp
from algorithm.constants import USE_LNA_SUGGESTIONS, ALGORITHM_VERSION
from db import local_db

# static_folder=None: Flask's default /static route would serve backend/static.
# The only files served are those of the built frontend (_register_frontend).
app = Flask(__name__, static_folder=None)
log = logging.getLogger(__name__)
# Reject oversized bodies with 413 before any JSON parsing (audit ENG-04).
# The largest legitimate payload is /api/export (a full design result, ~100s of KB).
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

# Ensure schema + indexes exist on every startup (CREATE IF NOT EXISTS — safe on existing DBs;
# a read-only database, as in the deployed image, is only logged)
local_db.init_schema()

# Behind a reverse proxy (Vercel), the client address is in X-Forwarded-For: without
# this every request comes from the proxy and the per-IP rate limit is one shared
# bucket. Only for that many trusted proxy hops (default 0 = off: a client could
# otherwise forge the header when the app is reached directly).
_proxy_hops = int(os.environ.get("PROXY_FIX_X_FOR", "0") or 0)
if _proxy_hops > 0:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=_proxy_hops)

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]


def _cors_origins() -> list:
    """CORS_ORIGINS (comma-separated) or the local dev servers. The deployed app serves
    the frontend from the same origin, so it needs no CORS entry."""
    raw = os.environ.get("CORS_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or list(_DEFAULT_CORS_ORIGINS)


CORS(app, resources={r"/api/*": {"origins": _cors_origins()}})

# Rate limiter — applies @limiter.limit() decorators across all blueprints
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[],          # no global limit; limits set per route
    storage_uri="memory://",    # in-process storage (reset on restart)
)

app.register_blueprint(mirbase_bp,         url_prefix="/api")
app.register_blueprint(design_bp,          url_prefix="/api")
app.register_blueprint(blast_check_bp,     url_prefix="/api")
app.register_blueprint(export_bp,          url_prefix="/api")
app.register_blueprint(benchmark_bp,       url_prefix="/api")
app.register_blueprint(lna_suggest_bp,     url_prefix="/api")
app.register_blueprint(analyze_bp,         url_prefix="/api")
app.register_blueprint(docs_bp,            url_prefix="/api")
app.register_blueprint(visualize_bp,       url_prefix="/api")

# Apply rate limit to blast-check: 10 req/min/IP [spec §9.3]
limiter.limit("10 per minute")(blast_check_bp)


@app.route("/api/health")
def health():
    """Liveness probe. Always returns 200 so the frontend can render a readable status."""
    return {
        "status":  "ok",
        "message": "Backend is running",
        "version": ALGORITHM_VERSION,
        "features": {
            # LNA Tm suggestions are gated until the NN tables are verified. [A2]
            "lna_suggestions": USE_LNA_SUGGESTIONS,
        },
    }


# ── Built frontend (same origin as /api) ─────────────────────────
# frontend/dist (or FRONTEND_DIST) when it exists. Files are served ONLY from that
# directory — never from the repository root or backend/ — and only regular files
# whose path stays inside it with no hidden segment. Every other non-/api path gets
# index.html, so BrowserRouter routes (/design, /results, ...) survive a reload.
# Unknown /api/* paths stay JSON 404.

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _frontend_dist() -> str | None:
    d = os.environ.get("FRONTEND_DIST") or os.path.join(_REPO_ROOT, "frontend", "dist")
    d = os.path.realpath(d)
    # Never a directory that holds the backend or the repository (FRONTEND_DIST=/app
    # would otherwise publish the source tree).
    for inner in (os.path.realpath(_REPO_ROOT), os.path.realpath(os.path.dirname(__file__))):
        try:
            contains = os.path.commonpath([d, inner]) == d
        except ValueError:      # another drive (Windows)
            contains = False
        if contains:
            log.error("FRONTEND_DIST %r contains the source tree; frontend not served", d)
            return None
    return d if os.path.isfile(os.path.join(d, "index.html")) else None


def _is_api(path: str) -> bool:
    return path == "api" or path.startswith("api/")


def _safe_dist_file(dist: str, path: str) -> str | None:
    """Relative path of a regular file inside `dist`, or None."""
    parts = path.replace("\\", "/").split("/")
    if not path or any(p in ("", ".", "..") or p.startswith(".") for p in parts):
        return None
    full = os.path.realpath(os.path.join(dist, *parts))
    try:
        inside = os.path.commonpath([full, dist]) == dist
    except ValueError:          # another drive (Windows)
        inside = False
    if not inside or not os.path.isfile(full):
        return None
    return "/".join(parts)


class _NonApiPath(PathConverter):
    """A path converter that never matches api or api/...: the SPA fallback cannot
    shadow an /api route (GET on a POST-only route stays 405, unknown /api/* stays a
    JSON 404 from the error handler below)."""
    regex = r"(?!api(?:/|$))[^/].*?"


def _register_frontend(flask_app: Flask, dist: str) -> None:
    flask_app.url_map.converters["nonapi"] = _NonApiPath

    @flask_app.route("/", defaults={"path": ""})
    @flask_app.route("/<nonapi:path>")
    def frontend(path):
        rel = _safe_dist_file(dist, path)
        if rel is not None:
            resp = send_from_directory(dist, rel)
            if rel.startswith("assets/"):      # Vite content-hashed file names
                resp.cache_control.public = True
                resp.cache_control.max_age = 31536000
                resp.cache_control.immutable = True
            return resp
        resp = send_from_directory(dist, "index.html")
        resp.cache_control.no_cache = True
        return resp


@app.errorhandler(404)
def _not_found(e):
    if _is_api(request.path.lstrip("/")):
        return jsonify({"error": "Not found", "path": request.path}), 404
    return e


_DIST = _frontend_dist()
if _DIST:
    _register_frontend(app, _DIST)


if __name__ == "__main__":
    # Debug (Werkzeug debugger = remote code execution) only when FLASK_DEBUG=1.
    _debug = os.environ.get("FLASK_DEBUG", "").strip() == "1"
    app.run(debug=_debug, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
