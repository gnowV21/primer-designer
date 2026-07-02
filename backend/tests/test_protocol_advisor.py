# tests/test_protocol_advisor.py — SPEC_phase5 §A.7
# All 6 required tests for the protocol advisor.
# Run: pytest tests/test_protocol_advisor.py -v

import pytest
from algorithm.protocol_advisor import advise_protocol


def _result(family_risk=False, edge_codes=None):
    """Helper to build a minimal design_result."""
    cr = []
    if family_risk:
        cr = [{"sibling": "hsa-let-7c-5p", "risk": "HIGH", "mismatch": 1, "delta_tm": 2.0}]
    ecs = [{"code": c, "severity": "critical", "message": "test"} for c in (edge_codes or [])]
    return {
        "edge_cases": ecs,
        "specificity_warnings": {
            "cross_reactivity": {"cross_reactivity": cr}
        },
    }


def test_sybr_high_family_triggers_P1():
    advice = advise_protocol(_result(family_risk=True), {"signalMethod": "sybr"})
    ids = [a["id"] for a in advice]
    assert "P1" in ids, "P1 must fire for SYBR + HIGH family risk"
    p1 = next(a for a in advice if a["id"] == "P1")
    assert p1["match"] in ("high", "medium")


def test_ffpe_low_input_triggers_P2():
    advice = advise_protocol(_result(), {"sampleType": "ffpe", "inputAmount": "5"})
    ids = [a["id"] for a in advice]
    assert "P2" in ids, "P2 must fire for FFPE sample type"
    p2 = next(a for a in advice if a["id"] == "P2")
    assert p2["match"] in ("high", "medium")


def test_sybr_always_triggers_P3_melting():
    advice = advise_protocol(_result(), {"signalMethod": "sybr"})
    ids = [a["id"] for a in advice]
    assert "P3" in ids, "P3 must fire for any SYBR assay (melting-curve mandatory)"


def test_multiplex_triggers_P4():
    advice = advise_protocol(_result(), {"multiplex": True})
    ids = [a["id"] for a in advice]
    assert "P4" in ids, "P4 must fire when multiplex=True"


def test_no_conditions_returns_empty_or_generic():
    """With no matching conditions, advice list should be empty (no false positives)."""
    advice = advise_protocol(_result(), {"signalMethod": "taqman"})
    ids = [a["id"] for a in advice]
    # None of P1-P6 should fire with no triggers
    assert "P1" not in ids
    assert "P3" not in ids
    assert "P4" not in ids


def test_every_advice_has_source_doi():
    """Every advice item returned by any combination must carry at least one source with doi."""
    params_combos = [
        {"signalMethod": "sybr"},
        {"sampleType": "plasma", "inputAmount": "2"},
        {"multiplex": True},
        {"applicationContext": "clinical"},
    ]
    results_combos = [
        _result(family_risk=True),
        _result(edge_codes=["E1"]),
        _result(edge_codes=["E4"]),
        _result(),
    ]
    for dr, fp in zip(results_combos, params_combos):
        for item in advise_protocol(dr, fp):
            sources = item.get("sources", [])
            assert sources, f"Rule {item['id']} returned no sources"
            has_doi = any(s.get("doi") for s in sources)
            assert has_doi, f"Rule {item['id']} has no source with doi"
