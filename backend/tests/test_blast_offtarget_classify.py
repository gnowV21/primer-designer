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


def _aln(*, mm, dangling, cols, p3="A", t3="A", mm_pos=None):
    """Build a minimal alignment dict shaped like nw_align's output."""
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


# ── Fix B dependency: family lookup ──────────────────────────────────

def test_get_family_id_groups_let7_members():
    """let-7a-5p and let-7c-5p must resolve to the SAME seed-family id (folded together)."""
    fam_a = get_family_id("hsa-let-7a-5p")
    fam_c = get_family_id("hsa-let-7c-5p")
    assert fam_a is not None
    assert fam_a == fam_c


def test_get_family_id_unknown_returns_none():
    assert get_family_id("not-a-real-mirna-xyz") is None
