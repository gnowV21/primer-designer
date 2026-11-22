# ================================================================
# tests/test_export.py — Backend tests for POST /api/export (Phase 4)
# ================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from app import app

# Minimal results fixture mimicking /api/design response
_RESULTS = {
    "top3": [
        {
            "rank": 1, "sequence": "GCTATCAGACTGATGTTGA", "length": 19,
            "tm_full": 59.8, "tm_binding": 45.2, "gc_percent": 47.4,
            "amplicon_size": 82, "total_score": 81.5, "grade": "Excellent",
            "specific_length": 12, "specific_region": "TAGCTTATCAGA",
            "binding_start_1based": 1, "binding_end_1based": 12,
            "structure_checks": {
                "hairpin": {"dg": -1.2, "severity": "safe"},
                "self_dimer": {"dg": -2.1},
                "end_stability": {"stability_kcal_mol": 4.5, "pass": True},
                "overall_pass": True, "has_critical_flag": False,
            },
            "heterodimer_checks": {
                "fwd_reverse": {"dg": -3.0},
                "fwd_stemloop": {"dg": -2.5},
            },
            "scores": {"bound_fraction_binding_pct": 4.1, "gc_clamp": 100},
            "isomir_flag": {"isomir_discrimination_risk": False},
        },
        {
            "rank": 2, "sequence": "AGCTATCAGACTGATGTTGA", "length": 20,
            "tm_full": 60.1, "gc_percent": 45.0, "amplicon_size": 83,
            "total_score": 78.0, "grade": "Good",
            "specific_length": 13, "specific_region": "TAGCTTATCAGAC",
            "structure_checks": {"hairpin": {"dg": -1.0}, "self_dimer": {"dg": -1.5},
                                 "end_stability": {"stability_kcal_mol": 4.0, "pass": True},
                                 "overall_pass": True, "has_critical_flag": False},
            "heterodimer_checks": {"fwd_reverse": {"dg": -2.8}, "fwd_stemloop": {"dg": -2.0}},
            "scores": {"bound_fraction_binding_pct": 3.2, "gc_clamp": 100},
            "isomir_flag": {"isomir_discrimination_risk": False},
        },
        {
            "rank": 3, "sequence": "TAGCTATCAGACTGATGTTGA", "length": 21,
            "tm_full": 61.0, "gc_percent": 42.9, "amplicon_size": 84,
            "total_score": 75.0, "grade": "Good",
            "specific_length": 14, "specific_region": "TAGCTTATCAGACT",
            "structure_checks": {"hairpin": {"dg": -0.8}, "self_dimer": {"dg": -1.2},
                                 "end_stability": {"stability_kcal_mol": 3.8, "pass": True},
                                 "overall_pass": True, "has_critical_flag": False},
            "heterodimer_checks": {"fwd_reverse": {"dg": -2.5}, "fwd_stemloop": {"dg": -1.9}},
            "scores": {"bound_fraction_binding_pct": 2.0, "gc_clamp": 60},
            "isomir_flag": {"isomir_discrimination_risk": False},
        },
    ],
    "stemloop_rt": {
        "sequence": "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACTCAACA",
        "length": 50, "tm_full": 69.0, "gc_percent": 56.0,
        "mfe": -27.5, "mfe_method": "ViennaRNA",
        "self_structure_check": {"hairpin_dg": -25.0},
    },
    "universal_reverse": {
        "sequence": "CCAGTGCAGGGTCCGAGGTA", "length": 20,
        "tm": 60.4, "gc_percent": 65.0,
        "self_structure_check": {"hairpin_dg": -3.0, "self_dimer_dg": -2.0},
    },
    "global_warnings": [],
    "edge_cases": [],
    "metadata": {
        "mirna_id": "hsa-miR-21-5p", "mirna_sequence": "UAGCUUAUCAGACUGAUGUUGA",
        "mirna_length": 22, "algorithm_version": "3.0.0",
        "scoring_version": "V4 (15 criteria)",
        "candidates_generated": 45, "candidates_passed_prefilter": 12,
        "elapsed_seconds": 1.23,
        "sources": ["Chen et al. 2005"],
    },
}


def _post(fmt, results=None):
    client = app.test_client()
    body = {"format": fmt, "results": results if results is not None else _RESULTS}
    return client.post("/api/export", json=body)


# ── CSV tests ─────────────────────────────────────────────────────

def test_export_csv_content_type():
    r = _post("csv")
    assert r.status_code == 200
    assert "text/csv" in r.content_type


def test_export_csv_has_attachment():
    r = _post("csv")
    cd = r.headers.get("Content-Disposition", "")
    assert "attachment" in cd
    assert ".csv" in cd


def test_export_csv_has_all_roles():
    r = _post("csv")
    text = r.data.decode("utf-8")
    for role in ("Forward", "RT_StemLoop", "Universal_Reverse"):
        assert role in text, f"Missing role: {role}"


def test_export_csv_header_comment():
    r = _post("csv")
    text = r.data.decode("utf-8")
    assert text.startswith("# HG Lab")
    assert "hsa-miR-21-5p" in text


def test_export_csv_has_column_headers():
    r = _post("csv")
    text = r.data.decode("utf-8")
    assert "Set_Rank" in text
    assert "Sequence" in text
    assert "Tm_C" in text


def test_export_csv_filename_sanitized():
    """Path traversal in mirna_id must not allow directory traversal in filename.
    After sanitisation, '..' must be collapsed; '/' is already stripped by _SAFE_CHARS.
    The remaining words (e.g. 'passwd') are harmless once traversal tokens are gone.
    """
    results = dict(_RESULTS)
    results["metadata"] = dict(_RESULTS["metadata"])
    results["metadata"]["mirna_id"] = "../../etc/passwd"
    r = _post("csv", results)
    cd = r.headers.get("Content-Disposition", "")
    assert ".." not in cd          # no double-dot traversal
    assert "/" not in cd.split("filename=")[-1]   # no path separator


# ── PDF tests ─────────────────────────────────────────────────────

def test_export_pdf_returns_pdf_bytes():
    try:
        import reportlab  # noqa
    except ImportError:
        import pytest; pytest.skip("reportlab not installed")
    r = _post("pdf")
    assert r.status_code == 200
    assert r.data[:4] == b"%PDF"


def test_export_pdf_content_type():
    try:
        import reportlab  # noqa
    except ImportError:
        import pytest; pytest.skip("reportlab not installed")
    r = _post("pdf")
    assert "application/pdf" in r.content_type


def test_export_pdf_has_attachment():
    try:
        import reportlab  # noqa
    except ImportError:
        import pytest; pytest.skip("reportlab not installed")
    r = _post("pdf")
    assert "attachment" in r.headers.get("Content-Disposition", "")


# ── Validation tests ──────────────────────────────────────────────

def test_export_invalid_format_400():
    r = _post("docx")
    assert r.status_code == 400
    assert "format" in r.get_json()["error"].lower()


def test_export_missing_results_400():
    client = app.test_client()
    r = client.post("/api/export", json={"format": "csv"})
    assert r.status_code == 400


def test_export_empty_top3_400():
    results = dict(_RESULTS)
    results["top3"] = []
    r = _post("csv", results)
    assert r.status_code == 400


def test_export_filename_contains_mirna_id():
    r = _post("csv")
    cd = r.headers.get("Content-Disposition", "")
    assert "hsa-miR-21-5p" in cd or "hsa-miR-21" in cd


if __name__ == "__main__":
    test_export_csv_content_type()
    test_export_csv_has_attachment()
    test_export_csv_has_all_roles()
    test_export_csv_header_comment()
    test_export_csv_has_column_headers()
    test_export_csv_filename_sanitized()
    test_export_invalid_format_400()
    test_export_missing_results_400()
    test_export_empty_top3_400()
    test_export_filename_contains_mirna_id()
    print("\nAll export tests passed (PDF skipped if reportlab not installed).")


# ── Tiered sets (algorithm 4.0.0, SPEC_ui_tiered_4.0.0 §2.5) ──────────

def _tiered_results():
    import copy
    res = copy.deepcopy(_RESULTS)
    res["metadata"] = {**res.get("metadata", {}), "scoring_system": "tiered"}
    for s, (s1, veto, floor, viol) in zip(res["top3"], [(5, False, False, []),
                                                         (4, True, False, ["hard_hairpin_tm"]),
                                                         (None, False, True, ["gc_clamp_fail"])]):
        s["grade"] = "A" if s1 == 5 else "B"
        s["grade_reasons"] = [] if s1 == 5 else ["structure veto", "binding Tm below the 39 °C floor"]
        s["v4_rule_violations"] = viol
        s["ranking"] = {
            "system": "tiered",
            "specificity": {"blast": {"score": s1}, "assay_dcq": {"score": 4},
                            "tm_margin": {"score": 5}, "total": (s1 or 0) + 9,
                            "max": 15 if s1 is not None else 10},
            "pcr": {"total": 5, "max": 5}, "flexible": {"total": 17, "max": 20},
            "structure_veto": veto, "binding_floor_fail": floor, "eliminated": False,
            "detailed_score": s["total_score"],
        }
    return res


def _csv_rows(text):
    import csv as _csv
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    rows = list(_csv.reader(lines))
    return rows[0], rows[1:]


def test_export_csv_tiered_columns():
    r = _post("csv", _tiered_results())
    header, rows = _csv_rows(r.data.decode("utf-8"))
    # Column titles follow the criteria groups (2026-11-22); order and values unchanged.
    cols = ("scoring_system", "grade", "grade_reasons", "Req_S1_BLAST", "Req_S2_dCq", "Req_S3_Tm_margin",
            "Req_S_total", "Flex2_PCR", "Flex3_composition_structure", "Flex1_structure",
            "Flex1_binding_floor", "Flex1_standard_rules", "tie_break_score")
    i0 = header.index("scoring_system")
    assert tuple(header[i0:i0 + len(cols)]) == cols
    for old in ("S1", "S_total", "P_total", "F_total", "structure_veto", "v4_rule_violations"):
        assert old not in header, old
    assert "Total_Score" not in header
    rec = {h: v for h, v in zip(header, rows[0])}
    assert (rec["scoring_system"], rec["grade"], rec["Req_S1_BLAST"], rec["Req_S_total"]) == \
        ("tiered", "A", "5", "14/15")
    assert rec["tie_break_score"] == "81.5"
    rec3 = {h: v for h, v in zip(header, rows[2])}
    assert (rec3["Req_S1_BLAST"], rec3["Req_S_total"], rec3["Flex1_binding_floor"],
            rec3["Flex1_standard_rules"]) == ("n/a", "9/10", "True", "gc_clamp_fail")
    # The shared RT / reverse rows stay aligned with the header.
    assert all(len(r_) == len(header) for r_ in rows[:5])


def test_export_csv_v4_header_unchanged():
    header, _ = _csv_rows(_post("csv").data.decode("utf-8"))
    assert header == ["Set_Rank", "Primer_Role", "Sequence", "Length_nt", "Tm_C", "GC_percent",
                      "Hairpin_dG_kcalmol", "SelfDimer_dG_kcalmol", "Amplicon_bp", "Total_Score",
                      "Grade", "Notes"]


def test_export_pdf_tiered_ok():
    r = _post("pdf", _tiered_results())
    assert r.status_code in (200, 503)   # 503 = reportlab missing
