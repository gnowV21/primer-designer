# ================================================================
# tests/test_review_panel_fixes.py — review panel 2026-11-18 (docs/REVIEW_panel_4.0.0.md)
#
# Input robustness of the routes (C1–C5) and the MIQE candidate counts (A6).
# None of these change a primer, a score or a rank.
# ================================================================

import sqlite3

import pytest

from algorithm.constants import STEMLOOP_BODY

_MIR21 = "UAGCUUAUCAGACUGAUGUUGA"
_FWD = "CGCAGTAGCTTATCAGACTGA"


@pytest.fixture
def client():
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── C1: /api/design body that is not an object → 400, not 500 ──────

@pytest.mark.parametrize("body", ["null", "[]", '"UAGC"', '{"sequence": "UAGCUUAUCAGACUGAUGUUGA"}',
                                  '{"sequence": {"matureSequence": "UAGCUUAUCAGACUGAUGUUGA"}, "qpcr": []}'])
def test_design_rejects_non_object_bodies(client, body):
    r = client.post("/api/design", data=body, content_type="application/json")
    assert r.status_code == 400
    assert "error" in r.get_json()


# ── C2: the overhang must be a whole number of nucleotides ───────────

@pytest.mark.parametrize("ov", [6.9, 5.5, True, "6.5", "inf"])
def test_design_rejects_non_integer_overhang(client, ov):
    r = client.post("/api/design", json={"sequence": {"matureSequence": _MIR21},
                                         "primerConstraints": {"bindingRegion3prime": ov}})
    assert r.status_code == 400
    assert "bindingRegion3prime" in r.get_json()["error"]


def test_design_rejects_infinity_overhang(client):
    body = '{"sequence": {"matureSequence": "%s"}, "primerConstraints": {"bindingRegion3prime": Infinity}}' % _MIR21
    r = client.post("/api/design", data=body, content_type="application/json")
    assert r.status_code == 400


# ── C3: miRBase 5xx is an outage (retry, then raise), not "not found" ─

class _Resp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body if body is not None else {"results": []}

    def json(self):
        return self._body


def test_fetch_mirbase_5xx_raises_and_404_is_not_found(monkeypatch):
    import routes.mirbase as rm
    monkeypatch.setattr(rm, "_RETRY_DELAYS", [0, 0])
    monkeypatch.setattr(rm.requests, "get", lambda *a, **k: _Resp(503))
    with pytest.raises(RuntimeError, match="503"):
        rm._fetch_mirbase("cel-miR-1")
    monkeypatch.setattr(rm.requests, "get", lambda *a, **k: _Resp(404))
    assert rm._fetch_mirbase("cel-miR-1") is None


# ── C4: a locked BLAST cache does not turn /api/blast-check into a 500 ─

def test_blast_check_survives_cache_errors(client, monkeypatch):
    import routes.blast_check as rb

    def locked(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(rb, "check_offtarget",
                        lambda **kw: {"summary": {"overall_risk": "SAFE"}, "forward_primer_hits": []})
    monkeypatch.setattr(rb._cache, "get_result", locked)
    monkeypatch.setattr(rb._cache, "set_result", locked)
    r = client.post("/api/blast-check", json={"forward_primer": _FWD,
                                              "rt_primer": STEMLOOP_BODY + "TCAACA"})
    assert r.status_code == 200
    assert r.get_json()["summary"]["overall_risk"] == "SAFE"


# C5 (/api/visualize, malformed amplicon Tm) is tested in visualization/test_visualize_route.py.


# ── A6 + A4: candidate counts and the screened species (one real design) ─

def _design(monkeypatch, seq, params, name=""):
    """design_pipeline.run with BLAST stubbed to SAFE (fast, offline)."""
    from algorithm import design_pipeline, tiered_pipeline

    def fake(seqs, *a, **k):
        return {"results": {s: {"summary": {"overall_risk": "SAFE"}, "forward_primer_hits": [],
                                "identical_sequence_risk": {}} for s in seqs},
                "available": True, "reason": None, "cache_hits": 0, "ms": 0}
    monkeypatch.setattr(tiered_pipeline, "blast_candidates", fake)
    return design_pipeline.run(seq, params, name)


_NOVEL = "UGCAUGGACUACGUAGCAUCGA"   # not in miRBase 22.1


@pytest.mark.parametrize("species, assumed", [("other", True), ("human", False), ("mouse", False)])
def test_screen_species_reported(monkeypatch, species, assumed):
    out = _design(monkeypatch, _NOVEL, {"species": species})
    rs = out["ranking_summary"]
    assert rs["screen_species_assumed"] is assumed
    assert rs["screen_species"] == {"other": "hsa", "human": "hsa", "mouse": "mmu"}[species]


def test_named_mirna_is_not_assumed(monkeypatch):
    out = _design(monkeypatch, _MIR21, {"species": "other"}, "hsa-miR-21-5p")
    assert out["ranking_summary"]["screen_species"] == "hsa"
    assert out["ranking_summary"]["screen_species_assumed"] is False


@pytest.mark.parametrize("system", ["tiered", "v4"])
def test_candidate_counts_are_distinct_candidates(monkeypatch, system):
    out = _design(monkeypatch, _MIR21, {"scoringSystem": system}, "hsa-miR-21-5p")
    md = out["metadata"]
    gen, passed, rej = (md["candidates_generated"], md["candidates_passed_prefilter"],
                        md["candidates_rejected"])
    # rejection_summary counts reasons; a candidate with several reasons is one candidate
    assert rej <= sum(md["rejection_summary"].values())
    if system == "tiered":
        # no hard filter: every rejected candidate is a pre-filter reject, counted once
        assert gen - passed == rej
    else:
        # V4 hard-filter rejects come from the passed candidates: not generated twice
        assert gen - passed <= rej <= gen
