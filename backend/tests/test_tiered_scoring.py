"""
test_tiered_scoring.py — the tiered ranking inside /api/design (algorithm 4.0.0,
docs/SPEC_scoring_tiered_4.0.0.md §3.5, §4, Giai đoạn 2; QD 24–27).

Level boundaries of every 1–5 table and the pure ranking rules (specificity beats PCR,
soft veto, elimination, tie-breaks) are in test_tiered_scoring_levels.py. Here: the
pipeline, the API fields, BLAST degradation, determinism, v4_rule_violations and the
V4 regression. BLAST is replaced by a stub except in the tests marked live.
"""
import json

import pytest

from algorithm import design_pipeline, tiered_pipeline
from algorithm import tiered_scoring as ts
from algorithm.constants import CANDIDATES_TOP_N
from algorithm.specificity_check import blast_offtarget as bo

MIR16, MIR16_ID = "UAGCAGCACGUAAAUAUUGGCG", "hsa-miR-16-5p"
MIR21, MIR21_ID = "UAGCUUAUCAGACUGAUGUUGA", "hsa-miR-21-5p"


# Informational keys in a tiered set's scores: shown, never weighted or ranked
# (bound_fraction_binding_pct = cycle-1 occupancy at Ta, SPEC_ui_tiered_4.0.0 UI-2).
_INFO_SCORES = {"bound_fraction_binding_pct"}

def _blast_result(risk: str, n_medium: int = 0) -> dict:
    hits = [{"subject_id": f"hsa-miR-x{i}", "risk": "MEDIUM"} for i in range(n_medium)]
    if risk in ("HIGH", "CRITICAL"):
        hits.insert(0, {"subject_id": "hsa-miR-worst", "risk": risk})
    return {"summary": {"overall_risk": risk}, "forward_primer_hits": hits,
            "identical_sequence_risk": {}}


def _stub_blast(monkeypatch, risk_of):
    """Replace the BLAST step: risk_of(sequence) → overall_risk."""
    calls = []

    def fake(seqs, *a, **k):
        calls.append(list(seqs))
        return {"results": {s: _blast_result(risk_of(s)) for s in seqs}, "available": True,
                "reason": None, "cache_hits": 0, "ms": 0}
    monkeypatch.setattr(tiered_pipeline, "blast_candidates", fake)
    return calls


def _run(seq=MIR16, name=MIR16_ID, **params):
    return design_pipeline.run(seq, {"scoringSystem": "tiered", **params}, name)


# ── system selection ─────────────────────────────────────────────

def test_default_system_is_tiered(monkeypatch):
    monkeypatch.delenv("SCORING_SYSTEM", raising=False)
    assert tiered_pipeline.resolve_system({}) == "tiered"
    monkeypatch.setenv("SCORING_SYSTEM", "v4")
    assert tiered_pipeline.resolve_system({}) == "v4"
    assert tiered_pipeline.resolve_system({"scoringSystem": "TIERED"}) == "tiered"
    with pytest.raises(ValueError):
        tiered_pipeline.resolve_system({"scoringSystem": "v5"})


def test_route_rejects_unknown_system_and_accepts_v4():
    from app import app
    c = app.test_client()
    r = c.post("/api/design", json={"sequence": {"matureSequence": MIR16}, "scoringSystem": "x"})
    assert r.status_code == 400 and "scoringSystem" in r.get_json()["error"]
    r = c.post("/api/design", json={"sequence": {"matureSequence": MIR16, "mirnaId": MIR16_ID},
                                    "scoringSystem": "v4"})
    d = r.get_json()
    assert r.status_code == 200
    assert d["metadata"]["scoring_system"] == "v4" and d["ranking_summary"] is None
    assert all("ranking" not in s for s in d["top3"])


# ── API fields (SPEC §4) ─────────────────────────────────────────

def test_tiered_sets_carry_ranking_and_v4_compatible_fields(monkeypatch):
    _stub_blast(monkeypatch, lambda s: "SAFE")
    d = _run()
    assert d["metadata"]["scoring_system"] == "tiered"
    assert d["metadata"]["provenance"]["scoring_system"] == "tiered"
    assert len(d["metadata"]["provenance"]["tiered_thresholds_sha256"]) == 12
    rs = d["ranking_summary"]
    assert rs["system"] == "tiered" and rs["blast_available"] is True
    assert rs["returned_sets"] == len(d["top3"]) == CANDIDATES_TOP_N
    assert {"blast", "total"} <= set(rs["timing_ms"])
    for s in d["top3"]:
        rk = s["ranking"]
        assert s["total_score"] == rk["detailed_score"]
        # frontend breakdown; cycle-1 occupancy is informational (not weighted), as in V4
        assert set(s["weights"]) == set(s["scores"]) - _INFO_SCORES
        assert abs(sum(s["weights"].values()) - 1.0) < 0.01
        assert rk["specificity"]["max"] == 15 and rk["pcr"]["max"] == 5 and rk["flexible"]["max"] == 20
        assert s["grade"] in ("A", "B") and s["grade_basis"] == "tiers (QD 30)"   # QD 35 defaults
        assert rk["pcr"]["tm_pair"]["report_only"] is True
        assert rk["pcr"]["total"] == rk["pcr"]["tm_vs_ta"]["score"]
        assert rk["specificity"]["blast"]["overall_risk"] == "SAFE"
        assert isinstance(s["v4_rule_violations"], list)


def test_rank_order_follows_the_tiered_key(monkeypatch):
    _stub_blast(monkeypatch, lambda s: "SAFE")
    top = _run()["top3"]
    key = [(-s["ranking"]["specificity"]["total"], s["ranking"]["structure_veto"],
            -s["ranking"]["pcr"]["total"], -s["ranking"]["flexible"]["total"],
            -s["ranking"]["detailed_score"]) for s in top]
    assert key[0] == min(key)
    assert top[0]["selection"] == "best"


# ── elimination / fallback / fewer than 3 (QD 4, QD 5) ──────────

def test_blast_critical_candidates_are_eliminated_and_not_used_to_fill(monkeypatch):
    keep = set()

    def risk(s):
        # keep the first two sequences seen, CRITICAL for everything else
        if len(keep) < 2:
            keep.add(s)
        return "SAFE" if s in keep else "CRITICAL"
    _stub_blast(monkeypatch, risk)
    d = _run()
    rs = d["ranking_summary"]
    assert {s["sequence"] for s in d["top3"]} == keep
    assert rs["returned_sets"] == 2 and not rs["specificity_fallback"]
    assert rs["eliminated_specificity"] == rs["candidates_scored"] - 2
    assert "fewer_than_3_sets" in {w["field"] for w in d["global_warnings"]}


def test_all_eliminated_gives_fallback_with_all_candidates_blasted(monkeypatch):
    calls = _stub_blast(monkeypatch, lambda s: "CRITICAL")
    d = _run()
    rs = d["ranking_summary"]
    assert rs["specificity_fallback"] and rs["returned_sets"] == CANDIDATES_TOP_N
    assert rs["blast_candidates"] == rs["candidates_scored"]
    assert sum(len(c) for c in calls) == rs["candidates_scored"]
    assert all(s["ranking"]["eliminated"] for s in d["top3"])
    assert "specificity_fallback" in {w["field"] for w in d["global_warnings"]}


def test_only_s2_survivors_are_blasted(monkeypatch):
    """hsa-miR-100-5p: S2 eliminates the specific lengths at which hsa-miR-99a-5p is
    CO-AMPLIFIED (test_family_per_candidate.py) → those candidates are not BLASTed."""
    calls = _stub_blast(monkeypatch, lambda s: "SAFE")
    d = _run("AACCCGUAGAUCCGAACUUGUG", "hsa-miR-100-5p")
    rs = d["ranking_summary"]
    assert len(calls) == 1
    assert 0 < rs["eliminated_specificity"] < rs["candidates_scored"]
    assert len(calls[0]) == rs["blast_candidates"] == rs["candidates_scored"] - rs["eliminated_specificity"]
    assert all(s["ranking"]["specificity"]["assay_dcq"]["score"] > 1 for s in d["top3"])


# ── no BLAST (QD 24e) ────────────────────────────────────────────

def test_without_blast_the_request_succeeds_on_s2_plus_s3(monkeypatch):
    monkeypatch.setattr(bo, "blast_available", lambda: (False, "test: no blastn"))
    d = _run()
    rs = d["ranking_summary"]
    assert rs["blast_available"] is False and rs["blast_candidates"] == 0
    w = next(w for w in d["global_warnings"] if w["field"] == "blast_unavailable")
    assert "specificity ranking reduced to S2 + S3" in w["message"]
    for s in d["top3"]:
        sp = s["ranking"]["specificity"]
        assert sp["blast"]["score"] is None and sp["max"] == 10


def test_blast_failure_mid_run_degrades_the_same_way(monkeypatch):
    import subprocess

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("blastn", 1)
    monkeypatch.setattr(bo, "blast_available", lambda: (True, None))
    monkeypatch.setattr(bo, "check_offtarget_batch", boom)
    monkeypatch.setenv("BLAST_CACHE_DISABLED", "1")
    d = _run()
    assert d["ranking_summary"]["blast_available"] is False
    assert "TimeoutExpired" in d["ranking_summary"]["blast_unavailable_reason"]


def test_fallback_reblast_failure_drops_s1_for_every_candidate(monkeypatch):
    """miR-100-5p: S2 eliminates some candidates; if every S2 survivor is BLAST CRITICAL
    the fallback BLASTs the rest — when that second run fails, no candidate keeps S1
    (S totals stay comparable)."""
    n = {"calls": 0}

    def fake(seqs, *a, **k):
        n["calls"] += 1
        if n["calls"] == 1:
            return {"results": {s: _blast_result("CRITICAL") for s in seqs}, "available": True,
                    "reason": None, "cache_hits": 0, "ms": 1}
        return {"results": {}, "available": False, "reason": "BLAST run failed: OSError",
                "cache_hits": 0, "ms": 1}
    monkeypatch.setattr(tiered_pipeline, "blast_candidates", fake)
    d = _run("AACCCGUAGAUCCGAACUUGUG", "hsa-miR-100-5p")
    rs = d["ranking_summary"]
    assert n["calls"] == 2
    assert rs["blast_available"] is False and rs["blast_candidates"] == 0
    assert all(s["ranking"]["specificity"]["blast"]["score"] is None for s in d["top3"])
    assert "blast_unavailable" in {w["field"] for w in d["global_warnings"]}


# ── determinism ──────────────────────────────────────────────────

def test_same_input_same_output(monkeypatch):
    _stub_blast(monkeypatch, lambda s: "MEDIUM" if s.endswith("A") else "SAFE")
    a, b = _run(), _run()
    strip = lambda d: json.dumps(d["top3"], sort_keys=True, default=str)   # noqa: E731
    assert strip(a) == strip(b)
    assert a["ranking_summary"]["eliminated_specificity"] == b["ranking_summary"]["eliminated_specificity"]


# ── v4_rule_violations (QD 25) ───────────────────────────────────

def test_v4_rule_violations_lists_gc_and_hard_filter_rules():
    from algorithm.forward_primer import _build_candidate
    from algorithm.structure_check import run_all_structure_checks
    from algorithm.constants import UNIVERSAL_REVERSE
    dna = "TAGCAGCACGTAAATATTGGCG"
    c = _build_candidate("GCGCGCGCTAGCAGCACGTA", dna[:12], "GCGCGCGC", 12, len(dna), {})
    c["structure_checks"] = run_all_structure_checks(c["sequence"], UNIVERSAL_REVERSE, {})
    v = tiered_pipeline.v4_rule_violations(c, {})
    assert "gc_out_of_range" in v                      # 65 % GC > 60 %
    assert all(" " not in r for r in v)                # codes only, no detail text


def test_v4_sets_of_a_normal_design_break_no_v4_rule():
    d = design_pipeline.run(MIR16, {"scoringSystem": "v4"}, MIR16_ID)
    assert all(s["v4_rule_violations"] == [] for s in d["top3"])


# ── V4 regression (QD 11: V4 unchanged behind the flag) ─────────

@pytest.mark.parametrize("name, seq, top3", [
    ("hsa-miR-16-5p", MIR16,
     ["CAACTCCGAATAGCAGCACGTA", "CGAGTTCGATTAGCAGCACGTA", "AGTACTCCGTAGCAGCACGTA"]),
    ("hsa-miR-100-5p", "AACCCGUAGAUCCGAACUUGUG",
     ["ACAGGAACCCGTAGATCCGAA", "CATGGATCACAACCCGTAGATCC", "CAGGTAGAACCCGTAGATCCGA"]),
    ("hsa-let-7a-5p", "UGAGGUAGUAGGUUGUAUAGUU",
     ["CCGGATAGTGAGGTAGTAGGTTGT", "CGACGGATTTGAGGTAGTAGGTTG", "ATGCCATCGTGAGGTAGTAGGT"]),
])
def test_v4_top3_unchanged_from_3_8_2(name, seq, top3):
    """API top 3 of algorithm 3.8.2 (outputs/freeze_cache/pools_hsa_3.8.2.jsonl.gz)."""
    d = design_pipeline.run(seq, {"scoringSystem": "v4"}, name)
    assert [s["sequence"] for s in d["top3"]] == top3


# ── overhang suggestion (SPEC §3.6) ──────────────────────────────

def test_overhang_suggestion_only_when_another_length_scores_higher(monkeypatch):
    real = tiered_pipeline.assay_screen

    def screen(seq, name, params, ov, lens, **k):
        out = real(seq, name, params, ov, lens, **k)
        if ov == 7:
            out = {L: {**v, "min_delta_cq": None, "worst": None} for L, v in out.items()}
        return out
    best = {"specific_length": 14,
            "ranking": {"specificity": {"assay_dcq": {"min_delta_cq": 8.0}}}}
    monkeypatch.setattr(tiered_pipeline, "assay_screen", screen)
    sug = tiered_pipeline.overhang_suggestion(MIR16, {}, MIR16_ID, 6, best, "hsa")
    assert sug["length"] == 7 and sug["s2_level"] == 5 and sug["s2_level_current"] == 4
    assert "Off-label" in sug["note"]
    # a region longer than the miRNA allows with that overhang is never suggested
    best["specific_length"] = 16                        # 22 − 7 = 15 < 16
    assert tiered_pipeline.overhang_suggestion(MIR16, {}, MIR16_ID, 6, best, "hsa") is None


# ── export (SPEC §4, QD 25) ──────────────────────────────────────

def test_export_carries_scoring_system_thresholds_and_v4_rules(monkeypatch):
    from app import app
    _stub_blast(monkeypatch, lambda s: "SAFE")
    d = _run()
    d["top3"][0]["v4_rule_violations"] = ["gc_out_of_range"]
    r = app.test_client().post("/api/export", json={"format": "csv", "results": d})
    text = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "scoring system tiered" in text and "tiered thresholds #" in text
    assert "Required S " in text and "Standard primer rules not met: gc_out_of_range" in text


# ── live BLAST ───────────────────────────────────────────────────

live = pytest.mark.skipif(not bo.blast_available()[0], reason="BLAST+ or the miRBase DB missing")


def _flags(monkeypatch, on: bool):
    from algorithm import constants as K
    for f in ("TIERED_F4_FLOOR", "TIERED_GRADE_BY_TIERS", "TIERED_V4_COMPLIANT_FIRST",
              "TIERED_BINDING_FLOOR_VETO"):
        monkeypatch.setattr(K, f, on)


@live
def test_live_design_matches_the_giai_doan_1_dry_run(monkeypatch):
    """hsa-miR-21-5p with real BLAST, QD 29/30/34 off (the configuration of Giai đoạn
    1–2): the top 3 of the dry run (benchmark/tiered_scoring_dryrun.json, cases)."""
    _flags(monkeypatch, False)
    d = _run(MIR21, MIR21_ID)
    assert [s["sequence"] for s in d["top3"]] == [
        "ACCGCCTAGCTTATCAGACTGA", "CTAGCCGTCCTATAGCTTATCAGACT", "ACCGAGTGAGTGTAGCTTATCAGA"]
    assert [s["ranking"]["specificity"]["total"] for s in d["top3"]] == [14, 14, 14]
    assert [s["total_score"] for s in d["top3"]] == [92.1, 88.2, 82.7]
    assert d["ranking_summary"]["blast_candidates"] == d["ranking_summary"]["candidates_scored"]


def test_blast_s1_inputs_counts_medium_hits_and_variants():
    r = _blast_result("MEDIUM", n_medium=2)
    r["identical_sequence_risk"] = {"hsa-miR-v": {"risk": "MEDIUM"}}
    assert ts.blast_s1_inputs(r) == ("MEDIUM", 3, "hsa-miR-x0")
    r = {"summary": {"overall_risk": "HIGH"}, "forward_primer_hits": [],
         "identical_sequence_risk": {"hsa-miR-5p-shift": {"risk": "HIGH"}}}
    assert ts.blast_s1_inputs(r) == ("HIGH", 0, "hsa-miR-5p-shift")


def test_a_broken_blast_cache_does_not_fail_the_design(monkeypatch):
    """The sqlite cache is optional: a locked file only skips it (BLAST still runs)."""
    import sqlite3
    from algorithm.specificity_check import blast_cache

    def locked(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(blast_cache.BlastCache, "get_results", lambda *a, **k: {})
    monkeypatch.setattr(blast_cache.BlastCache, "set_results", locked)
    monkeypatch.setattr(bo, "blast_available", lambda: (True, None))
    monkeypatch.setattr(bo, "check_offtarget_batch",
                        lambda seqs, *a, **k: {s: _blast_result("SAFE") for s in seqs})
    monkeypatch.delenv("BLAST_CACHE_DISABLED", raising=False)
    d = _run()
    assert d["ranking_summary"]["blast_available"] is True
    assert d["ranking_summary"]["blast_cache_hits"] == 0
    assert "database is locked" in d["ranking_summary"]["blast_cache_write_error"]   # counted


# ── QD 29 / QD 30 behind their flags ─────────────────────────────

def test_flags_qd29_qd30_in_the_api(monkeypatch):
    from algorithm import constants as K
    _stub_blast(monkeypatch, lambda s: "SAFE")
    monkeypatch.setattr(K, "TIERED_F4_FLOOR", True)
    monkeypatch.setattr(K, "TIERED_GRADE_BY_TIERS", True)
    d = _run()
    for s in d["top3"]:
        fx = s["ranking"]["flexible"]
        assert fx["max"] == 20 and fx["specific_length"]["report_only"] is True
        assert fx["binding_tm"]["mode"] == "floor (QD 29)"
        assert "primer_size" not in s["scores"]
        assert set(s["weights"]) == set(s["scores"]) - _INFO_SCORES
        assert set(s["explanations"]) == set(s["scores"]) - _INFO_SCORES
        assert s["grade"] in ("A", "B") and s["grade_basis"] == "tiers (QD 30)"
        assert (s["grade"] == "A") == (s["grade_reasons"] == [])


def test_grade_c_on_fallback_and_b_without_blast(monkeypatch):
    from algorithm import constants as K
    monkeypatch.setattr(K, "TIERED_GRADE_BY_TIERS", True)
    _stub_blast(monkeypatch, lambda s: "CRITICAL")
    assert {s["grade"] for s in _run()["top3"]} == {"C"}
    monkeypatch.setattr(tiered_pipeline, "blast_candidates",
                        lambda *a, **k: {"results": {}, "available": False, "reason": "test",
                                         "cache_hits": 0, "ms": 0})
    top = _run()["top3"]
    assert {s["grade"] for s in top} <= {"B"}
    assert all(any("BLAST unavailable" in r for r in s["grade_reasons"]) for s in top)


def test_flags_off_keep_the_giai_doan_2_output(monkeypatch):
    _flags(monkeypatch, False)
    _stub_blast(monkeypatch, lambda s: "SAFE")
    s = _run()["top3"][0]
    assert s["ranking"]["flexible"]["max"] == 25 and "primer_size" in s["scores"]
    assert s["grade_basis"] == "detailed score" and s["grade_reasons"] is None



def test_v4_compliant_set_preferred_at_equal_specificity(monkeypatch):
    """QD 34 in the pipeline: with BLAST stubbed SAFE, the #1 breaks a V4 rule only if
    every candidate with its S total and veto does."""
    _stub_blast(monkeypatch, lambda s: "SAFE")
    top = _run()["top3"][0]
    if top["v4_rule_violations"]:
        d = _run()
        same = [c for c in d["top3"]
                if c["ranking"]["specificity"]["total"] == top["ranking"]["specificity"]["total"]
                and c["ranking"]["structure_veto"] == top["ranking"]["structure_veto"]]
        assert all(c["v4_rule_violations"] for c in same)



def test_blast_cache_uses_wal_and_a_busy_timeout(tmp_path):
    from algorithm.specificity_check.blast_cache import BlastCache
    c = BlastCache(str(tmp_path / "c.sqlite"))
    with c._conn() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    c.set_results({"ACGT": {"x": 1}}, "REV", "db", "hsa-miR-1-3p", "ctx")
    assert c.get_results(["ACGT", "TTTT"], "REV", "db", "hsa-miR-1-3p", "ctx") == {"ACGT": {"x": 1}}


# ── review fixes (Giai đoạn 3 G) ─────────────────────────────────

def test_explanation_names_the_qd33_anchor(monkeypatch):
    _stub_blast(monkeypatch, lambda s: "SAFE")
    s = _run()["top3"][0]
    assert "linear to 0 at 25 °C" in s["explanations"]["tm_binding_accuracy"]


def test_cache_not_used_without_db_metadata(monkeypatch, tmp_path):
    from algorithm.specificity_check import blast_cache
    called = []
    monkeypatch.setattr(bo, "_METADATA", str(tmp_path / "missing.json"))
    monkeypatch.setattr(bo, "blast_available", lambda: (True, None))
    monkeypatch.setattr(blast_cache.BlastCache, "get_results",
                        lambda *a, **k: called.append(1) or {})
    monkeypatch.setattr(bo, "check_offtarget_batch",
                        lambda seqs, *a, **k: {s: _blast_result("SAFE") for s in seqs})
    monkeypatch.delenv("BLAST_CACHE_DISABLED", raising=False)
    assert tiered_pipeline._blast_db_version() is None
    d = _run()
    assert d["ranking_summary"]["blast_available"] is True and not called
