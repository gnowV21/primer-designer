# ================================================================
# tests/test_specificity_v5.py — review items 3/4/6/8/10 (2026-10-29)
#
# BLAST classifier v5: seed-family hits are flagged, not exempted; identical-
# sequence hits are split into identical / 5' isomiR / 3' isomiR; a forward
# primer that does not match the target skips the Tm gate; conditions and
# species are validated. Scoring: tm_accuracy targets the user's Ta.
# isomiR flag: biofluid note.
# ================================================================

import pytest

from algorithm.specificity_check import blast_offtarget as bo

_TARGET = "TAGCTTATCAGACTGATGTTGA"           # hsa-miR-21-5p
_PRIMER = "CGCTGCTCTAGCTTATCAGACTG"


def _hit(sid, aligned="TAGCTTATCAGACTG"):
    return {"subject_id": sid, "identity_pct": 100.0, "length": len(aligned),
            "mismatches": 0, "gap_opens": 0, "q_start": 9, "q_end": 23,
            "s_start": 1, "s_end": len(aligned), "evalue": 1.0, "bitscore": 30.0,
            "subject_seq": aligned, "query_seq": aligned}


def test_seed_family_hits_are_flagged_not_folded(monkeypatch):
    other = "TAGCTTATCAGACTGAAGCCCC"             # forward region identical
    monkeypatch.setattr(bo, "run_blastn", lambda *a, **k: [_hit("hsa-miR-x")])
    monkeypatch.setattr(bo, "fetch_sequences", lambda ids, *a, **k: {"hsa-miR-x": other})
    p3 = bo.resolve_p3_conditions(None)
    hits, safe, _, fam, _ = bo._check_primer(
        _PRIMER, [bo._MIRBASE_DB], "hsa-miR-21-5p", bo._normalize_mirna_name("hsa-miR-21-5p"),
        "hsa-", 60, "FAKE_FAMILY", tm_on=bo.duplex_tm(_PRIMER, _TARGET, p3), p3=p3,
        target_sequence=_TARGET)
    monkeypatch.setattr(bo, "get_family_id", lambda name: "FAKE_FAMILY")
    hits, safe, _, fam, _ = bo._check_primer(
        _PRIMER, [bo._MIRBASE_DB], "hsa-miR-21-5p", bo._normalize_mirna_name("hsa-miR-21-5p"),
        "hsa-", 60, "FAKE_FAMILY", tm_on=bo.duplex_tm(_PRIMER, _TARGET, p3), p3=p3,
        target_sequence=_TARGET)
    assert fam == 1
    assert len(hits) == 1 and hits[0]["same_seed_family"] is True
    assert bo._summarise(hits, safe, 0, fam, 0)["overall_risk"] != "SAFE"


def test_primer_matches_target():
    assert bo.primer_matches_target(_PRIMER, _TARGET)
    assert not bo.primer_matches_target("CGCTGCTCCAACACCAGTCGATG", _TARGET)   # other arm


@pytest.mark.parametrize("bad", [{"mv_conc": 0}, {"dna_conc": -5}, {"dv_conc": float("nan")},
                                 {"dntp_conc": float("inf")}])
def test_conditions_are_validated(bad):
    with pytest.raises(ValueError):
        bo.resolve_p3_conditions(bad)


def test_zero_mg_and_dntp_are_allowed():
    p3 = bo.resolve_p3_conditions({"dv_conc": 0, "dntp_conc": 0})
    assert p3["dv_conc"] == 0 and p3["dntp_conc"] == 0


@pytest.fixture
def client():
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_route_rejects_bad_conditions_and_species(client):
    r = client.post("/api/blast-check", json={"forward_primer": _PRIMER,
                                              "conditions": {"mv_conc": 0}})
    assert r.status_code == 400
    r = client.post("/api/blast-check", json={"forward_primer": _PRIMER, "species": "human"})
    assert r.status_code == 400


def test_route_passes_species_and_skips_tm_gate_on_mismatch(client, monkeypatch):
    seen = {}

    def fake_check(**kw):
        seen.update(kw)
        return {"summary": {"overall_risk": "SAFE"}, "forward_primer_hits": []}
    import routes.blast_check as rb
    monkeypatch.setattr(rb, "check_offtarget", fake_check)
    monkeypatch.setattr(rb._cache, "get_result", lambda *a, **k: None)
    monkeypatch.setattr(rb._cache, "set_result", lambda *a, **k: None)
    r = client.post("/api/blast-check", json={"forward_primer": _PRIMER, "species": "MMU",
                                              "mirna_sequence": _TARGET})
    assert r.status_code == 200
    assert seen["species"] == "mmu"


def test_check_offtarget_skips_tm_gate_when_primer_is_not_the_targets(monkeypatch):
    monkeypatch.setattr(bo, "_db_exists", lambda p: True)
    monkeypatch.setattr(bo, "run_blastn", lambda *a, **k: [])
    r = bo.check_offtarget("CGCTGCTCCAACACCAGTCGATG", None, "hsa-miR-21-5p",
                           target_sequence=_TARGET)
    assert r["classification"]["tm_gate_applied"] is False
    assert "does not end with" in r["classification"]["tm_gate_note"]


def test_identical_hits_are_split_by_variant(monkeypatch):
    seqs = {"hsa-miR-copy": _TARGET, "hsa-miR-short3": _TARGET[:-1], "hsa-miR-shift5": _TARGET[1:]}
    monkeypatch.setattr(bo, "_db_exists", lambda p: True)
    monkeypatch.setattr(bo, "run_blastn", lambda *a, **k: [_hit(s) for s in seqs])
    monkeypatch.setattr(bo, "fetch_sequences",
                        lambda ids, *a, **k: {i: seqs[i] for i in ids if i in seqs})
    r = bo.check_offtarget(_PRIMER, None, "hsa-miR-21-5p", target_sequence=_TARGET)
    assert r["identical_sequence_variants"] == {
        "hsa-miR-copy": "identical", "hsa-miR-short3": "isomir_3p", "hsa-miR-shift5": "isomir_5p"}


# ── item 6: tm_accuracy targets the user's Ta ────────────────────

def test_tm_accuracy_uses_annealing_temp():
    from algorithm.scoring import score_candidate
    from tests.test_dimer_full_dg import _build_forward, SEQ, SL, REV
    fwd = _build_forward(SEQ, -2.0, -2.0)
    fwd["tm_full"] = 57.0
    at57 = score_candidate(fwd, SL, REV, {"annealingTemp": 57}, use_v4=False)["scores"]["tm_accuracy"]
    at60 = score_candidate(fwd, SL, REV, {}, use_v4=False)["scores"]["tm_accuracy"]
    assert at57 == 100 and at60 < 100


# ── item 10: biofluid note on the 3' isomiR flag ─────────────────

def test_biofluid_note_only_for_biofluids():
    from algorithm.specificity_check.isomir_flag import check_3prime_isomir_flag
    assert check_3prime_isomir_flag("hsa-miR-221-3p", 6, "tissue")["sample_type_note"] is None
    note = check_3prime_isomir_flag("hsa-miR-221-3p", 6, "plasma")["sample_type_note"]
    assert "serum + plasma" in note and "42,494" in note
