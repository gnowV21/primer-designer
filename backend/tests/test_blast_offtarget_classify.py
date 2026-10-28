"""
Unit tests for the BLAST off-target risk classifier (blast_offtarget.classify_hit_risk).

These lock in the two fixes that collapsed the "hundreds of CRITICAL hits" problem:

  A. 3'-anchoring — off-target priming requires the primer's 3' terminus to anneal.
     BLAST reports only the local alignment, so the number of primer 3' nt left
     OUTSIDE the alignment ('three_prime_dangling') decides whether the 3' end can
     prime. A dangling 3' end, or a 3'-anchored match too short to reach the
     annealing temperature, cannot seed extension → SAFE.

  (Fix B — folding same-seed-family hits into one bucket — is exercised via
  get_family_id below; the full fold needs a live blastn run.)

classify_hit_risk is a pure function over an alignment dict, so these tests need
no blastn binary or database.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.specificity_check.blast_offtarget import classify_hit_risk
from algorithm.specificity_check.family_crossreactivity import get_family_id
from algorithm.constants import (
    BLAST_3PRIME_DANGLE_SAFE,
    PRIMER_BLAST_MIN_3PRIME_ANCHOR,
)

_PRIMER = "GCCGCTGAGGTAGTAGGTTGTA"  # 22 nt (tail + specific region)


def _aln(*, mm, dangling, cols, p3="A", t3="T", mm_pos=None):
    """Build a minimal alignment dict shaped like nw_align's output.

    t3 is the TEMPLATE-strand base facing the primer 3' end (Kwok notation), so
    the default A/T is a Watson-Crick match.
    """
    return {
        "mismatches": mm,
        "mismatch_positions": mm_pos if mm_pos is not None else [],
        "primer_3prime_base": p3,
        "template_3prime_base": t3,
        "aln_cols": cols,
        "three_prime_dangling": dangling,
    }


# ── Fix A: 3'-anchoring gate ─────────────────────────────────────────

def test_three_prime_dangling_is_safe():
    """A primer whose 3' end lies outside the alignment cannot prime → SAFE."""
    risk, reason = classify_hit_risk(_PRIMER, _aln(mm=0, dangling=BLAST_3PRIME_DANGLE_SAFE, cols=14))
    assert risk == "SAFE"
    assert "3′ end" in reason or "does not anneal" in reason


def test_single_dangling_base_capped_at_medium():
    """A 1-nt 3' overhang / trimmed terminal mismatch reduces priming → MEDIUM, never CRITICAL."""
    risk, _ = classify_hit_risk(_PRIMER, _aln(mm=0, dangling=1, cols=15))
    assert risk == "MEDIUM"


def test_short_three_prime_anchor_is_safe():
    """A perfect but very short (<10 nt) 3'-anchored match has Tm << Ta → SAFE."""
    risk, reason = classify_hit_risk(
        _PRIMER, _aln(mm=0, dangling=0, cols=PRIMER_BLAST_MIN_3PRIME_ANCHOR - 2)
    )
    assert risk == "SAFE"
    assert "too" not in reason.lower() or "short" in reason.lower()


# ── Fix A: genuine 3'-anchored matches still surface ─────────────────

def test_full_3prime_match_zero_mismatch_is_critical():
    """3' terminus annealed, long anchor, 0 mismatches → genuine CRITICAL off-target."""
    risk, _ = classify_hit_risk(_PRIMER, _aln(mm=0, dangling=0, cols=17))
    assert risk == "CRITICAL"


def test_3prime_match_three_mismatches_is_high():
    risk, _ = classify_hit_risk(_PRIMER, _aln(mm=3, dangling=0, cols=17, mm_pos=[0, 1, 2]))
    assert risk == "HIGH"


def test_six_mismatches_is_safe():
    """Ye12 ignore threshold: ≥6 total mismatches → SAFE even when 3'-anchored."""
    risk, _ = classify_hit_risk(_PRIMER, _aln(mm=6, dangling=0, cols=17, mm_pos=list(range(6))))
    assert risk == "SAFE"


def test_blocking_terminal_is_safe():
    """A:G 3'-terminal is BLOCKING (~1% yield) → SAFE despite few mismatches."""
    risk, reason = classify_hit_risk(
        _PRIMER, _aln(mm=1, dangling=0, cols=15, p3="A", t3="G", mm_pos=[14])
    )
    assert risk == "SAFE"
    assert "BLOCKING" in reason


# ── Kwok90 orientation: primer base vs TEMPLATE-strand base ──────────

def test_kwok_categories_use_template_strand():
    from algorithm.specificity_check.blast_offtarget import classify_3prime_mismatch as k
    assert k("A", "T") == "MATCH"
    assert k("A", "G") == "BLOCKING"
    assert k("C", "C") == "BLOCKING"     # unreachable before: C==C was read as a match
    assert k("A", "A") == "REDUCING"
    assert k("A", "C") == "TOLERANT"


def test_nw_align_reports_template_strand_base():
    """Off-target sense ends in C opposite primer A → template G → Kwok A:G BLOCKING."""
    from algorithm.specificity_check.blast_offtarget import nw_align, classify_3prime_mismatch
    aln = nw_align("CTTATCAGACTA", "CTTATCAGACTC")
    assert aln["primer_3prime_base"] == "A"
    assert aln["template_3prime_base"] == "G"
    assert classify_3prime_mismatch("A", aln["template_3prime_base"]) == "BLOCKING"
    # A perfect sense match is a Watson-Crick pair on the template strand.
    same = nw_align("CTTATCAGACTG", "CTTATCAGACTG")
    assert classify_3prime_mismatch(same["primer_3prime_base"], same["template_3prime_base"]) == "MATCH"


# ── B3: duplex-Tm gate (relative to the on-target duplex Tm) ─────────

def _tm_aln(tm_off, tm_on=45.0, **kw):
    a = _aln(**{"mm": 0, "dangling": 0, "cols": 15, **kw})
    a["tm_offtarget"], a["tm_ontarget"] = tm_off, tm_on
    return a


def test_tm_far_below_target_is_safe_even_if_perfect_match():
    """>10 °C weaker than the target → SAFE, overriding the mismatch rules."""
    risk, reason = classify_hit_risk(_PRIMER, _tm_aln(34.9))
    assert risk == "SAFE"
    assert "on target" in reason


def test_tm_safe_boundary_is_exclusive():
    """Exactly Tm_on − 10 is NOT safe (rule is Tm_off < Tm_on − 10) → grey zone."""
    risk, _ = classify_hit_risk(_PRIMER, _tm_aln(35.0))
    assert risk == "MEDIUM"


def test_grey_zone_caps_at_medium():
    """Ye/Kwok would say CRITICAL (0 mm, 3' match) but the Tm gap caps it at MEDIUM."""
    risk, reason = classify_hit_risk(_PRIMER, _tm_aln(38.0))
    assert risk == "MEDIUM"
    assert "capped at MEDIUM" in reason


def test_grey_zone_keeps_safe_from_mismatch_rules():
    """The cap only lowers: a BLOCKING terminal stays SAFE in the grey zone."""
    risk, _ = classify_hit_risk(_PRIMER, _tm_aln(38.0, mm=1, p3="A", t3="G", mm_pos=[14]))
    assert risk == "SAFE"


def test_within_critical_margin_is_critical():
    """Tm_off ≥ Tm_on − 5 with the 3' end annealed → CRITICAL."""
    risk, _ = classify_hit_risk(_PRIMER, _tm_aln(40.0))
    assert risk == "CRITICAL"


def test_offtarget_stronger_than_target_is_critical():
    risk, reason = classify_hit_risk(_PRIMER, _tm_aln(48.0))
    assert risk == "CRITICAL"
    assert "above" in reason


def test_top_tier_blocking_terminal_is_high():
    """Stable duplex but BLOCKING 3' mismatch (Kwok90 ~1% yield) → HIGH, not CRITICAL."""
    risk, reason = classify_hit_risk(_PRIMER, _tm_aln(44.0, mm=1, p3="C", t3="C", mm_pos=[14]))
    assert risk == "HIGH"
    assert "BLOCKING" in reason


def test_top_tier_unpaired_terminal_is_high():
    risk, _ = classify_hit_risk(_PRIMER, _tm_aln(44.0, dangling=1))
    assert risk == "HIGH"


def test_anchor_gate_runs_before_tm_gate():
    """A non-annealed 3' end is SAFE however stable the duplex (Tm can't see the 3' end)."""
    risk, _ = classify_hit_risk(_PRIMER, _tm_aln(50.0, dangling=BLAST_3PRIME_DANGLE_SAFE))
    assert risk == "SAFE"


def test_tm_gate_replaces_legacy_short_anchor_rule():
    """With Tm data, a short anchor is judged by its Tm, not by the 10-nt rule."""
    short = PRIMER_BLAST_MIN_3PRIME_ANCHOR - 2
    assert classify_hit_risk(_PRIMER, _tm_aln(43.0, cols=short))[0] == "CRITICAL"
    assert classify_hit_risk(_PRIMER, _aln(mm=0, dangling=0, cols=short))[0] == "SAFE"


def test_custom_margins():
    """Sensitivity analysis passes other margins; margin 5/5 has no grey zone."""
    assert classify_hit_risk(_PRIMER, _tm_aln(38.0), 5.0, 5.0)[0] == "SAFE"
    assert classify_hit_risk(_PRIMER, _tm_aln(38.0), 20.0, 5.0)[0] == "MEDIUM"


# ── (a) DB paths with spaces ─────────────────────────────────────────

def test_blast_db_located_via_blastdb_env_not_spaced_path():
    """-db must get only the DB name; the spaced directory goes in BLASTDB."""
    from algorithm.specificity_check.blast_offtarget import _blast_env_and_name
    env, name = _blast_env_and_name(os.path.join("C:\\", "Users", "TIEN VUONG", "db", "mirbase_multi"))
    assert name == "mirbase_multi"
    assert " " not in name
    assert env["BLASTDB"].endswith(os.path.join("TIEN VUONG", "db"))


def test_live_blast_runs_from_spaced_path():
    """Integration: the repo DB lives under 'TIEN VUONG' on the dev machine."""
    import shutil
    import pytest
    from algorithm.specificity_check import blast_offtarget as bo
    if not shutil.which("blastn") or not bo._db_exists(bo._MIRBASE_DB):
        pytest.skip("blastn or BLAST DB not available")
    hits = bo.run_blastn("CGCTGCTCTAGCTTATCAGACTG", bo._MIRBASE_DB)
    assert any(h["subject_id"] == "hsa-miR-21-5p" for h in hits)
    seqs = bo.fetch_sequences(["hsa-miR-21-5p", "not-a-real-id"], bo._MIRBASE_DB)
    assert seqs == {"hsa-miR-21-5p": "TAGCTTATCAGACTGATGTTGA"}


def test_universal_reverse_is_not_blasted():
    import shutil
    import pytest
    from algorithm.specificity_check import blast_offtarget as bo
    if not shutil.which("blastn") or not bo._db_exists(bo._MIRBASE_DB):
        pytest.skip("blastn or BLAST DB not available")
    r = bo.check_offtarget("CGCTGCTCTAGCTTATCAGACTG", "CCAGTGCAGGGTCCGAGGTA", "hsa-miR-21-5p")
    assert r["reverse_primer_hits"] == []
    assert r["reverse_primer_skipped"]
    assert r["classification"]["tm_gate_applied"] is True


# ── Classifier v3: self-hit by name + compatible sequence ────────────

def test_self_name_match_is_boundary_safe():
    """'ssc-miR-21' must not swallow 'ssc-miR-210' (old substring rule did)."""
    from algorithm.specificity_check.blast_offtarget import _is_self_hit
    assert not _is_self_hit("ssc-miR-210", "ssc-miR-21")
    assert not _is_self_hit("hsa-miR-10-5p", "hsa-miR-1")
    assert not _is_self_hit("hsa-miR-21-5px", "hsa-miR-21-5p")


def test_self_name_match_keeps_legit_variants():
    from algorithm.specificity_check.blast_offtarget import _is_self_hit
    assert _is_self_hit("hsa-miR-21-5p", "hsa-miR-21-5p")
    assert _is_self_hit("HSA-MIR-21-5P", "hsa-miR-21-5p")          # case
    assert _is_self_hit("hsa-miR-16-1-5p", "hsa-miR-16-5p")        # precursor copy
    assert _is_self_hit("hsa-miR-622", "hsa-miR-622-5p")           # arm-less DB name
    assert _is_self_hit("ssc-miR-21-5p", "ssc-miR-21")             # arm-less target id
    assert _is_self_hit("ssc-miR-21-3p", "ssc-miR-21")             # …names both arms


def test_sequences_compatible_end_shifts():
    from algorithm.specificity_check.blast_offtarget import sequences_compatible as ok
    # miRBase 22.1 vs Busk 2014 (real pairs)
    assert ok("AGCTGGTGTTGTGAATCAGGCCG", "CAGCTGGTGTTGTGAATCAGGCCG")      # 138-5p: 5' +1
    assert ok("TGCTATGCCAACATATTGCCATC", "CTGCTATGCCAACATATTGCCA")      # 31-3p: 5' 1, 3' 2
    assert ok("TAGCTTATCAGACTGATGTTGA", "TAGCTTATCAGACTGATGTTGA")       # identical
    assert not ok("TTTCCTCATATTCATTCAGGAGTG", "ATCCCTGAGTGTATGTGGTGAA")  # 670 renamed
    # 3-nt end shift is beyond the tolerance
    assert not ok("AAATAGCTTATCAGACTGATGTTGA", "TAGCTTATCAGACTGATGTTGA")
    # internal mismatch (paralogs such as miR-23a/b) is not an annotation shift
    assert not ok("ATCACATTGCCAGGGATTTCC", "ATCACATTGCCAGGGATTACC")


def _live_blast_or_skip():
    import shutil
    import pytest
    from algorithm.specificity_check import blast_offtarget as bo
    if not shutil.which("blastn") or not bo._db_exists(bo._MIRBASE_DB):
        pytest.skip("blastn or BLAST DB not available")
    return bo


def test_identical_sequence_copies_are_folded_not_critical():
    """ath-miR156a = 156b–f: listed as identical, never risk-classified."""
    bo = _live_blast_or_skip()
    r = bo.check_offtarget("GGCACTGCTGACAGAAGAGAG", "", "ath-miR156a-5p")
    assert "ath-miR156b-5p" in r["identical_sequence_hits"]
    assert all(h["subject_id"] not in r["identical_sequence_hits"] for h in r["forward_primer_hits"])
    assert r["summary"]["identical_sequence_count"] == len(r["identical_sequence_hits"])


def _fake_hit(sid, aligned="TAGCTTATCAGACTG"):
    # Primer = 8-nt tail + 15-nt specific region; the hit covers the specific region.
    return {"subject_id": sid, "identity_pct": 100.0, "length": len(aligned),
            "mismatches": 0, "gap_opens": 0, "q_start": 9, "q_end": 23,
            "s_start": 1, "s_end": len(aligned), "evalue": 1.0, "bitscore": 30.0,
            "subject_seq": aligned, "query_seq": aligned}


def test_self_and_identity_rules_with_arm_less_target(monkeypatch):
    """Target 'ssc-miR-21' (Busk 2014 naming), sequence known. Deterministic fakes:
    - ssc-miR-21-5p  same name, same sequence      → self (skipped)
    - ssc-miR-21-3p  same name, other sequence     → classified, not self
    - ssc-miR-210    old substring rule hid it     → classified, not self
    - ssc-miR-9999   other name, identical seq     → identical_sequence
    - hsa-miR-21-5p  other species                 → cross-species excluded
    """
    from algorithm.specificity_check import blast_offtarget as bo
    target = "TAGCTTATCAGACTGATGTTGA"
    seqs = {"ssc-miR-21-5p": target, "ssc-miR-21-3p": "CAACACCAGTCGATGGGCTGT",
            "ssc-miR-210": "CTGTGCGTGTGACAGCGGCTGA", "ssc-miR-9999": target}
    raw = [_fake_hit(s) for s in (*seqs, "hsa-miR-21-5p")]
    monkeypatch.setattr(bo, "run_blastn", lambda *a, **k: raw)
    monkeypatch.setattr(bo, "fetch_sequences",
                        lambda ids, *a, **k: {i: seqs[i] for i in ids if i in seqs})
    p3 = bo.resolve_p3_conditions(None)
    hits, safe, cross, fam, ident = bo._check_primer(
        "CGCTGCTCTAGCTTATCAGACTG", [bo._MIRBASE_DB], "ssc-miR-21",
        bo._normalize_mirna_name("ssc-miR-21"), "ssc-", 60,
        tm_on=bo.duplex_tm("CGCTGCTCTAGCTTATCAGACTG", target, p3), p3=p3,
        target_sequence=target)
    # 5 hits = 1 self + 2 classified + 1 identical + 1 cross-species
    assert len(hits) + safe == 2
    assert ident == ["ssc-miR-9999"]
    assert cross == 1


def test_renamed_entry_with_shifted_end_is_folded_as_identical(monkeypatch):
    """Busk 'ssc-miR-20' vs miRBase 22.1 'ssc-miR-20a-5p' (3' end 1 nt shorter):
    another name, same molecule → identical_sequence, not a CRITICAL off-target."""
    from algorithm.specificity_check import blast_offtarget as bo
    monkeypatch.setattr(bo, "run_blastn", lambda *a, **k: [_fake_hit("ssc-miR-20a-5p",
                                                                     "TAAAGTGCTTATAGTG")])
    monkeypatch.setattr(bo, "fetch_sequences",
                        lambda ids, *a, **k: {"ssc-miR-20a-5p": "TAAAGTGCTTATAGTGCAGGTA"})
    hits, safe, _, _, ident = bo._check_primer(
        "AGCCGGTGTAAAGTGCTTATAGTG", [bo._MIRBASE_DB], "ssc-miR-20",
        bo._normalize_mirna_name("ssc-miR-20"), "ssc-", 60,
        target_sequence="TAAAGTGCTTATAGTGCAGGTAG")
    assert ident == ["ssc-miR-20a-5p"]
    assert hits == [] and safe == 0


def test_renamed_entry_with_other_sequence_is_not_self(monkeypatch):
    """Same name but an unrelated sequence (miRBase 22.1 ssc-miR-670) is an off-target."""
    from algorithm.specificity_check import blast_offtarget as bo
    monkeypatch.setattr(bo, "run_blastn", lambda *a, **k: [_fake_hit("ssc-miR-670")])
    monkeypatch.setattr(bo, "fetch_sequences",
                        lambda ids, *a, **k: {"ssc-miR-670": "TTTCCTCATATTCATTCAGGAGTG"})
    hits, safe, *_ = bo._check_primer(
        "CGCTGCTCTAGCTTATCAGACTG", [bo._MIRBASE_DB], "ssc-miR-670",
        bo._normalize_mirna_name("ssc-miR-670"), "ssc-", 60,
        target_sequence="ATCCCTGAGTGTATGTGGTGAA")
    assert len(hits) + safe == 1          # classified, not skipped as self


def test_species_override():
    bo = _live_blast_or_skip()
    r = bo.check_offtarget("CGCTGCTCTAGCTTATCAGACTG", "", None,
                           target_sequence="UAGCUUAUCAGACUGAUGUUGA", species="mmu")
    assert r["classification"]["species"] == "mmu"
    import pytest
    with pytest.raises(ValueError):
        bo.check_offtarget("CGCTGCTCTAGCTTATCAGACTG", "", None, species="mouse")


# ── Fix B dependency: family lookup ──────────────────────────────────

def test_get_family_id_groups_let7_members():
    """let-7a-5p and let-7c-5p must resolve to the SAME seed-family id (folded together)."""
    fam_a = get_family_id("hsa-let-7a-5p")
    fam_c = get_family_id("hsa-let-7c-5p")
    assert fam_a is not None
    assert fam_a == fam_c


def test_get_family_id_unknown_returns_none():
    assert get_family_id("not-a-real-mirna-xyz") is None
