"""
test_blast_batch.py — batched BLAST (SPEC_scoring_tiered_4.0.0 QD 24b): one multi-FASTA
blastn (split over parallel processes) + one blastdbcmd per design must give exactly
what check_offtarget gives one primer at a time — every hit, every field, S1.

The full proof is benchmark/blast_batch_equivalence.json (31,049 calls of the
Giai đoạn 1 sample, scripts/blast_batch_equivalence.py); these tests keep it true.
"""
import json

import pytest

from algorithm.constants import UNIVERSAL_REVERSE
from algorithm.forward_primer import generate_forward_candidates
from algorithm.stemloop_rt import design_stemloop_rt
from algorithm.specificity_check import blast_offtarget as bo

live = pytest.mark.skipif(not bo.blast_available()[0], reason="BLAST+ or the miRBase DB missing")


def _pool(rna, name, n):
    cands, _ = generate_forward_candidates(rna, {}, gc_prefilter=False)
    # spread over the specific lengths: every 3' end, several tails
    picked = sorted(cands, key=lambda c: (c["specific_length"], c["sequence"]))[:: max(1, len(cands) // n)]
    return [c["sequence"] for c in picked][:n], design_stemloop_rt(rna, {}, mirna_name=name)["sequence"]


@live
@pytest.mark.parametrize("name, rna", [
    ("hsa-let-7a-5p", "UGAGGUAGUAGGUUGUAUAGUU"),      # family: HIGH/CRITICAL hits, variants
    ("hsa-miR-21-5p", "UAGCUUAUCAGACUGAUGUUGA"),
])
def test_batch_equals_one_primer_at_a_time(name, rna):
    seqs, rt = _pool(rna, name, 8)
    kw = dict(mirna_id=name, target_sequence=rna, species="hsa", rt_primer=rt)
    batch = bo.check_offtarget_batch(seqs + seqs[:2], UNIVERSAL_REVERSE, **kw)   # duplicates folded
    assert set(batch) == set(seqs)
    for s in seqs:
        single = bo.check_offtarget(s, UNIVERSAL_REVERSE, **kw)
        assert json.dumps(batch[s], sort_keys=True) == json.dumps(single, sort_keys=True), s


@live
def test_multi_query_split_does_not_change_hits():
    seqs, _ = _pool("UGAGGUAGUAGGUUGUAUAGUU", "hsa-let-7a-5p", 6)
    one = bo.run_blastn_multi(seqs, bo._MIRBASE_DB, processes=1)
    many = bo.run_blastn_multi(seqs, bo._MIRBASE_DB, processes=4)
    assert one == many
    for s in seqs[:3]:
        assert one[s] == bo.run_blastn(s, bo._MIRBASE_DB)


def test_empty_batch_and_missing_db(monkeypatch):
    assert bo.run_blastn_multi([], "x") == {}
    monkeypatch.setattr(bo, "_db_exists", lambda p: False)
    ok, why = bo.blast_available()
    assert not ok and ("database" in why.lower() or "binary" in why.lower())
    with pytest.raises(FileNotFoundError):
        bo.check_offtarget_batch(["ACGT"], UNIVERSAL_REVERSE, mirna_id="hsa-miR-1-3p")


def test_batch_classifies_with_the_shared_code(monkeypatch):
    """Stubbed blastn / blastdbcmd: the batch path feeds each primer's own hits to the
    same classifier as the single path (one blastn, one blastdbcmd call in total)."""
    target = "TAGCTTATCAGACTGATGTTGA"
    other = "TAGCTTATCAGACTGACGTTGA"        # 1 mismatch inside the 16-nt region
    p1 = "ACCGCCTAGCTTATCAGACTGA"
    p2 = "CTAGCCGTCCTATAGCTTATCAGACT"

    def hit(primer):
        L = len(target) - 6
        return {"subject_id": "hsa-miR-other", "identity_pct": 95.0, "length": L,
                "mismatches": 1, "gap_opens": 0, "q_start": len(primer) - L + 1,
                "q_end": len(primer), "s_start": 1, "s_end": L, "evalue": 1.0,
                "bitscore": 20.0, "subject_seq": other[:L], "query_seq": primer[-L:]}
    calls = {"multi": 0, "fetch": 0}

    def multi(primers, db, timeout=60, processes=None):
        calls["multi"] += 1
        return {p: [hit(p)] for p in primers}

    def fetch(ids, db, timeout=60):
        calls["fetch"] += 1
        return {i: other for i in ids if i == "hsa-miR-other"}
    monkeypatch.setattr(bo, "run_blastn_multi", multi)
    monkeypatch.setattr(bo, "fetch_sequences", fetch)
    monkeypatch.setattr(bo, "_db_exists", lambda p: True)
    out = bo.check_offtarget_batch([p1, p2], UNIVERSAL_REVERSE, mirna_id="hsa-miR-21-5p",
                                   target_sequence=target, species="hsa")
    assert calls == {"multi": 1, "fetch": 1}

    monkeypatch.setattr(bo, "run_blastn", lambda primer, db, timeout=60: [hit(primer)])
    for p in (p1, p2):
        single = bo.check_offtarget(p, UNIVERSAL_REVERSE, mirna_id="hsa-miR-21-5p",
                                    target_sequence=target, species="hsa")
        assert json.dumps(out[p], sort_keys=True) == json.dumps(single, sort_keys=True)
