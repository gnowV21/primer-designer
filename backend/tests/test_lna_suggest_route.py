"""
Contract tests for routes/lna_suggest.py — POST /api/lna-suggest.

These guard the FRONTEND↔BACKEND response shape that LnaPanel depends on.
The panel (frontend/src/components/LnaPanel/index.jsx) flattens a *nested*
response: calc_at_suggestion.{tm_dna,tm_lna,delta_tm,method,lna_positions},
lna_result.{suggested_positions,target_met,search,discrimination_gain} and the
top-level tm_reference_primer3. If a backend refactor renames any of those keys
the panel silently renders `undefined` — the build still passes and no other
test fails. This test fails loudly instead.

A minimal Flask app hosts just the blueprint so we avoid importing app.py
(which pulls in transformers/chromadb for the chatbot).
"""

import os
import sys

import pytest
from flask import Flask

# Allow running from repo root or backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routes.lna_suggest import lna_suggest_bp
from algorithm.constants import USE_LNA_SUGGESTIONS


@pytest.fixture()
def client():
    app = Flask(__name__)
    app.register_blueprint(lna_suggest_bp, url_prefix="/api")
    return app.test_client()


_VALID_BODY = {
    "sequence": "ACGTACGTAGCTAGCTAGCT",  # 20 nt DNA (a forward primer is DNA)
    "role": "forward",
    "mode": "tm",
    "target_tm": 60,
    "params": {
        "saltConcentration": 50,
        "magnesiumConcentration": 1.5,
        "dntpTotal": 0.8,
        "primerConcentration": 200,
    },
}


@pytest.mark.skipif(not USE_LNA_SUGGESTIONS, reason="LNA endpoint disabled by feature flag")
def test_response_shape_matches_lnapanel_contract(client):
    """Every key LnaPanel reads must be present with a non-null value."""
    resp = client.post("/api/lna-suggest", json=_VALID_BODY)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()

    # Top-level key the panel maps to result.tm_reference_primer3
    assert "tm_reference_primer3" in data
    assert data["tm_reference_primer3"] is not None

    # calc_at_suggestion.* → result.{tm_dna,tm_lna,delta_tm,method}
    calc = data.get("calc_at_suggestion")
    assert isinstance(calc, dict)
    for key in ("tm_dna", "tm_lna", "delta_tm", "lna_positions", "method"):
        assert key in calc, f"calc_at_suggestion missing {key!r} (LnaPanel reads it)"
    assert calc["tm_dna"] is not None
    assert calc["tm_lna"] is not None
    assert calc["delta_tm"] is not None
    assert isinstance(calc["method"], list)

    # lna_result.* → result.{suggested_positions,target_met,search,discrimination_gain}
    lna = data.get("lna_result")
    assert isinstance(lna, dict)
    for key in ("suggested_positions", "target_met", "search", "discrimination_gain"):
        assert key in lna, f"lna_result missing {key!r} (LnaPanel reads it)"
    assert isinstance(lna["suggested_positions"], list)
    assert isinstance(lna["target_met"], bool)


@pytest.mark.skipif(not USE_LNA_SUGGESTIONS, reason="LNA endpoint disabled by feature flag")
def test_rejects_non_dna_sequence(client):
    """Non-DNA bases (e.g. RNA 'U') must 400 — mirrors the client-side guard."""
    body = {**_VALID_BODY, "sequence": "ACGUACGU"}
    resp = client.post("/api/lna-suggest", json=body)
    assert resp.status_code == 400


@pytest.mark.skipif(not USE_LNA_SUGGESTIONS, reason="LNA endpoint disabled by feature flag")
def test_rejects_rt_role(client):
    """RT overhang is DNA:RNA context — out of scope for the LNA NN model."""
    body = {**_VALID_BODY, "role": "rt"}
    resp = client.post("/api/lna-suggest", json=body)
    assert resp.status_code == 400
