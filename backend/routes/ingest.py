"""
routes/ingest.py — POST /api/ingest, GET /api/papers [SPEC_Phase1 §6].

POST /api/ingest  {"query": "stem-loop RT-qPCR miRNA", "max_results": 20}
    -> searches PubMed, stores metadata+abstract, embeds chunks. Idempotent.

GET  /api/papers?page=1&per_page=20
    -> paginated list of what is currently in the knowledge base.
"""

from flask import Blueprint, jsonify, request

from db import store
from ingest import indexer, pubmed

ingest_bp = Blueprint("ingest", __name__)

DEFAULT_MAX_RESULTS = 20
MAX_QUERY_LEN       = 500


@ingest_bp.route("/ingest", methods=["POST"])
def ingest():
    body  = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()

    if not query:
        return jsonify({"error": "Missing 'query'.",
                        "message": "Provide a PubMed search query, e.g. "
                                   "\"stem-loop RT-qPCR microRNA quantification\"."}), 400
    if len(query) > MAX_QUERY_LEN:
        return jsonify({"error": "Query too long.",
                        "message": f"Keep the query under {MAX_QUERY_LEN} characters."}), 400

    try:
        max_results = int(body.get("max_results", DEFAULT_MAX_RESULTS))
    except (TypeError, ValueError):
        return jsonify({"error": "'max_results' must be an integer."}), 400
    max_results = max(1, min(pubmed.MAX_RESULTS, max_results))

    # ── 1. PubMed ────────────────────────────────────────────────────────────
    try:
        papers = pubmed.search_and_fetch(query, max_results)
    except Exception as exc:
        return jsonify({
            "error":   "PubMed search failed.",
            "message": f"Could not reach PubMed E-utilities: {exc}",
        }), 502

    if not papers:
        return jsonify({
            "query":   query,
            "message": "No papers with an abstract matched this query. "
                       "Try broader keywords.",
            "added": [], "skipped": [], "failed": [],
            "n_added": 0, "n_skipped": 0, "n_failed": 0, "total_chunks": 0,
        })

    # ── 2. Chunk + embed + store ─────────────────────────────────────────────
    # The first call here loads S-PubMedBert (~440 MB download on a cold machine),
    # so this request can legitimately take a while.
    try:
        result = indexer.index_papers(papers)
    except RuntimeError as exc:
        # Raised by llm.embed()/store.get_collection() when a dependency is absent.
        return jsonify({"error": "Indexing unavailable.", "message": str(exc)}), 503

    result["query"]  = query
    result["n_found"] = len(papers)
    return jsonify(result)


@ingest_bp.route("/reindex", methods=["POST"])
def reindex():
    """
    Re-embed every stored chunk into the current embedding model's collection.

    Needed after changing EMBED_MODEL: vectors from a different model are not comparable (and
    usually not even the same width), so the old ones are dead weight. The chunk TEXT is in
    SQLite, so this rebuilds the index from local data — no second trip to PubMed, no
    re-ingest, nothing lost.

    Idempotent: a no-op when the index is already current.
    """
    try:
        return jsonify(store.reindex_if_stale())
    except RuntimeError as exc:
        return jsonify({"error": "Reindex unavailable.", "message": str(exc)}), 503


@ingest_bp.route("/papers", methods=["GET"])
def papers():
    try:
        page     = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "'page' and 'per_page' must be integers."}), 400

    return jsonify(store.list_papers(page=page, per_page=per_page))
