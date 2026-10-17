import os
import sys

# Ensure BLAST+ binaries are on PATH on Windows (installed but not yet in process env)
_BLAST_WIN = r"C:\Program Files\NCBI\blast-2.17.0+\bin"
if sys.platform.startswith("win") and os.path.isdir(_BLAST_WIN) and _BLAST_WIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _BLAST_WIN + os.pathsep + os.environ.get("PATH", "")

from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from routes.mirbase import mirbase_bp
from routes.design import design_bp
from routes.blast_check import blast_check_bp
from routes.export import export_bp
from routes.multiplex_check import multiplex_check_bp
from routes.benchmark import benchmark_bp
from routes.lna_suggest import lna_suggest_bp
from routes.analyze import analyze_bp
from routes.docs import docs_bp
from routes.visualize import visualize_bp
from algorithm.constants import USE_LNA_SUGGESTIONS, ALGORITHM_VERSION
from db import local_db

app = Flask(__name__)
# Reject oversized bodies with 413 before any JSON parsing (audit ENG-04).
# The largest legitimate payload is /api/export (a full design result, ~100s of KB).
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

# Ensure schema + indexes exist on every startup (CREATE IF NOT EXISTS — safe on existing DBs)
local_db.init_schema()

CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]}})

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
app.register_blueprint(multiplex_check_bp, url_prefix="/api")
app.register_blueprint(benchmark_bp,       url_prefix="/api")
app.register_blueprint(lna_suggest_bp,     url_prefix="/api")
app.register_blueprint(analyze_bp,         url_prefix="/api")
app.register_blueprint(docs_bp,            url_prefix="/api")
app.register_blueprint(visualize_bp,       url_prefix="/api")

# Apply rate limit to blast-check and multiplex-check: 10 req/min/IP [spec §9.3]
limiter.limit("10 per minute")(blast_check_bp)
limiter.limit("10 per minute")(multiplex_check_bp)


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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
