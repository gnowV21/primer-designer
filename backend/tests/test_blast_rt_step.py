# ================================================================
# tests/test_blast_rt_step.py — BLAST classifier v7 (A3/A4 re-audit, 2026-11-10)
#
# A4: a forward-primer hit only produces signal if the RT overhang first makes
#     that miRNA's cDNA — with the design's RT primer, each plus-strand hit is
#     graded by the RT step of the assay model (apply_rt_step).
# A3: a same-molecule entry with a shifted end is a different molecule the assay
#     cannot fully separate — it must not leave overall_risk at SAFE.
# ================================================================

import pytest

from algorithm.constants import STEMLOOP_BODY
from algorithm.specificity_check import blast_offtarget as bo
from algorithm.specificity_check.assay_model import rt_axis

_LET7A = "TGAGGTAGTAGGTTGTATAGTT"            # hsa-let-7a-5p
_LET7C = "TGAGGTAGTAGGTTGTATGGTT"            # rG·dT at RT position 3 → ΔCq_RT 4.75
_LET7B = "TGAGGTAGTAGGTTGTGTGGTT"            # 2 overhang mismatches → ΔCq_RT 8
_LET7D = "AGAGGTAGTAGGTTGCATAGTT"            # same 3' 6 nt → ΔCq_RT 0
_FAR_MM = "TGAGGTAGTAGGTTGTATAGCT"           # 1 mismatch at RT position 5 → ΔCq_RT 3.5
_REGION = "TGAGGTAGTAGGTT"                   # 14-nt specific region
_PRIMER = "CGCAGC" + _REGION
_RT = STEMLOOP_BODY + "AACTAT"               # overhang = revcomp(ATAGTT)


def _hit(sid, aligned=_REGION):
    return {"subject_id": sid, "identity_pct": 100.0, "length": len(aligned),
            "mismatches": 0, "gap_opens": 0, "q_start": 7, "q_end": len(_PRIMER),
            "s_start": 1, "s_end": len(aligned), "evalue": 1.0, "bitscore": 30.0,
            "subject_seq": aligned, "query_seq": aligned}


@pytest.fixture
def blast(monkeypatch):
    """BLAST returns one plus-strand hit per off-target, each matching the region."""
    def install(seqs):
        monkeypatch.setattr(bo, "_db_exists", lambda p: True)
        monkeypatch.setattr(bo, "run_blastn", lambda *a, **k: [_hit(s) for s in seqs])
        monkeypatch.setattr(bo, "fetch_sequences",
                            lambda ids, *a, **k: {i: seqs[i] for i in ids if i in seqs})
    return install


# ── overhang length is read from the RT primer ────────────────────

@pytest.mark.parametrize("n", [5, 6, 7])
def test_overhang_len_from_rt_primer(n):
    assert bo.overhang_len_from_rt_primer(STEMLOOP_BODY + "A" * n) == n


@pytest.mark.parametrize("bad", [STEMLOOP_BODY + "A" * 4, STEMLOOP_BODY + "A" * 8,
                                 "A" * 50])
def test_overhang_len_rejects_bad_rt_primer(bad):
    with pytest.raises(ValueError):
        bo.overhang_len_from_rt_primer(bad)


# ── apply_rt_step thresholds ──────────────────────────────────────

def test_rt_step_thresholds():
    assert bo.apply_rt_step("CRITICAL", "r", rt_axis(_LET7A, _LET7C, 6))[0] == "SAFE"
    assert bo.apply_rt_step("CRITICAL", "r", rt_axis(_LET7A, _FAR_MM, 6))[0] == "MEDIUM"
    assert bo.apply_rt_step("CRITICAL", "r", rt_axis(_LET7A, _LET7D, 6))[0] == "CRITICAL"
    # never raises a lower forward-primer class
    assert bo.apply_rt_step("MEDIUM", "r", rt_axis(_LET7A, _FAR_MM, 6))[0] == "MEDIUM"


# ── A4: the RT step at work in check_offtarget ────────────────────

def test_rt_step_demotes_hits_the_overhang_rules_out(blast):
    blast({"hsa-let-7b-5p": _LET7B, "hsa-let-7c-5p": _LET7C, "hsa-let-7d-5p": _LET7D,
           "hsa-miR-far": _FAR_MM})
    without = bo.check_offtarget(_PRIMER, None, "hsa-let-7a-5p", target_sequence=_LET7A)
    with_rt = bo.check_offtarget(_PRIMER, None, "hsa-let-7a-5p", target_sequence=_LET7A,
                                 rt_primer=_RT)

    # Forward-primer-only: all four anneal as well as the target.
    assert {h["subject_id"] for h in without["forward_primer_hits"]} == {
        "hsa-let-7b-5p", "hsa-let-7c-5p", "hsa-let-7d-5p", "hsa-miR-far"}
    assert without["classification"]["rt_step_applied"] is False

    risk = {h["subject_id"]: h["risk"] for h in with_rt["forward_primer_hits"]}
    assert risk == {"hsa-let-7d-5p": "CRITICAL",    # same overhang: co-amplified
                    "hsa-miR-far": "MEDIUM"}        # partly reverse-transcribed
    assert with_rt["summary"]["rt_discriminated_count"] == 2   # let-7b, let-7c
    assert with_rt["classification"]["rt_step_applied"] is True
    assert with_rt["classification"]["rt_overhang_len"] == 6
    d = next(h for h in with_rt["forward_primer_hits"] if h["subject_id"] == "hsa-let-7d-5p")
    assert d["primer_risk"] == "CRITICAL" and d["rt_step"]["delta_cq"] == 0.0


def test_rt_step_needs_target_sequence(blast, monkeypatch):
    blast({"hsa-let-7c-5p": _LET7C})
    monkeypatch.setattr(bo, "fetch_sequences", lambda ids, *a, **k: {})
    r = bo.check_offtarget(_PRIMER, None, "hsa-let-7a-5p", rt_primer=_RT)
    assert r["classification"]["rt_step_applied"] is False


# ── A3: shifted same-molecule entries are never SAFE ──────────────

def test_shifted_5p_entry_raises_overall_risk(blast):
    blast({"hsa-miR-shift5": _LET7A[1:]})
    r = bo.check_offtarget(_PRIMER, None, "hsa-let-7a-5p", target_sequence=_LET7A,
                           rt_primer=_RT)
    assert r["identical_sequence_variants"] == {"hsa-miR-shift5": "shifted_5p"}
    assert r["identical_sequence_risk"]["hsa-miR-shift5"]["risk"] == "HIGH"
    assert r["summary"]["overall_risk"] == "HIGH"
    assert r["summary"]["unresolvable_variant_count"] == 1


def test_shifted_3p_entry_is_graded_by_rt_step(blast):
    blast({"hsa-miR-short3": _LET7A[:-1]})       # 1 nt shorter: ΔCq_RT 0 → HIGH
    r = bo.check_offtarget(_PRIMER, None, "hsa-let-7a-5p", target_sequence=_LET7A,
                           rt_primer=_RT)
    v = r["identical_sequence_risk"]["hsa-miR-short3"]
    assert v["category"] == "shifted_3p" and v["rt_delta_cq"] == 0.0 and v["risk"] == "HIGH"


def test_same_sequence_entry_stays_out_of_the_risk(blast):
    blast({"hsa-miR-copy": _LET7A})
    r = bo.check_offtarget(_PRIMER, None, "hsa-let-7a-5p", target_sequence=_LET7A,
                           rt_primer=_RT)
    assert r["summary"]["overall_risk"] == "SAFE"
    assert r["summary"]["unresolvable_variant_count"] == 0


def test_variant_risk_without_rt_step_is_conservative():
    assert bo.variant_risk("shifted_3p", None) == "HIGH"
    assert bo.variant_risk("same_sequence", None) == "SAFE"


# ── route ─────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_route_validates_and_forwards_rt_primer(client, monkeypatch):
    r = client.post("/api/blast-check", json={"forward_primer": _PRIMER,
                                              "rt_primer": STEMLOOP_BODY + "AC"})
    assert r.status_code == 400

    seen = {}

    def fake_check(**kw):
        seen.update(kw)
        return {"summary": {"overall_risk": "SAFE"}, "forward_primer_hits": []}
    import routes.blast_check as rb
    monkeypatch.setattr(rb, "check_offtarget", fake_check)
    monkeypatch.setattr(rb._cache, "get_result", lambda *a, **k: None)
    monkeypatch.setattr(rb._cache, "set_result", lambda *a, **k: None)
    r = client.post("/api/blast-check", json={"forward_primer": _PRIMER,
                                              "rt_primer": _RT.lower()})
    assert r.status_code == 200
    assert seen["rt_primer"] == _RT
