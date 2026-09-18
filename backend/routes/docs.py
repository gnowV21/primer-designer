# ================================================================
# routes/docs.py — API documentation (OpenAPI 3.1 + Swagger UI)
#
# Static approach, ZERO new backend dependency (PLAN Gap B §2):
#   GET /api/openapi.yaml  → serves backend/static/openapi.yaml verbatim
#   GET /api/docs          → HTML page embedding Swagger UI from a CDN
#
# The contract file itself is the single source of truth; tests/test_openapi_sync.py
# asserts it stays in lockstep with the registered Flask routes.
# ================================================================

import os

from flask import Blueprint, Response

docs_bp = Blueprint("docs", __name__)

_OPENAPI_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "static", "openapi.yaml")
)

# Swagger UI is loaded from a CDN so no Python/npm dependency is added. The page
# is self-contained apart from those two CDN assets.
_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HG Lab Primer Designer — API</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
  <style>body { margin: 0; }</style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js" crossorigin></script>
  <script>
    window.ui = SwaggerUIBundle({
      url: "/api/openapi.yaml",
      dom_id: "#swagger-ui",
      deepLinking: true,
      tryItOutEnabled: true
    });
  </script>
</body>
</html>
"""


@docs_bp.route("/openapi.yaml", methods=["GET"])
def openapi_spec():
    """Serve the OpenAPI 3.1 contract as YAML."""
    try:
        with open(_OPENAPI_PATH, encoding="utf-8") as f:
            spec = f.read()
    except FileNotFoundError:
        return Response("openapi.yaml not found", status=500, mimetype="text/plain")
    return Response(spec, mimetype="application/yaml")


@docs_bp.route("/docs", methods=["GET"])
def swagger_ui():
    """Interactive API docs (Swagger UI from CDN)."""
    return Response(_SWAGGER_HTML, mimetype="text/html")
