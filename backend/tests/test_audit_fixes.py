"""Regression tests for AUDIT_REPORT.md fixes (2026-09-18).

Each test fails on the pre-audit code.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app import app
from algorithm.constants import STEMLOOP_BODY, SCORING_WEIGHTS_V4, UNSCORED_CRITERIA_V4
from algorithm.sequence_utils import reverse_complement, rna_to_dna
from algorithm.bound_fraction import calculate_bound_fraction_binding

MIR16 = "UAGCAGCACGUAAAUAUUGGCG"
MIR16_DNA = rna_to_dna(MIR16)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


# ── SCI-01: Analyzer reads the overhang length from the RT primer ──────────────

@pytest.mark.parametrize("o", [5, 6, 7])
def test_analyzer_infers_overhang_length(client, o):
    rt = STEMLOOP_BODY + reverse_complement(MIR16_DNA[-o:])
    r = client.post("/api/analyze", json={
        "matureSequence": MIR16,
        "primers": {"rt": rt, "forward": "GGCGTAGCAGCACGTAAA",
                    "reverse": "CCAGTGCAGGGTCCGAGGTA"},
    })
    ov = r.get_json()["context"]["rt_overhang"]
    assert ov["overhang_length"] == o
    assert ov["matches"] is True and ov["match_count"] == o
    assert ov["overhang_length_inferred"] is True


def test_analyzer_recognises_loop_reverse_variant(client):
    """An 18-nt reverse primer inside the stem-loop body is a valid universal reverse."""
    rt = STEMLOOP_BODY + reverse_complement(MIR16_DNA[-6:])
    r = client.post("/api/analyze", json={
        "matureSequence": MIR16,
        "primers": {"rt": rt, "forward": "GGCGTAGCAGCACGTAAA",
                    "reverse": "GCAGGGTCCGAGGTATTC"},
    })
    rev = r.get_json()["context"]["reverse_universal"]
    assert rev["matches"] is False and rev["within_stemloop_body"] is True


def test_cross_dimer_notes_name_the_pair(client):
    rt = STEMLOOP_BODY + reverse_complement(MIR16_DNA[-6:])
    r = client.post("/api/analyze", json={
        "matureSequence": MIR16,
        "primers": {"rt": rt, "forward": "GGCGTAGCAGCACGTAAA",
                    "reverse": "CCAGTGCAGGGTCCGAGGTA"},
    })
    for d in r.get_json()["cross_dimers"]:
        assert d["pair"] in d["note"], d["note"]          # SCI-13


# ── SCI-08: overhang range 5–7 enforced at the API boundary ────────────────────

@pytest.mark.parametrize("o, status", [(4, 400), (8, 400), ("x", 400)])
def test_design_rejects_out_of_range_overhang(client, o, status):
    r = client.post("/api/design", json={
        "sequence": {"matureSequence": MIR16},
        "primerConstraints": {"bindingRegion3prime": o},
    })
    assert r.status_code == status


# ── SCI-02 / SCI-03: scoring ──────────────────────────────────────────────────

def test_cycle1_occupancy_uses_annealing_temp():
    region = MIR16_DNA[:12]
    at60 = calculate_bound_fraction_binding(region, {"annealingTemp": 60})
    at50 = calculate_bound_fraction_binding(region, {"annealingTemp": 50})
    assert at60 < at50                                     # hotter → less bound
    assert at60 < 10                                       # not the old 42 °C ~49 %


def test_binding_occupancy_not_scored_and_total_renormalised(client):
    r = client.post("/api/design", json={"sequence": {"matureSequence": MIR16}})
    top = r.get_json()["top3"][0]
    assert "bound_fraction_binding" not in top["scores"]
    assert "bound_fraction_binding_pct" in top["scores"]
    assert "bound_fraction_binding" not in top["weights"]
    assert abs(sum(top["weights"].values()) - 1.0) < 0.01
    # total == weighted mean of the scored criteria
    total = sum(top["scores"][k] * w for k, w in top["weights"].items())
    assert abs(total - top["total_score"]) < 0.2
    assert set(UNSCORED_CRITERIA_V4) <= set(SCORING_WEIGHTS_V4)   # weights stay locked


def test_missing_mfe_is_excluded_not_invented():
    from algorithm.scoring import score_candidate
    seq = "GGCGTAGCAGCACGTAAA"
    fwd = {
        "sequence": seq, "length": len(seq), "tm_full": 60.0, "tm_binding": 45.0,
        "gc_percent": 55.0, "gc_skew": 0.0, "amplicon_size": 63,
        "specific_region": seq[-14:], "specific_length": 14,
        "structure_checks": {
            "hairpin": {"dg": -1.0, "severity": "safe", "pass": True},
            "self_dimer": {"dg_overall": -3.0, "dg_3prime": -2.0, "pass_overall": True,
                           "pass_3prime": True, "critical_3prime": False},
            "hetero_dimer": {"dg_overall": -3.0, "dg_3prime": -2.0, "pass_overall": True,
                             "pass_3prime": True, "critical_3prime": False},
            "end_stability": {"stability_kcal_mol": 5.0, "last_5_bases": seq[-5:], "pass": True},
            "overall_pass": True, "has_critical_flag": False,
        },
    }
    sl = {"mfe": None, "mfe_method": "unavailable", "gc_percent": 55, "tm_full": 70.0}
    res = score_candidate(fwd, sl, {"tm": 60.4}, {}, cross_reactivity=None, use_v4=False)
    assert "mfe_stemloop" not in res["scores"]
    assert "mfe_stemloop" in res["unscored_criteria"]
    assert abs(sum(res["weights"].values()) - 1.0) < 0.01


# ── SCI-12: LNA Tm reported in the primer3 frame ───────────────────────────────

def test_lna_tm_reported_in_primer3_frame(client):
    r = client.post("/api/lna-suggest", json={
        "sequence": "GGCGTAGCAGCACGTAAA", "mode": "tm", "target_tm": 60.0,
    })
    d = r.get_json()
    calc = d["calc_at_suggestion"]
    assert calc["tm_dna_primer3_frame"] == d["tm_reference_primer3"]
    assert abs(calc["tm_lna_primer3_frame"] - calc["tm_dna_primer3_frame"] - calc["delta_tm"]) < 0.11
    if d["lna_result"].get("target_met"):
        assert calc["tm_lna_primer3_frame"] >= 60.0 - 0.2


# ── ENG-04: oversized request bodies are rejected ─────────────────────────────

def test_oversized_body_rejected(client):
    r = client.post("/api/analyze", data=b"x" * (3 * 1024 * 1024),
                    content_type="application/json")
    assert r.status_code == 413


# ── SCI-11: Controls & contamination (parts 1 + 2) ────────────────────────────

def test_controls_table_is_assay_specific():
    from algorithm.controls_advisor import advise_controls
    span = {"mg_mM": [1.5, 3.0], "tm_c": [80.8, 83.8]}
    sybr = advise_controls("hsa-miR-X", MIR16, "sybr", span)
    taq = advise_controls("hsa-miR-X", MIR16, "taqman", span)
    names = [c["name"] for c in sybr["controls"]]
    assert names[:4] == ["NTC (water)", "RT-NTC", "No-RT", "Positive control"]
    assert MIR16 in sybr["controls"][3]["setup"]                  # synthetic oligo = mature
    assert "≥ 10" in sybr["controls"][0]["pass"]                   # lab ΔCq convention
    assert sybr["melt_note"] and "positive control" in sybr["melt_note"]
    assert taq["melt_note"] is None and "probe" in taq["controls"][0]["setup"]


def test_contamination_risk_sources(monkeypatch):
    import algorithm.controls_advisor as ca
    db = {"_metadata": {}, "hsa-miR-HI": {"median_total_rpm": 5000.0, "abundance_percentile": 99.0},
          "hsa-miR-LO": {"median_total_rpm": 3.0, "abundance_percentile": 40.0}}
    monkeypatch.setattr(ca, "_load_db3", lambda: db)
    assert ca.advise_controls("hsa-miR-HI", MIR16, "sybr")["contamination"]["risk"] == "elevated"
    assert ca.advise_controls("hsa-miR-LO", MIR16, "sybr")["contamination"]["risk"] == "standard"
    monkeypatch.setattr(ca, "_lab_synthetic_controls", lambda: ["cel-mir-39-3p"])
    res = ca.advise_controls("cel-miR-39-3p", MIR16, "sybr")
    assert res["contamination"]["risk"] == "elevated"
    assert any("triplicate" in p for p in res["contamination"]["precautions"])


def test_pdf_contains_controls_section(client):
    r = client.post("/api/design", json={"sequence": {"matureSequence": MIR16},
                                         "detectionMethod": {"signalMethod": "sybr"}})
    results = r.get_json()
    assert results["controls_advice"]["ntc_delta_cq_min"] == 10
    pdf = client.post("/api/export", json={"format": "pdf", "results": results, "history_count": 1})
    assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF"
