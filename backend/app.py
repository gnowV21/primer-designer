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
# Phase 1 AI Chatbot [SPEC_Phase1_AI_Chatbot.md §6]
from routes.ingest import ingest_bp
from routes.hrm import hrm_bp
from routes.chat import chat_bp
from db import local_db, store
import llm

app = Flask(__name__)

# Ensure schema + indexes exist on every startup (CREATE IF NOT EXISTS — safe on existing DBs)
local_db.init_schema()
store.init_schema()      # papers + chunks tables for the chatbot knowledge base


def _ensure_index_current() -> None:
    """
    Rebuild the vector index if it is behind SQLite — e.g. after EMBED_MODEL changed.

    A stale index is the worst kind of broken: retrieval keeps working, just against the wrong
    or a partial vector space, so answers quietly cite the wrong papers with no error anywhere.
    Better to pay the re-embed once at startup. The chunk text is local, so this never touches
    PubMed. Failures are non-fatal — the rest of the primer-designer app must still boot.
    """
    try:
        result = store.reindex_if_stale()
        if result["reindexed"]:
            print(f" * Re-embedded {result['reindexed']} chunks into {result['collection']} "
                  f"(embedding model changed)")
    except Exception as exc:
        print(f" * WARNING: vector index is stale and could not be rebuilt: {exc}")
        print(f" *          The assistant will retrieve from a partial index. "
              f"Fix, then POST /api/reindex.")


_ensure_index_current()

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
app.register_blueprint(benchmark_bp,      url_prefix="/api")
app.register_blueprint(lna_suggest_bp,    url_prefix="/api")
app.register_blueprint(ingest_bp,         url_prefix="/api")
app.register_blueprint(hrm_bp,            url_prefix="/api")
app.register_blueprint(chat_bp,           url_prefix="/api")

# Apply rate limit to blast-check and multiplex-check: 10 req/min/IP [spec §9.3]
limiter.limit("10 per minute")(blast_check_bp)
limiter.limit("10 per minute")(multiplex_check_bp)

def _limit_endpoint(endpoint: str, rule: str) -> None:
    """
    Rate-limit a single endpoint rather than a whole blueprint.

    The result MUST be assigned back into app.view_functions. limiter.limit() returns a
    wrapper; without the assignment Flask keeps dispatching to the original function and the
    limit silently never fires — it looks applied and does nothing.
    """
    app.view_functions[endpoint] = limiter.limit(rule)(app.view_functions[endpoint])


# POST /api/ingest hits NCBI E-utilities, which throttles unidentified clients; 5/min/IP keeps
# us well inside their limit. Scoped to the endpoint, not the blueprint: a blueprint-wide limit
# also caught GET /api/papers, so merely opening the Assistant page a few times exhausted the
# quota and the knowledge-base list began returning 429.
_limit_endpoint("ingest.ingest", "5 per minute")

# CPU inference on a 3B model occupies the process for tens of seconds. Without a cap, a
# handful of concurrent questions would starve every other endpoint. Scoped per endpoint for
# the same reason: /api/chat/health is a cheap probe the UI polls and must never be throttled.
_limit_endpoint("chat.chat",        "20 per minute")
_limit_endpoint("chat.chat_stream", "20 per minute")


@app.route("/api/health")
def health():
    """
    Liveness + readiness of every backend dependency [SPEC_Phase1 §6].

    Always returns 200: the frontend uses this to decide what to TELL the user is
    unavailable, so a failing probe must still produce a readable body rather than
    an error the UI has to guess about.
    """
    ollama = llm.ollama_health()
    chroma = store.chroma_health()
    sqlite = store.sqlite_health()

    return {
        "status":  "ok",
        "message": "Backend is running",
        "version": "3.1.0",
        "chat": {
            # The chatbot can answer only when the LLM is up, the model is pulled,
            # and the vector store is readable.
            "ready":    ollama["alive"] and ollama["model_ready"] and chroma["alive"],
            "ollama":   ollama,
            "embedder": llm.embedder_health(),
            "chroma":   chroma,
            "sqlite":   sqlite,
        },
    }


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
