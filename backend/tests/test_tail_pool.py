# ================================================================
# tests/test_tail_pool.py — Unit tests for tail homopolymer filter (PROMPT 5)
# Verifies Busk 2014 (DOI 10.1186/1471-2105-15-29) tail quality:
# no run ≥ TAIL_MAX_HOMOPOLYMER_RUN consecutive identical bases.
# ================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.forward_primer import _generate_tail_pool, generate_forward_candidates
from algorithm.constants import TAIL_MAX_HOMOPOLYMER_RUN, FORWARD_TAIL_MIN, FORWARD_TAIL_MAX


# ── Constant sanity ───────────────────────────────────────────────

def test_constant_value():
    """TAIL_MAX_HOMOPOLYMER_RUN should be 3 per Busk14 (runs of 3+ rejected)."""
    assert TAIL_MAX_HOMOPOLYMER_RUN == 3


# ── No tail in pool has a run >= TAIL_MAX_HOMOPOLYMER_RUN ────────

def _has_run(tail, run_len):
    return any(b * run_len in tail for b in "ACGT")


def test_no_homopolymer_run_all_lengths():
    """All generated tails for every tail length must have no run ≥ TAIL_MAX_HOMOPOLYMER_RUN."""
    for tail_len in range(FORWARD_TAIL_MIN, FORWARD_TAIL_MAX + 1):
        pool = _generate_tail_pool(tail_len)
        for tail in pool:
            assert not _has_run(tail, TAIL_MAX_HOMOPOLYMER_RUN), (
                f"Tail '{tail}' (len={tail_len}) has a run of "
                f"{TAIL_MAX_HOMOPOLYMER_RUN}+ identical bases — violates Busk14 rule."
            )


def test_no_poly_ggg_in_pool():
    """Pool must not contain 'GGG' (poly-G run of 3, common Busk14 concern)."""
    for tail_len in range(3, FORWARD_TAIL_MAX + 1):
        pool = _generate_tail_pool(tail_len)
        for tail in pool:
            assert "GGG" not in tail, f"Tail '{tail}' contains 'GGG' — violates Busk14."


def test_no_poly_ccc_in_pool():
    """Pool must not contain 'CCC' (poly-C run of 3)."""
    for tail_len in range(3, FORWARD_TAIL_MAX + 1):
        pool = _generate_tail_pool(tail_len)
        for tail in pool:
            assert "CCC" not in tail, f"Tail '{tail}' contains 'CCC' — violates Busk14."


# ── Pool is not empty after filtering ────────────────────────────

def test_pool_not_empty_short_lengths():
    """Tail pool must have entries for lengths 3 through 6 (exhaustive enumeration)."""
    for tail_len in range(3, 7):
        pool = _generate_tail_pool(tail_len)
        assert len(pool) > 0, f"Tail pool is empty for tail_len={tail_len} after Busk14 filter."


def test_pool_not_empty_long_lengths():
    """Tail pool must have entries for lengths 7 through 12 (random sampling)."""
    for tail_len in range(7, FORWARD_TAIL_MAX + 1):
        pool = _generate_tail_pool(tail_len)
        assert len(pool) > 0, f"Tail pool is empty for tail_len={tail_len} after Busk14 filter."


def test_long_pool_is_diverse():
    """Sampling must yield a real pool, not one tail replayed."""
    for tail_len in range(7, FORWARD_TAIL_MAX + 1):
        pool = _generate_tail_pool(tail_len)
        assert len(pool) >= 100, f"Only {len(pool)} tails for tail_len={tail_len}."


# ── Determinism invariant ────────────────────────────────────────

def _fwd_seqs(seq):
    return [c["sequence"] for c in generate_forward_candidates(seq, {})[0]]


def test_same_mirna_twice_gives_same_primers():
    """Designing the same miRNA again, after other designs, must not change the result."""
    mir21, let7a = "UAGCUUAUCAGACUGAUGUUGA", "UGAGGUAGUAGGUUGUAUAGUU"
    first = _fwd_seqs(mir21)
    _fwd_seqs(let7a)
    assert _fwd_seqs(mir21) == first


def test_global_random_state_does_not_leak_in():
    """Output must not depend on the module-global `random` state."""
    import random
    seq = "UAGCUUAUCAGACUGAUGUUGA"
    random.seed(1)
    a = _fwd_seqs(seq)
    random.seed(12345)
    random.random()
    assert _fwd_seqs(seq) == a


def test_long_pool_reproducible():
    for tail_len in range(7, FORWARD_TAIL_MAX + 1):
        assert _generate_tail_pool(tail_len, sequence="ACGT") == _generate_tail_pool(tail_len, sequence="ACGT")


def test_pool_independent_of_other_pools():
    """Each pool seeds its own RNG: building other pools first must not change it."""
    alone = _generate_tail_pool(9, sequence="TAGCTTATCAGACTGATGTTGA")
    for tl in (7, 8, 10):
        _generate_tail_pool(tl, sequence="TAGCTTATCAGACTGATGTTGA")
    assert _generate_tail_pool(9, sequence="TAGCTTATCAGACTGATGTTGA") == alone


def test_pool_seed_comes_from_input():
    """Different inputs → different samples (seed is derived from the call's inputs)."""
    a = _generate_tail_pool(10, sequence="TAGCTTATCAGACTGATGTTGA")
    b = _generate_tail_pool(10, sequence="TGAGGTAGTAGGTTGTATAGTT")
    assert a != b


# ── Pool is GC-rich (≥50% GC) ────────────────────────────────────

def test_all_tails_gc_rich():
    """All tails must have ≥50% GC (pre-existing GC-rich filter still active)."""
    for tail_len in range(FORWARD_TAIL_MIN, FORWARD_TAIL_MAX + 1):
        pool = _generate_tail_pool(tail_len)
        for tail in pool:
            gc_frac = sum(1 for b in tail if b in "GC") / len(tail)
            assert gc_frac >= 0.5, f"Tail '{tail}' has GC={gc_frac:.0%} < 50%."


# ── Full pipeline: low-GC miRNA still gets candidates ────────────

def test_low_gc_mirna_gets_candidates():
    """
    A low-GC miRNA (AT-rich) must still produce at least one forward candidate
    despite the stricter tail homopolymer filter. Ensures pool not too sparse.
    miR-7-5p: UGGAAGACUAGUGAUUUUGUUGU (24 nt, GC ~33%)
    """
    seq = "UGGAAGACUAGUGAUUUUGUUGU"
    params = {}  # use all defaults
    candidates, rejection_log = generate_forward_candidates(seq, params)
    assert len(candidates) > 0, (
        "No forward primer candidates generated for low-GC miRNA after Busk14 tail filter. "
        f"Rejection log: {rejection_log[:5]}"
    )


if __name__ == "__main__":
    test_constant_value()
    test_no_homopolymer_run_all_lengths()
    test_no_poly_ggg_in_pool()
    test_no_poly_ccc_in_pool()
    test_pool_not_empty_short_lengths()
    test_pool_not_empty_long_lengths()
    test_all_tails_gc_rich()
    test_low_gc_mirna_gets_candidates()
    print("\nAll tail_pool tests passed.")
