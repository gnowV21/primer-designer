# ================================================================
# routes/visualize.py — POST /api/visualize  (SPEC_visualization §E)
#
# Renders the 3 reaction/melting/gel SVG panels from /api/design output.
# Never designs or scores. mirna_id is validated (XSS defence, §E.4); all SVG
# text is escaped in svg_builder. Results cached 30 days keyed on the request
# minus `theme` (colours are CSS vars, so one SVG serves both themes — §E.2/§E.5).
# ================================================================

import hashlib
import json
import os
import re

from flask import Blueprint, jsonify, request

from visualization.coordinates import build_amplicon_model, VisualizationError
from visualization.melting import simulate_melting
from visualization.gel import simulate_gel
from visualization.renderer import render_reaction, render_melting, render_gel
from utils.sqlite_kv_cache import SQLiteKVCache

visualize_bp = Blueprint("visualize", __name__)

_MIRNA_ID_RE = re.compile(r"^[A-Za-z0-9\-\._]{1,64}$")   # SPEC §E.4
_ALLOWED_PANELS = ("reaction", "melting", "gel")
_CACHE_TTL_DAYS = 30                                      # SPEC §E.2

# Bump whenever the renderers change their OUTPUT. The cache key is derived from
# the request only, so without this a fixed renderer would keep serving the old
# SVG for up to the full TTL.
#   2 — fixed stage-1/stage-3 base pairing (strands must be passed 5'->3'),
#       melting-curve headroom, gel header/lane overlap.
_RENDER_VERSION = 9

_CACHE = SQLiteKVCache(
    db_path=os.path.join(os.path.dirname(__file__), "..", "data", "visualize_cache.sqlite"),
    table_name="visualize",
    default_ttl_days=_CACHE_TTL_DAYS,
)


def _err(error_code, detail, status=422, **extra):
    body = {"error_code": error_code, "detail": detail}
    body.update({k: v for k, v in extra.items() if v is not None})
    return jsonify(body), status


def _cache_key(data: dict) -> str:
    # Theme is excluded (colours are CSS vars → theme-agnostic SVG). SPEC §E.2.
    key_src = {k: data.get(k) for k in (
        "mirna_sequence", "mirna_id", "stemloop_rt", "forward",
        "forward_binding_length", "universal_reverse",
        "predicted_amplicon_tm", "dimer_tm_warning", "panels", "params",
    )}
    key_src["_render_version"] = _RENDER_VERSION
    canon = json.dumps(key_src, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


@visualize_bp.route("/visualize", methods=["POST"])
def visualize():
    data = request.get_json(force=True) or {}

    # ── 1. Validate mirna_id (user-typed → XSS surface, SPEC §E.4) ────────────
    mirna_id = str(data.get("mirna_id", "")).strip()
    if not _MIRNA_ID_RE.match(mirna_id):
        return _err("INVALID_MIRNA_ID",
                    r"mirna_id must match ^[A-Za-z0-9\-\._]{1,64}$",
                    actual=mirna_id[:80])

    panels = data.get("panels") or list(_ALLOWED_PANELS)
    panels = [p for p in panels if p in _ALLOWED_PANELS]
    if not panels:
        return _err("NO_PANELS", "panels must include at least one of reaction/melting/gel")

    # ── 2. Cache ──────────────────────────────────────────────────────────────
    key = _cache_key(data)
    hit = _CACHE.get(key)
    if hit:
        return jsonify(json.loads(hit["value"]))

    # ── 3. Coordinate model (A1–A6 → 422) ────────────────────────────────────
    try:
        model = build_amplicon_model(
            data.get("mirna_sequence", ""),
            data.get("stemloop_rt", ""),
            data.get("forward", ""),
            data.get("forward_binding_length"),
            data.get("universal_reverse", ""),
        )
    except VisualizationError as e:
        return _err(e.error_code, e.detail, expected=e.expected, actual=e.actual)
    except (TypeError, ValueError) as e:
        return _err("INVALID_REQUEST", f"Malformed visualization request: {e}")

    # ── 4. Render requested panels ────────────────────────────────────────────
    out = {}
    peak_temperature = None
    dh_source = None

    if "reaction" in panels:
        out["reaction"] = render_reaction(model, mirna_id)

    if "gel" in panels:
        out["gel"] = render_gel(simulate_gel(len(model.amplicon)), mirna_id=mirna_id)

    if "melting" in panels:
        atm = data.get("predicted_amplicon_tm")
        if atm is None:
            return _err("MISSING_AMPLICON_TM",
                        "predicted_amplicon_tm is required to render the melting panel")
        melt = simulate_melting(model.amplicon, float(atm), params=data.get("params") or {})
        out["melting"] = render_melting(
            melt, mirna_id=mirna_id, amplicon_bp=len(model.amplicon),
            gc_percent=model.gc_percent, dimer_tm_warning=data.get("dimer_tm_warning"),
        )
        peak_temperature = melt.peak_temperature
        dh_source = melt.dh_source

    resp = {
        "panels": out,
        "meta": {
            "amplicon_length": len(model.amplicon),
            "amplicon_sequence": model.amplicon,
            "gc_percent": model.gc_percent,
            "regions": [{"name": r.name, "start": r.start, "end": r.end} for r in model.regions],
            "peak_temperature": peak_temperature,
            "dh_source": dh_source,
            "size_warning": model.size_warning,
        },
    }
    _CACHE.set(key, json.dumps(resp), ttl_days=_CACHE_TTL_DAYS)
    return jsonify(resp)
