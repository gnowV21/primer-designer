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
from db import local_db

app = Flask(__name__)

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

app.register_blueprint(mirbase_bp,       url_prefix="/api")
app.register_blueprint(design_bp,        url_prefix="/api")
app.register_blueprint(blast_check_bp,   url_prefix="/api")
app.register_blueprint(export_bp,        url_prefix="/api")
app.register_blueprint(multiplex_check_bp, url_prefix="/api")

# Apply rate limit to blast-check and multiplex-check: 10 req/min/IP [spec §9.3]
limiter.limit("10 per minute")(blast_check_bp)
limiter.limit("10 per minute")(multiplex_check_bp)


@app.route("/api/health")
def health():
    return {"status": "ok", "message": "Backend is running", "version": "3.0.0"}


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
