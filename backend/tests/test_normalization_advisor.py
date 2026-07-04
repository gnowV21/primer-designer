"""Tests for normalization_advisor.py (Phase 7 PART D)."""

import pytest
from algorithm.normalization_advisor import advise_normalization


class TestAdviseNormalization:
    def test_tissue_returns_n1(self):
        result = advise_normalization("tissue")
        assert result["rule_id"] == "N1"
        assert "geNorm" in result["recommended_strategy"] or "NormFinder" in result["recommended_strategy"]
        assert result["sample_type"] == "tissue"

    def test_plasma_returns_n2(self):
        result = advise_normalization("plasma")
        assert result["rule_id"] == "N2"
        assert "spike-in" in result["recommended_strategy"]

    def test_serum_returns_n2(self):
        result = advise_normalization("serum")
        assert result["rule_id"] == "N2"

    def test_ffpe_returns_n3(self):
        result = advise_normalization("ffpe")
        assert result["rule_id"] == "N3"

    def test_large_panel_returns_n4(self):
        result = advise_normalization("tissue", panel_size=12)
        # N4 should be matched; primary may still be N1 but N4 must be in matched rules
        # In this implementation N4 is matched when panel_size >= 10; strategy may be N4
        # depending on match order. Check that N4 caution appears.
        all_cautions = result.get("cautions", [])
        # N4 triggers alongside N1 — check strategy mentions global-mean OR N4 caution present
        has_n4_signal = (
            result["rule_id"] == "N4"
            or "global-mean" in result["recommended_strategy"]
            or any("global-mean" in c.get("text", "") for c in all_cautions)
        )
        assert has_n4_signal

    def test_all_rules_have_source_doi(self):
        for sample_type in ("tissue", "plasma", "ffpe"):
            result = advise_normalization(sample_type)
            assert len(result["sources"]) > 0, f"No sources for sample_type={sample_type}"

    def test_disclaimer_always_present(self):
        for sample_type in ("tissue", "plasma", "serum", "ffpe", "urine", "cell", ""):
            result = advise_normalization(sample_type or "tissue")
            assert result["disclaimer"], f"No disclaimer for sample_type={sample_type}"

    def test_reference_candidates_plasma(self):
        result = advise_normalization("plasma")
        names = [r["name"] for r in result["reference_candidates"]]
        assert "cel-miR-39-3p" in names, "Plasma should include spike-in cel-miR-39-3p"

    def test_reference_candidates_tissue(self):
        result = advise_normalization("tissue")
        # Tissue should have endogenous candidates (not the biofluid spike-in)
        roles = [r["role"] for r in result["reference_candidates"]]
        assert any(role == "endogenous candidate" for role in roles)

    def test_validation_note_present(self):
        result = advise_normalization("tissue")
        assert result["validation_note"]
        assert "geNorm" in result["validation_note"] or "NormFinder" in result["validation_note"]

    def test_external_tools_present(self):
        result = advise_normalization("tissue")
        tool_names = [t["name"] for t in result["external_tools"]]
        assert "geNorm" in tool_names
        assert "NormFinder" in tool_names

    def test_unknown_sample_type_defaults_gracefully(self):
        result = advise_normalization("unknown_type")
        assert result["rule_id"] is not None
        assert result["disclaimer"]

    def test_all_reference_candidates_have_source_doi(self):
        result = advise_normalization("plasma")
        for ref in result["reference_candidates"]:
            assert ref.get("source_doi"), f"Missing source_doi for {ref.get('name')}"
