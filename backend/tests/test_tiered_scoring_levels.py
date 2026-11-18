"""
test_tiered_scoring_levels.py — boundaries of every 1–5 table of the tiered system
(docs/SPEC_scoring_tiered_4.0.0.md §3; algorithm/tiered_scoring.py).
"""
import pytest

from algorithm import tiered_scoring as ts


@pytest.mark.parametrize("risk, n, lvl", [
    ("SAFE", 0, 5), ("MEDIUM", 1, 4), ("MEDIUM", 2, 3), ("MEDIUM", 5, 3),
    ("HIGH", 1, 2), ("CRITICAL", 1, 1), (None, 0, None),
])
def test_s1_blast(risk, n, lvl):
    assert ts.s1_blast(risk, n) == lvl


@pytest.mark.parametrize("dcq, lvl", [
    (None, 5), (10.0, 5), (9.99, 4), (7.0, 4), (6.99, 3), (4.3, 3), (4.29, 2),
    (3.3, 2), (3.29, 1), (0.0, 1),
])
def test_s2_assay_dcq(dcq, lvl):
    assert ts.s2_assay_dcq(dcq) == lvl


@pytest.mark.parametrize("margin, lvl", [
    (None, 5), (15.0, 5), (14.9, 4), (10.0, 4), (9.9, 3), (7.5, 3), (7.4, 2),
    (5.0, 2), (4.9, 1), (-3.0, 1),
])
def test_s3_tm_margin(margin, lvl):
    assert ts.s3_tm_margin(margin) == lvl


@pytest.mark.parametrize("diff, lvl", [
    (0.0, 5), (1.0, 5), (1.01, 4), (2.0, 4), (2.01, 3), (3.0, 3), (3.01, 2), (5.0, 2), (5.01, 1),
])
def test_p1_and_p2(diff, lvl):
    assert ts.p1_tm_pair(60.0 + diff, 60.0) == lvl
    assert ts.p1_tm_pair(60.0 - diff, 60.0) == lvl
    assert ts.p2_tm_vs_ta(60.0 + diff, 60.0) == lvl


@pytest.mark.parametrize("gc, lvl", [
    (40, 5), (60, 5), (50, 5), (39.9, 4), (35, 4), (60.1, 4), (65, 4),
    (34.9, 3), (30, 3), (65.1, 3), (70, 3), (29.9, 2), (25, 2), (70.1, 2), (75, 2),
    (24.9, 1), (75.1, 1), (90, 1),
])
def test_f1_gc(gc, lvl):
    assert ts.f1_gc(gc) == lvl


@pytest.mark.parametrize("end5, lvl", [
    ("AAGCA", 5),    # 2 G/C
    ("GAGCA", 4),    # 3 G/C, last 3 not all G/C
    ("AAGGC", 2),    # 3 G/C but last 3 all G/C
    ("AAACA", 3),    # 1 G/C
    ("GCGCA", 2),    # 4 G/C
    ("AAAAA", 1),    # 0
    ("GCGCG", 1),    # 5
])
def test_f2_gc_clamp(end5, lvl):
    assert ts.f2_gc_clamp("TTTTTTTT" + end5) == lvl


@pytest.mark.parametrize("L, lvl", [(17, 5), (16, 5), (15, 4), (14, 3), (13, 2), (12, 1), (11, 1)])
def test_f3_length(L, lvl):
    assert ts.f3_specific_length(L) == lvl


@pytest.mark.parametrize("dev, lvl", [(0, 5), (2, 5), (2.1, 4), (4, 4), (4.1, 3), (6, 3), (6.1, 2), (8, 2), (8.1, 1)])
def test_f4_binding_tm(dev, lvl):
    assert ts.f4_binding_tm(45.0 + dev) == lvl
    assert ts.f4_binding_tm(45.0 - dev) == lvl


@pytest.mark.parametrize("tm, lvl", [(29.9, 5), (30, 4), (36.9, 4), (37, 3), (41.9, 3), (42, 2), (46.9, 2), (47, 1)])
def test_f5_tm_sub_indices(tm, lvl):
    assert ts.f5_structure(tm, None, None)["sub_scores"]["hairpin_tm"] == lvl
    assert ts.f5_structure(None, None, tm)["sub_scores"]["end_dimer_tm"] == lvl


@pytest.mark.parametrize("dg, lvl", [(-4.9, 5), (-5.0, 4), (-6.9, 4), (-7.0, 3), (-8.9, 3), (-9.0, 2), (-9.9, 2), (-10.0, 1)])
def test_f5_dimer_dg(dg, lvl):
    assert ts.f5_structure(None, dg, None)["sub_scores"]["dimer_dg"] == lvl


def test_f5_is_minimum_and_veto():
    r = ts.f5_structure(20.0, -6.0, 50.0)
    assert r["score"] == 1 and r["veto"] is True
    r = ts.f5_structure(20.0, -6.0, 40.0)
    assert r["score"] == 3 and r["veto"] is False


def test_piecewise_interpolates_and_clamps():
    anchors = ((0.0, 0.0), (10.0, 100.0))
    assert ts.piecewise(5.0, anchors) == 50.0
    assert ts.piecewise(-1.0, anchors) == 0.0
    assert ts.piecewise(99.0, anchors) == 100.0


def _m(seq="ACGTACGTAGCTTATCAGAC", **kw):
    base = dict(sequence=seq, specific_length=15, tm_full=60.0, tm_binding=45.0, tm_reverse=60.0,
                ta=60.0, gc_percent=50.0, blast_risk="SAFE", blast_medium_hits=0,
                min_delta_cq=None, tm_margin=None, hairpin_tm=None, dimer_dg=-3.0,
                end_dimer_tm=None,
                v4_scores=dict(tm_accuracy=100, tm_binding_accuracy=100, gc_content=100,
                               gc_clamp=100, primer_size=100, amplicon_size=100))
    base.update(kw)
    return base


def test_specificity_beats_pcr():
    a = _m(seq="AAAA", min_delta_cq=None, tm_full=63.0)          # S 15, P low
    b = _m(seq="CCCC", min_delta_cq=8.0, tm_margin=12.0)          # S 13, P 10
    ra, rb = ts.score(a), ts.score(b)
    assert ra["specificity"]["total"] == 15 and rb["specificity"]["total"] == 13
    assert ra["pcr"]["total"] < rb["pcr"]["total"]
    out = ts.rank([(b, rb), (a, ra)])["ranked"]
    assert out[0][0]["sequence"] == "AAAA"


def test_veto_only_within_same_specificity():
    clean = _m(seq="AAAA", tm_full=63.0)
    veto = _m(seq="CCCC", hairpin_tm=50.0)
    rc, rv = ts.score(clean), ts.score(veto)
    assert rv["structure_veto"] and rc["specificity"]["total"] == rv["specificity"]["total"]
    assert ts.rank([(veto, rv), (clean, rc)])["ranked"][0][0]["sequence"] == "AAAA"
    weaker = _m(seq="GGGG", min_delta_cq=8.0)                       # lower S, no veto
    rw = ts.score(weaker)
    assert ts.rank([(weaker, rw), (veto, rv)])["ranked"][0][0]["sequence"] == "CCCC"


def test_elimination_and_fallback():
    bad = _m(seq="AAAA", blast_risk="CRITICAL")
    coamp = _m(seq="CCCC", min_delta_cq=1.0)
    ok = _m(seq="GGGG")
    out = ts.rank([(m, ts.score(m)) for m in (bad, coamp, ok)])
    assert [c[0]["sequence"] for c in out["ranked"]] == ["GGGG"]
    assert out["eliminated"] == 2 and not out["specificity_fallback"]
    out = ts.rank([(m, ts.score(m)) for m in (bad, coamp)])
    assert out["specificity_fallback"] and len(out["ranked"]) == 2


def test_no_blast_counts_two_criteria():
    r = ts.score(_m(blast_risk=None))
    assert r["specificity"]["blast"] is None and r["specificity"]["max"] == 10


def test_ties_fall_to_detail_then_tm_then_sequence():
    a = _m(seq="TTTT")
    b = _m(seq="AAAA")
    ra, rb = ts.score(a), ts.score(b)
    assert ts.rank([(a, ra), (b, rb)])["ranked"][0][0]["sequence"] == "AAAA"
    c = _m(seq="ZZZZ", v4_scores=dict(tm_accuracy=100, tm_binding_accuracy=100, gc_content=100,
                                      gc_clamp=100, primer_size=100, amplicon_size=0))
    rc = ts.score(c)
    assert rc["detailed_score"] < ra["detailed_score"]
    assert ts.rank([(c, rc), (a, ra)])["ranked"][0][0]["sequence"] == "TTTT"


def test_pcr_tier_is_p2_only_and_p1_is_reported():
    r = ts.score(_m(tm_full=60.0, tm_reverse=62.9))
    assert r["pcr"]["total"] == r["pcr"]["tm_vs_ta"] == 5 and r["pcr"]["max"] == 5
    assert r["pcr"]["tm_pair_report_only"] == 3


def test_tie_on_tiers_and_detail_falls_to_tm_then_sequence():
    """Same S/P/F totals and detailed score (V4 sub-scores fixed by _m): |Tm − Ta|
    decides, then the sequence (QD 27: arbitrary but deterministic)."""
    near = _m(seq="TTTT", tm_full=60.2)
    far = _m(seq="AAAA", tm_full=60.6)              # both P2 level 5
    rn, rf = ts.score(near), ts.score(far)
    assert rn["detailed_score"] == rf["detailed_score"]
    assert ts.rank([(far, rf), (near, rn)])["ranked"][0][0]["sequence"] == "TTTT"
    same = _m(seq="AAAA", tm_full=60.2)
    assert ts.rank([(near, rn), (same, ts.score(same))])["ranked"][0][0]["sequence"] == "AAAA"


# ── QD 29: one-sided F4 floor, F3 report-only (behind TIERED_F4_FLOOR) ──

@pytest.mark.parametrize("tm, lvl", [(60.0, 5), (45.0, 5), (44.9, 4), (43.0, 4), (42.9, 3),
                                     (41.0, 3), (40.9, 2), (39.0, 2), (38.9, 1), (30.0, 1)])
def test_f4_floor_levels(tm, lvl):
    assert ts.f4_binding_tm_floor(tm) == lvl


def test_floor_drops_f3_from_the_flexible_tier():
    m = _m(specific_length=12, tm_binding=50.0)
    old, new = ts.score(m, f4_floor=False), ts.score(m, f4_floor=True)
    assert old["flexible"]["max"] == 25 and "specific_length" in old["flexible"]
    assert old["flexible"]["binding_tm"] == 3              # |50 − 45| = 5 → two-sided level 3
    assert new["flexible"]["max"] == 20 and "specific_length" not in new["flexible"]
    assert new["flexible"]["specific_length_report_only"] == 1
    assert new["flexible"]["binding_tm"] == 5              # above the floor
    assert new["flexible"]["total"] == old["flexible"]["total"] - 1 + 5 - 3


def test_floor_detailed_score_is_one_sided_without_primer_size():
    hi, at, lo, low = (_m(tm_binding=t) for t in (55.0, 45.0, 40.0, 30.0))
    p = [ts.detailed_parts(x, f4_floor=True)["tm_binding_accuracy"] for x in (hi, at, lo, low)]
    assert p == [100.0, 100.0, 75.0, 25.0]                 # QD 33: 0 at 25 °C, 100 at 45 °C
    assert "primer_size" not in ts.detailed_parts(hi, f4_floor=True)
    w = ts.detailed_weights(f4_floor=True)
    assert "primer_size" not in w and abs(sum(w.values()) - 1) < 0.01
    assert "primer_size" in ts.detailed_weights(f4_floor=False)


def test_flag_default_reads_the_constant(monkeypatch):
    from algorithm import constants as K
    m = _m(tm_binding=50.0)
    monkeypatch.setattr(K, "TIERED_F4_FLOOR", True)
    assert ts.score(m)["flexible"]["max"] == 20
    monkeypatch.setattr(K, "TIERED_F4_FLOOR", False)
    assert ts.score(m)["flexible"]["max"] == 25


# ── QD 30: grade by tiers ────────────────────────────────────────

def _graded(fallback=False, **kw):
    return ts.grade_tiers(ts.score(_m(**kw)), fallback)


def test_grade_a_needs_every_specificity_level_and_no_veto():
    g = _graded(min_delta_cq=4.3, tm_margin=10.0)          # S1 5, S2 3, S3 4
    assert g == {"grade": "A", "reasons": []}


@pytest.mark.parametrize("kw, reason", [
    (dict(blast_risk="MEDIUM", blast_medium_hits=2), "S1 BLAST level 3"),
    (dict(blast_risk="HIGH"), "S1 BLAST level 2"),
    (dict(min_delta_cq=3.5), "S2 assay ΔCq level 2"),
    (dict(tm_margin=9.0), "S3 Tm margin level 3"),
    (dict(hairpin_tm=50.0), "structure veto"),
    (dict(blast_risk=None), "BLAST unavailable"),
])
def test_grade_b_names_the_weakness(kw, reason):
    g = _graded(**kw)
    assert g["grade"] == "B" and any(r.startswith(reason) for r in g["reasons"]), g


def test_grade_a_allows_medium_with_one_hit():
    assert _graded(blast_risk="MEDIUM", blast_medium_hits=1)["grade"] == "A"


def test_grade_c_is_the_fallback_whatever_the_levels():
    assert _graded(fallback=True)["grade"] == "C"
    assert _graded(fallback=True, blast_risk="CRITICAL")["grade"] == "C"



# ── QD 34: V4-compliant first, only within the same S total and veto ──

def test_v4_compliant_first_only_within_same_specificity():
    # same last 5 nt (same F2) so only the V4 step and the sequence differ
    bad = _m(seq="ATTTAAGCA", v4_violation=True)                  # better sequence, breaks a V4 rule
    ok = _m(seq="CTTTAAGCA", v4_violation=False)
    rb, ro = ts.score(bad), ts.score(ok)
    assert ts.rank([(bad, rb), (ok, ro)], v4_compliant_first=True)["ranked"][0][0]["sequence"] == "CTTTAAGCA"
    assert ts.rank([(bad, rb), (ok, ro)], v4_compliant_first=False)["ranked"][0][0]["sequence"] == "ATTTAAGCA"
    better_s = _m(seq="GTTTAAGCA", v4_violation=True)              # S 15 vs ok's S 13
    weaker = _m(seq="TTTTAAGCA", v4_violation=False, min_delta_cq=8.0)
    out = ts.rank([(weaker, ts.score(weaker)), (better_s, ts.score(better_s))], v4_compliant_first=True)
    assert out["ranked"][0][0]["sequence"] == "GTTTAAGCA"
    vetoed = _m(seq="AATTAAGCA", v4_violation=False, hairpin_tm=50.0)   # veto comes before the V4 step
    out = ts.rank([(vetoed, ts.score(vetoed)), (bad, rb)], v4_compliant_first=True)
    assert out["ranked"][0][0]["sequence"] == "ATTTAAGCA"



# ── QD 36: binding-Tm floor veto ──────────────────────────────────

def _r(m, **kw):
    return ts.score(m, f4_floor=True)


def test_binding_floor_fail_is_f4_level_1_with_the_floor_only():
    low = _m(tm_binding=38.9)
    assert ts.score(low, f4_floor=True)["binding_floor_fail"] is True
    assert ts.score(_m(tm_binding=39.0), f4_floor=True)["binding_floor_fail"] is False
    assert ts.score(low, f4_floor=False)["binding_floor_fail"] is False


def test_floor_veto_after_structure_veto_before_v4_step_same_s_only():
    tail = "TTTAAGCA"                       # same last 5 nt → same F2
    low = _m(seq="A" + tail, tm_binding=35.0)                       # floor fail, best sequence
    ok = _m(seq="C" + tail, tm_binding=46.0, v4_violation=True)    # above floor, breaks a V4 rule
    rl, ro = _r(low), _r(ok)
    key = dict(v4_compliant_first=True, binding_floor_veto=True)
    # before the V4 step: the V4-breaking candidate above the floor wins
    assert ts.rank([(low, rl), (ok, ro)], **key)["ranked"][0][0]["sequence"] == "C" + tail
    assert ts.rank([(low, rl), (ok, ro)], v4_compliant_first=True,
                   binding_floor_veto=False)["ranked"][0][0]["sequence"] == "A" + tail
    # after the structure veto: a structure-vetoed candidate above the floor loses
    hp = _m(seq="G" + tail, tm_binding=46.0, hairpin_tm=50.0)
    assert ts.rank([(hp, _r(hp)), (low, rl)], **key)["ranked"][0][0]["sequence"] == "A" + tail
    # only within the same S total: a higher-S candidate below the floor still wins
    weaker = _m(seq="T" + tail, tm_binding=46.0, min_delta_cq=8.0)
    assert ts.rank([(weaker, _r(weaker)), (low, rl)], **key)["ranked"][0][0]["sequence"] == "A" + tail


def test_grade_b_reason_binding_floor():
    g = ts.grade_tiers(_r(_m(tm_binding=35.0)), False)
    assert g["grade"] == "B" and any(x.startswith("binding Tm below") for x in g["reasons"])
