import pytest
# ================================================================
# tests/test_isomir_flag.py
# Unit tests for specificity_check/isomir_flag.py
#
# v2.1 (2026-07-02): isoMiR flag simplified to DB lookup only (spec §6.3).
#   Known miRNA → isomir_discrimination_risk = True (always, regardless of position)
#   Unknown miRNA → isomir_discrimination_risk = False
#
# Removed: geometric risk_window check (was never True for 12–17 nt primers).
# ================================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.specificity_check.isomir_flag import check_isomir_flag


# ── Case 1: Known isomiR miRNA — always flags True ────────────────

def test_isomir_flag_triggers_for_known_mirna():
    """hsa-miR-21-5p is in the DB → risk=True regardless of primer position."""
    result = check_isomir_flag(
        mirna_name="hsa-miR-21-5p",
        forward_3prime_position=15,
    )
    assert result["isomir_discrimination_risk"] is True
    assert result["mirna_name"] == "hsa-miR-21-5p"


def test_known_mirna_short_position_still_true():
    """Position within old risk_window — still True under new DB-only logic."""
    result = check_isomir_flag(
        mirna_name="hsa-miR-21-5p",
        forward_3prime_position=2,
    )
    assert result["isomir_discrimination_risk"] is True


def test_known_mirna_long_position_still_true():
    """Typical specific_length=15 → still True (geometric check removed)."""
    result = check_isomir_flag(
        mirna_name="hsa-miR-21-5p",
        forward_3prime_position=15,
    )
    assert result["isomir_discrimination_risk"] is True


def test_miR10a_known_flags_true():
    """hsa-miR-10a-5p is in the DB → True for any position."""
    for pos in [3, 4, 12, 17]:
        r = check_isomir_flag("hsa-miR-10a-5p", forward_3prime_position=pos)
        assert r["isomir_discrimination_risk"] is True, f"Expected True at pos {pos}"


# ── Case 2: Unknown miRNA ─────────────────────────────────────────

def test_unknown_mirna_no_risk():
    """A miRNA not in the DB → risk=False with informational note."""
    result = check_isomir_flag(
        mirna_name="hsa-miR-UNKNOWN-5p",
        forward_3prime_position=12,
    )
    assert result["isomir_discrimination_risk"] is False
    assert result["risk_window_nt"] is None
    assert "No known 5' isomiR" in result["note"]


# ── Output structure ──────────────────────────────────────────────

def test_output_has_required_keys_known():
    """All required keys present for a known miRNA."""
    result = check_isomir_flag("hsa-miR-21-5p", forward_3prime_position=12)
    for key in ("isomir_discrimination_risk", "mirna_name", "forward_3prime_position",
                "known_5prime_shift_nt", "risk_window_nt", "note", "co_amplification_warning"):
        assert key in result, f"Missing key: {key}"


def test_output_has_required_keys_unknown():
    """All required keys present for an unknown miRNA."""
    result = check_isomir_flag("hsa-miR-UNKNOWN-5p", forward_3prime_position=12)
    for key in ("isomir_discrimination_risk", "mirna_name", "forward_3prime_position",
                "risk_window_nt", "note", "data_warning"):
        assert key in result, f"Missing key: {key}"


def test_output_boolean_type():
    result = check_isomir_flag("hsa-miR-21-5p", 3)
    assert isinstance(result["isomir_discrimination_risk"], bool)


def test_co_amplification_warning_present_for_known():
    """co_amplification_warning must be a non-empty string for known miRNAs."""
    result = check_isomir_flag("hsa-miR-21-5p", 12)
    assert isinstance(result.get("co_amplification_warning"), str)
    assert len(result["co_amplification_warning"]) > 0


if __name__ == "__main__":
    test_isomir_flag_triggers_for_known_mirna()
    test_known_mirna_short_position_still_true()
    test_known_mirna_long_position_still_true()
    test_miR10a_known_flags_true()
    test_unknown_mirna_no_risk()
    test_output_has_required_keys_known()
    test_output_has_required_keys_unknown()
    test_output_boolean_type()
    test_co_amplification_warning_present_for_known()
    print("\nAll isomir_flag tests passed.")


# ── Week2 C11: 3' isomiR flag ─────────────────────────────────────
from algorithm.specificity_check import isomir_flag as _iso3


_FAKE_META = {"coverage_warning": "Human only.", "source": {"name": "isomiRdb", "pmid": "36243964"}}


def _entry(f):
    return {"median_3prime_fraction": f, "iqr_3prime_fraction": [f - 0.05, f + 0.05],
            "pooled_3prime_fraction": f, "n_samples_expressed": 1000,
            "top_3prime_variants": [{"sequence_dna": "ACGT", "label": "lv3p|lv3pT|lv3p#-1",
                                     "pooled_share": 0.3}]}


def test_3prime_no_entry_returns_false(monkeypatch):
    monkeypatch.setattr(_iso3, "_DB3_CACHE", {"_metadata": _FAKE_META})
    res = _iso3.check_3prime_isomir_flag("hsa-miR-NOPE-5p", overhang_len=6)
    assert res["three_prime_isomir_risk"] is False
    assert res["level"] == "no_data"
    assert "not evidence" in res["note"]


def test_3prime_majority_isoforms_raise_warning(monkeypatch):
    monkeypatch.setattr(_iso3, "_DB3_CACHE", {"_metadata": _FAKE_META, "hsa-miR-T-3p": _entry(0.89)})
    res = _iso3.check_3prime_isomir_flag("hsa-miR-T-3p", overhang_len=6)
    assert res["three_prime_isomir_risk"] is True and res["level"] == "high"
    assert "89%" in res["warning"] and "minority" in res["warning"]
    assert res["source"] == "isomiRdb (PMID 36243964)"


@pytest.mark.parametrize("f, level", [(0.49, "moderate"), (0.20, "moderate"), (0.19, "low")])
def test_3prime_tiers_below_majority_are_informational(monkeypatch, f, level):
    monkeypatch.setattr(_iso3, "_DB3_CACHE", {"_metadata": _FAKE_META, "hsa-miR-T-3p": _entry(f)})
    res = _iso3.check_3prime_isomir_flag("hsa-miR-T-3p")
    assert res["three_prime_isomir_risk"] is False
    assert res["level"] == level and res["warning"] is None and res["summary"]



def test_3prime_abundance_only_entry_is_no_data(monkeypatch):
    monkeypatch.setattr(_iso3, "_DB3_CACHE", {"_metadata": _FAKE_META,
                                              "hsa-miR-A-5p": {"median_total_rpm": 5.0,
                                                               "abundance_percentile": 50.0}})
    res = _iso3.check_3prime_isomir_flag("hsa-miR-A-5p")
    assert res["level"] == "no_data" and res["three_prime_isomir_risk"] is False


# ── fold-change bias warning (Nejad 2018) ────────────────────────

def test_fold_change_bias_fires_on_large_variable_isoform_pool():
    """miR-222-3p is Nejad 2018's own example: a big 3'-isoform pool whose share
    also swings between samples."""
    from algorithm.specificity_check.isomir_flag import check_3prime_isomir_flag
    r = check_3prime_isomir_flag("hsa-miR-222-3p", 6)
    assert r["fold_change_bias_risk"] is True
    w = r["fold_change_bias_warning"]
    assert "Nejad" in w and "fold change" in w
    # Qualitative only — never a numeric bias factor.
    assert "×" not in w and "fold-change of" not in w


def test_fold_change_bias_needs_both_size_and_spread():
    from algorithm.specificity_check.isomir_flag import _fold_change_bias_warning
    assert _fold_change_bias_warning("x", 0.05, 0.0, 0.9) is None    # pool too small
    assert _fold_change_bias_warning("x", 0.80, 0.78, 0.82) is None  # stable share
    assert _fold_change_bias_warning("x", 0.40, 0.25, 0.60) is not None


def test_fold_change_bias_absent_without_data():
    from algorithm.specificity_check.isomir_flag import check_3prime_isomir_flag
    r = check_3prime_isomir_flag("mmu-miR-99999-5p", 6)
    assert r["level"] == "no_data"
    assert r.get("fold_change_bias_risk") in (None, False)


# ── 3' variants vs the design sequence + dominant isoform (2026-11-21) ──
# Rules: docs/ISOMIR_VARIANTS_DRYRUN.md (approved by the project owner).

import json as _json
from algorithm.constants import ASSAY_DCQ_RT_SHIFT_RANGE as _RANGE

_DRYRUN = os.path.join(os.path.dirname(__file__), "..", "..", "benchmark",
                       "isomir_variants_dryrun.json")


def _variants(name, overhang=6, **kw):
    return _iso3.check_3prime_isomir_flag(name, overhang, **kw)["dominant_3prime_variants"]


def _record_rt_axis(monkeypatch):
    calls = []
    real = _iso3.rt_axis
    monkeypatch.setattr(_iso3, "rt_axis", lambda t, o, n: calls.append(o) or real(t, o, n))
    return calls


def test_variant_keys_only_added():
    raw = _iso3._load_db3()["hsa-miR-21-5p"]["top_3prime_variants"]
    for v, r in zip(_variants("hsa-miR-21-5p"), raw):
        for k in ("sequence_dna", "label", "pooled_share"):
            assert v[k] == r[k]
        assert {"shift_3p", "relation", "type_label", "rt_capture"} <= set(v)
        assert set(v["rt_capture"]) == {"class", "delta_cq_low", "delta_cq_high",
                                        "n_mirnas", "label", "note"}


def test_mir222_plus3_is_outside_measured_range_without_rt_axis(monkeypatch):
    """The 8-Ct register artefact of rt_axis (|shift| > 2) never reaches the output."""
    calls = _record_rt_axis(monkeypatch)
    v = _variants("hsa-miR-222-3p")
    plus3 = next(x for x in v if len(x["sequence_dna"]) == 24)
    assert plus3["shift_3p"] == 3 and plus3["relation"] == "extended"
    cap = plus3["rt_capture"]
    assert cap["class"] == "outside_measured_range"
    assert cap["delta_cq_low"] is None and cap["delta_cq_high"] is None
    assert plus3["sequence_dna"] not in calls
    assert all(x["rt_capture"]["delta_cq_low"] != 8.0 for x in v)


@pytest.mark.parametrize("overhang", [5, 6, 7])
def test_mir21_shifts_are_measured_range(overhang):
    lo, hi, n = _RANGE["longer"]
    got = {x["shift_3p"]: x for x in _variants("hsa-miR-21-5p", overhang)}
    assert set(got) == {1, -1, 2}
    for x in got.values():
        cap = x["rt_capture"]
        assert cap["class"] == "measured_range"
        assert (cap["delta_cq_low"], cap["delta_cq_high"], cap["n_mirnas"]) == (lo, hi, n)
    assert got[-1]["type_label"] == "−1 nt" and got[2]["type_label"] == "+2 nt"


def test_mir486_nta_a_is_assumed_templated():
    v = next(x for x in _variants("hsa-miR-486-5p") if x["label"].startswith("nta#A"))
    assert v["relation"] == "nta" and v["added_nt"] == "A" and v["trimmed_nt"] == 0
    assert v["rt_capture"]["class"] == "assumed_templated"
    assert v["rt_capture"]["delta_cq_low"] == _RANGE["longer"][0]
    assert "not measured by qPCR" in v["rt_capture"]["note"]
    assert v["type_label"] == "+A non-templated"


def test_nta_on_templated_extension_is_labelled_as_both():
    """nta#T#1 on a 2-nt-longer tail = 1 nt templated, then +U."""
    v = next(x for x in _variants("hsa-miR-133a-3p") if x["relation"] == "nta")
    assert v["shift_3p"] == 2 and v["templated_nt"] == 1 and v["added_nt"] == "U"
    assert v["type_label"] == "+1 nt then +U"
    assert v["rt_capture"]["class"] == "assumed_templated"


def test_trimmed_then_nta_is_not_measured_without_rt_axis(monkeypatch):
    calls = _record_rt_axis(monkeypatch)
    v = _variants("hsa-miR-107")[1]          # ...UAUCA -> ...UAUCU
    assert v["relation"] == "nta" and v["trimmed_nt"] == 1 and v["added_nt"] == "U"
    assert v["type_label"] == "−1 nt then +U"
    assert v["rt_capture"]["class"] == "not_measured"
    assert v["rt_capture"]["delta_cq_low"] is None
    assert "Czimmerer" in v["rt_capture"]["note"]
    assert v["sequence_dna"] not in calls


@pytest.mark.parametrize("name", ["hsa-miR-1275", "hsa-miR-8485"])      # mlv3p, mv
def test_mlv3p_and_mv_are_other_not_measured(name):
    v = next(x for x in _variants(name) if x["label"].split("|")[0] in ("mlv3p", "mv"))
    assert v["relation"] == "other" and v["rt_capture"]["class"] == "not_measured"


def test_variant_differing_from_22_1_in_a_confirmed_mirna():
    r = _iso3.check_3prime_isomir_flag("hsa-miR-133a-3p", 6)
    assert r["reference_status"] == "matches"
    v = next(x for x in r["dominant_3prime_variants"] if x["relation"] == "reference_mismatch")
    assert v["rt_capture"]["class"] == "not_assessed"
    assert v["rt_capture"]["note"] == "differs from miRBase 22.1 — not assessed"


def test_reference_may_differ_suppresses_dominant_warning():
    r = _iso3.check_3prime_isomir_flag("hsa-miR-1246", 6)
    assert r["reference_status"] == "isomirdb_reference_may_differ"
    assert r["reference_note"] == ("isomiRdb reference may differ from miRBase 22.1 "
                                   "— not assessed")
    assert r["dominant_isoform_risk"] is False and r["dominant_isoform_warning"] is None
    assert {x["rt_capture"]["class"] for x in r["dominant_3prime_variants"]} == {"not_assessed"}
    # old warnings stay as they were (owner decision c)
    assert r["three_prime_isomir_risk"] is (r["level"] == "high")


def test_design_sequence_differing_from_22_1_is_not_assessed():
    """miR-877-5p typed as the 24-nt GACA form (Schamberger14), not the 22.1 20-mer."""
    r = _iso3.check_3prime_isomir_flag("hsa-miR-877-5p", 6,
                                       target_seq="GUAGAGGAGAUGGCGCAGGGGACA")
    assert r["reference_status"] == "design_sequence_differs"
    assert r["dominant_isoform_risk"] is False
    assert {x["rt_capture"]["class"] for x in r["dominant_3prime_variants"]} == {"not_assessed"}
    same = _iso3.check_3prime_isomir_flag("hsa-miR-877-5p", 6,
                                          target_seq="GUAGAGGAGAUGGCGCAGGG")
    assert same["reference_status"] == "matches" and same["dominant_isoform_risk"] is True


def test_dominant_isoform_fires_on_mir222_not_mir21():
    r = _iso3.check_3prime_isomir_flag("hsa-miR-222-3p", 6)
    assert r["canonical_3prime_share_pooled"] == round(1 - 0.912, 3)
    assert r["dominant_isoform_risk"] is True
    w = r["dominant_isoform_warning"]
    for s in ("+3 nt", "36% of reads, pooled", "9% (pooled)", "miRBase 22.1 3' end",
              "not measured", "PMID 30487268", "isomiRdb pools all sample types"):
        assert s in w, s
    assert "median" not in w                     # never mixed with the median
    r21 = _iso3.check_3prime_isomir_flag("hsa-miR-21-5p", 6)
    assert r21["dominant_isoform_risk"] is False and r21["dominant_isoform_warning"] is None


def test_dominant_isoform_uses_the_full_range_for_measured_variants():
    w = _iso3.check_3prime_isomir_flag("hsa-miR-27b-3p", 6)["dominant_isoform_warning"]
    lo, hi, _ = _RANGE["short1"]
    assert f"captured {lo:g}–{hi:g} Ct later" in w and "two miRNAs measured" in w


def test_dominant_isoform_rule_r2_boundary(monkeypatch):
    """top-1 >= 0.8 x canonical on the 3-decimal values; 0.8 = own threshold."""
    def db(top):
        return {"_metadata": _FAKE_META, "hsa-miR-21-5p": {
            "median_3prime_fraction": 0.5, "iqr_3prime_fraction": [0.45, 0.55],
            "pooled_3prime_fraction": 0.5, "n_samples_expressed": 10,
            "top_3prime_variants": [{"sequence_dna": "TAGCTTATCAGACTGATGTTGAC",
                                     "label": "lv3p|lv3pE|lv3p#1", "pooled_share": top}]}}
    monkeypatch.setattr(_iso3, "_DB3_CACHE", db(0.4))          # 0.4 = 0.8 x 0.5
    assert _iso3.check_3prime_isomir_flag("hsa-miR-21-5p", 6)["dominant_isoform_risk"] is True
    monkeypatch.setattr(_iso3, "_DB3_CACHE", db(0.399))
    assert _iso3.check_3prime_isomir_flag("hsa-miR-21-5p", 6)["dominant_isoform_risk"] is False


def test_capture_warning_no_longer_says_about_as_well():
    w = _iso3.check_3prime_isomir_flag("hsa-miR-222-3p", 6)["warning"]
    assert "about as well" not in w
    for key in ("short1", "short2"):
        lo, hi, _ = _RANGE[key]
        assert f"{lo:g}–{hi:g} Ct later" in w
    assert "two miRNAs measured" in w and "one miRNA measured" in w


def test_mouse_mirna_without_data_has_no_dominant_warning():
    r = _iso3.check_3prime_isomir_flag("mmu-miR-21a-5p", 6, target_seq="UAGCUUAUCAGACUGAUGUUGA")
    assert r["level"] == "no_data"
    assert r["dominant_isoform_risk"] is False and r["dominant_isoform_warning"] is None


def _all_names():
    return [k for k, v in _iso3._load_db3().items()
            if not k.startswith("_") and "median_3prime_fraction" in v]


def test_rt_axis_register_matches_sequence_shift_at_5_6_7_nt():
    """Templated 1-2-nt variants: rt_axis' best register equals the sequence shift at
    every supported overhang, except four repeat ends at 5 nt (GUGUG, UUUUUC, UUGUU),
    where another register pairs the whole overhang too; those are class 'other'."""
    expected_other = {5: {("hsa-miR-1228-5p", -1), ("hsa-miR-1228-5p", -2),
                          ("hsa-miR-498-5p", -2), ("hsa-miR-7-5p", -2)}, 6: set(), 7: set()}
    for oh, exp in expected_other.items():
        other, checked = set(), 0
        for n in _all_names():
            for v in _variants(n, oh):
                if v["relation"] in ("trimmed", "extended") and 1 <= abs(v["shift_3p"]) <= 2:
                    if v["rt_capture"]["class"] == "not_assessed":
                        continue                    # reference not assessed
                    checked += 1
                    if v["rt_capture"]["class"] == "other":
                        other.add((n, v["shift_3p"]))
                        assert "register" in v["rt_capture"]["note"]
                    else:
                        assert v["rt_capture"]["class"] == "measured_range"
        assert other == exp, oh
        assert checked == 1855


def test_matches_dry_run_counts():
    """The web-app code reproduces the approved dry-run over all 2927 variants."""
    with open(_DRYRUN, encoding="utf-8") as fh:
        d = _json.load(fh)
    cls, fired = {}, 0
    for n in _all_names():
        r = _iso3.check_3prime_isomir_flag(n, 6)
        fired += r["dominant_isoform_risk"]
        for v in r["dominant_3prime_variants"]:
            c = v["rt_capture"]["class"]
            cls[c] = cls.get(c, 0) + 1
    assert {k: v for k, v in d["1_2_capture_class"]["final"].items() if v} == cls
    assert sum(cls.values()) == 2927
    assert fired == d["1_4_rules"]["R2"]["n_fire"] == 304


def test_stemloop_emits_dominant_warning_for_mir222():
    from algorithm.stemloop_rt import design_stemloop_rt
    sl = design_stemloop_rt("AGCUACAUCUGGCUACUGGGU", {}, mirna_name="hsa-miR-222-3p")
    assert "three_prime_isomir_dominant" in [w["field"] for w in sl["warnings"]]
    sl21 = design_stemloop_rt("UAGCUUAUCAGACUGAUGUUGA", {}, mirna_name="hsa-miR-21-5p")
    assert "three_prime_isomir_dominant" not in [w["field"] for w in sl21["warnings"]]
