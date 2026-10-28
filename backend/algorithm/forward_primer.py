# ================================================================
# forward_primer.py — Module 2: Forward primer candidate generation
# v2.8 key changes:
#   - specific_lengths = [12..17] nt [K11]
#   - EXCLUDES last 6 nt of miRNA (used by stemloop overhang) [V07]
#   - Exhaustive/random tail pool generation (vs hardcoded 6-7 seqs) [Fix L1]
#   - Real 2-step Tm: compute actual Tm for every (tail+specific) pair [Fix L2]
#   - Exact amplicon formula derived from cDNA/primer geometry [Fix L4]
# ================================================================

import hashlib
import itertools
import random

from .constants import (
    FORWARD_SPECIFIC_LENGTHS, FORWARD_SPECIFIC_LENGTH_MAX,
    FORWARD_EXCLUDES_LAST_NT,
    FORWARD_TAIL_MIN, FORWARD_TAIL_MAX,
    FORWARD_MIN_LENGTH, FORWARD_MAX_LENGTH, FORWARD_OPTIMAL_LENGTH,
    GC_MIN, GC_MAX, MAX_HOMOPOLYMER_RUN, GC_CLAMP_MIN_IN_LAST3, GC_CLAMP_HARD_MIN_IN_LAST3,
    FORWARD_TAILS_PER_LENGTH,
    GC_MAX_IN_3PRIME_WINDOW, PRIMER_AVOID_T_AT_3PRIME,
    AMPLICON_MIN_QPCR, AMPLICON_MAX_QPCR,
    STEMLOOP_BODY, STEMLOOP_BODY_LENGTH, UNIVERSAL_REVERSE,
    MIN_CANDIDATE_3PRIME_DISTANCE, TM_ANNEALING_TEMP_DEFAULT, TM_FORWARD_TOLERANCE,
    TAIL_MAX_HOMOPOLYMER_RUN,
    TM_BINDING_TARGET, TM_BINDING_TOLERANCE,
)
from .sequence_utils import rna_to_dna, calculate_gc, check_homopolymer
from .thermodynamics import calculate_tm_nn, calculate_tm_binding_only

# ── Amplicon geometry constant ──────────────────────────────────────────────────
# cDNA structure (5'→3'): [STEMLOOP_BODY(44nt)][RC(miRNA)(N nt)]
# Forward primer covers miRNA[0:specific_len] (specific_len = 12–17).
# Universal reverse primer matches STEMLOOP_BODY at position 7 (0-based, inclusive).
# Amplicon = tail_len + miRNA_len + (STEMLOOP_BODY_LENGTH - univ_rev_start_pos)
#          = tail_len + miRNA_len + (44 - 7) = tail_len + miRNA_len + 37
# Verified: 22 nt miRNA + 5 nt tail → 5+22+37 = 64 bp ✓ (Chen 2005 range: 60-70 bp)
_UNIV_REV_POS   = STEMLOOP_BODY.find(UNIVERSAL_REVERSE)   # = 7
_AMPLICON_OFFSET = STEMLOOP_BODY_LENGTH - _UNIV_REV_POS    # = 37

# Determinism: the len-7..12 tail pools use weighted-random sampling. A module-global
# RNG would carry state ACROSS design calls, so the same miRNA designed twice would
# yield different primers (state-order dependence). Instead each _generate_tail_pool
# call builds its OWN RNG, seeded from that call's inputs (sequence, tail_len,
# max_pool) — no generator is shared or passed around, so a pool depends only on its
# arguments, never on call order, other pools, or the process. [determinism invariant]
def _rng_for(*key) -> random.Random:
    digest = hashlib.sha256("|".join(map(str, key)).encode("utf-8")).hexdigest()
    return random.Random(int(digest[:12], 16))


def generate_forward_candidates(mature_sequence: str, params: dict) -> tuple:
    """
    Generate forward primer candidates using Primer3Plus SEQUENCE_OVERHANG_LEFT logic.

    Real 2-step Tm (v2.8):
    - specific_region (12-17 nt) binds cDNA → Tm_binding calculated here
    - 5' tail does NOT bind template → actual Tm for full primer (tail+specific)
      computed via SantaLucia 1998 NN model for every candidate

    v2.7: Forward primer uses positions [0 : len(miRNA) - 6] [V07][K11]

    Returns:
        (candidates_passed, rejection_log)
    """
    dna_seq    = rna_to_dna(mature_sequence).upper()
    miRNA_len  = len(dna_seq)
    excludes   = int(params.get("bindingRegion3prime", FORWARD_EXCLUDES_LAST_NT))
    available  = dna_seq[: miRNA_len - excludes]

    rejection_log  = []
    all_candidates = []
    seen_sequences = set()

    target_tm = float(params.get("annealingTemp", TM_ANNEALING_TEMP_DEFAULT))

    # v2.8 fix: generate tail pools ONCE per tail_len (shared across all specific_lens).
    # Previously called _generate_tail_pool inside _find_tails_for_target_tm which
    # was called 6 times — resulting in 60 pool builds instead of 10.
    _tail_pool_cache = {
        tl: _generate_tail_pool(tl, sequence=dna_seq)
        for tl in range(FORWARD_TAIL_MIN, FORWARD_TAIL_MAX + 1)
    }

    for specific_len in FORWARD_SPECIFIC_LENGTHS:
        if specific_len > len(available):
            continue

        specific_region = available[:specific_len]
        tm_binding      = calculate_tm_binding_only(specific_region, params)
        tails           = _find_tails_for_target_tm(
            specific_region, tm_binding, target_tm, params, _tail_pool_cache
        )

        for tail in tails:
            full_primer = tail + specific_region
            if full_primer in seen_sequences:
                continue
            seen_sequences.add(full_primer)
            candidate = _build_candidate(
                full_primer, specific_region, tail, specific_len, miRNA_len, params
            )
            all_candidates.append(candidate)

    # Pre-filter (strict)
    passed = []
    for c in all_candidates:
        hard_reasons, warning_reasons = _prefilter(c, params)
        if not hard_reasons:
            c["warnings_from_prefilter"] = warning_reasons
            passed.append(c)
        else:
            for r in hard_reasons:
                rejection_log.append({"sequence": c["sequence"], "reason": r})

    # Hand the best few tails of EVERY 3' end to scoring; which sets are returned is
    # decided after scoring by select_diverse_top (v3.2.0).
    passed = _candidate_pool(passed, target_tm)
    return passed, rejection_log


def _build_candidate(full_primer, specific_region, tail, specific_len, miRNA_len, params):
    gc        = calculate_gc(full_primer)
    gc_spec   = calculate_gc(specific_region)
    tm_bind   = calculate_tm_binding_only(specific_region, params)
    tm_full   = calculate_tm_nn(full_primer, params)
    amplicon  = _compute_amplicon_size(len(tail), miRNA_len)
    return {
        "sequence":            full_primer,
        "specific_region":     specific_region,
        "tail":                tail,
        "length":              len(full_primer),
        "specific_length":     specific_len,
        "tail_length":         len(tail),
        "gc_percent":          gc,
        "gc_specific_percent": gc_spec,
        "tm_full":             round(tm_full, 1),
        "tm_binding":          round(tm_bind, 1),
        "amplicon_size":       amplicon,
    }


def _find_tails_for_target_tm(
    specific_region: str,
    tm_binding: float,
    target_tm: float,
    params: dict,
    tail_pool_cache: dict,
) -> list:
    """
    Select tails so that Tm(tail + specific) is closest to target_tm.

    v2.8: Computes real SantaLucia 1998 NN Tm for every (tail+specific) pair
    instead of returning a fixed set. Searches across all tail lengths (3–12 nt)
    using exhaustive enumeration (lengths ≤ 6) and weighted-random sampling
    (lengths 7–12), giving ~4 000–6 000 candidates per specific region.

    tail_pool_cache must be pre-built by the caller (one build per tail_len
    rather than one per specific_len × tail_len).
    """
    _TM_STRICT = 3.0   # ±3 °C primary acceptance window
    _TM_WIDE   = 6.0   # ±6 °C fallback if fewer than 5 found in strict window

    scored = []   # [(tail, abs_delta_tm), ...]

    for tail_len in range(FORWARD_TAIL_MIN, FORWARD_TAIL_MAX + 1):
        pool = tail_pool_cache.get(tail_len, [])
        for tail in pool:
            tm_full = calculate_tm_nn(tail + specific_region, params)
            scored.append((tail, abs(tm_full - target_tm)))

    scored.sort(key=lambda x: x[1])

    selected = [t for t, d in scored if d <= _TM_STRICT]
    if len(selected) < 5:
        selected = [t for t, d in scored if d <= _TM_WIDE]
    if len(selected) < 5:
        selected = [t for t, d in scored[:10]]

    # Cap at 200: _candidate_pool keeps only FORWARD_TAILS_PER_LENGTH per specific
    # length anyway, so more than ~200 tails here just wastes prefilter computation.
    return selected[:200]


def _generate_tail_pool(tail_len: int, max_pool: int = 400, sequence: str = "") -> list:
    """
    Build a pool of GC-rich (≥50 %), no-homopolymer-run (< 4) tail sequences.

    Lengths ≤ 6: exhaustive enumeration over all 4^n k-mers, then sorted by
    GC% descending before capping at max_pool.
    v2.8 fix: previously capped BEFORE sorting → alphabetically-first 400
    sequences were kept, discarding 83 % of valid len-6 tails (A-biased pool).

    Lengths 7–12: weighted-random sampling (GC bases biased 2×) until max_pool,
    from an RNG local to this call and seeded from (sequence, tail_len, max_pool).

    Pool sizes (approximate, after GC and homopolymer filtering):
      len 3 → ~32     len 4 → ~176     len 5 → ~480     len 6 → ~2 400
      len 7–12 → 300–400 random samples each
    """
    GC_BASES = frozenset("GC")
    result   = []

    def _has_tail_homopolymer(t):
        """Return True if tail contains a run of TAIL_MAX_HOMOPOLYMER_RUN or more identical bases."""
        run_str = lambda b: b * TAIL_MAX_HOMOPOLYMER_RUN
        return any(run_str(b) in t for b in "ACGT")

    if tail_len <= 6:
        for combo in itertools.product("ACGT", repeat=tail_len):
            tail = "".join(combo)
            if sum(1 for b in tail if b in GC_BASES) / tail_len < 0.5:
                continue
            if _has_tail_homopolymer(tail):
                continue
            result.append(tail)
        # Sort by GC% descending so the pool top-400 are the most GC-rich tails,
        # not the alphabetically-first 400 (which are biased toward A/C-heavy sequences).
        result.sort(key=lambda s: -sum(1 for b in s if b in GC_BASES))
        result = result[:max_pool]
    else:
        # Build the RNG ONCE, before the loop: re-creating it per attempt would replay
        # the same draw every time and collapse the pool to a single tail.
        rng      = _rng_for(sequence, tail_len, max_pool)
        seen     = set()
        attempts = 0
        max_att  = max_pool * 30
        while len(result) < max_pool and attempts < max_att:
            attempts += 1
            # Weight G/C 2× over A/T to bias toward GC-rich tails
            tail = "".join(rng.choices("ACGT", weights=[1, 2, 2, 1], k=tail_len))
            if tail in seen:
                continue
            seen.add(tail)
            if sum(1 for b in tail if b in GC_BASES) / tail_len < 0.5:
                continue
            if _has_tail_homopolymer(tail):
                continue
            result.append(tail)

    return result


def _prefilter(candidate: dict, params: dict) -> tuple:
    """
    Pre-filter candidates. Returns (hard_rejection_reasons, warning_reasons).
    hard_reasons block candidate; warning_reasons are informational only.
    """
    hard_reasons    = []
    warning_reasons = []

    seq    = candidate["sequence"]
    tm     = candidate["tm_full"]
    gc     = candidate["gc_percent"]
    amp    = candidate["amplicon_size"]
    length = candidate["length"]

    tm_min = float(params.get("tmMin", TM_ANNEALING_TEMP_DEFAULT - TM_FORWARD_TOLERANCE))
    tm_max = float(params.get("tmMax", TM_ANNEALING_TEMP_DEFAULT + TM_FORWARD_TOLERANCE))

    if not (tm_min <= tm <= tm_max):
        hard_reasons.append("tm_out_of_range")
    if candidate["tm_binding"] < TM_BINDING_TARGET - 2 * TM_BINDING_TOLERANCE:
        hard_reasons.append("tm_binding_too_low")
    if not (float(params.get("gcMin", GC_MIN)) <= gc <= float(params.get("gcMax", GC_MAX))):
        hard_reasons.append("gc_out_of_range")
    if length < FORWARD_MIN_LENGTH:
        hard_reasons.append("too_short")
    if length > FORWARD_MAX_LENGTH:
        hard_reasons.append("too_long")

    if check_homopolymer(seq, MAX_HOMOPOLYMER_RUN):
        hard_reasons.append("homopolymer_run")

    # GC Clamp [IDT PrimerQuest]: 2 G/C in the last 3 bases preferred. The forward
    # primer's 3' end is set by the miRNA, so 1 G/C only warns (and scores 75 on the
    # gc_clamp criterion); 0 G/C — an all-A/T 3' end — is rejected. (v3.2.0)
    if params.get("gcClamp3prime", True):
        gc_last3 = sum(1 for b in seq[-3:].upper() if b in "GC")
        if gc_last3 < GC_CLAMP_HARD_MIN_IN_LAST3:
            hard_reasons.append("gc_clamp_fail")
        elif gc_last3 < GC_CLAMP_MIN_IN_LAST3:
            warning_reasons.append("gc_clamp_weak_warning")

    # GC end window: total GC in last 5 bases must be < max [P3P Max End GC=5]
    # v2.8 fix: was `> 5` on a 5-base window — impossible (max=5), never fired.
    # Correct condition is `>=` so GGGGG (all-GC 3' end) is rejected as intended.
    last5 = seq[-5:].upper()
    if sum(1 for b in last5 if b in "GC") >= GC_MAX_IN_3PRIME_WINDOW:
        hard_reasons.append("gc_end_window_fail")

    amp_min = int(params.get("ampliconMin", AMPLICON_MIN_QPCR))
    amp_max = int(params.get("ampliconMax", AMPLICON_MAX_QPCR))
    if not (amp_min <= amp <= amp_max):
        hard_reasons.append("amplicon_out_of_range")

    # T at 3' end — WARNING only, does not block [IDT / Section N]
    if PRIMER_AVOID_T_AT_3PRIME and seq[-1].upper() == "T":
        warning_reasons.append("t_at_3prime_warning")

    return hard_reasons, warning_reasons


def _candidate_pool(candidates: list, target_tm: float,
                    per_length: int = FORWARD_TAILS_PER_LENGTH) -> list:
    """
    Keep the `per_length` tails closest to target_tm for EACH specific length (each
    3' end), so every usable 3' end reaches the 15-criterion score.

    Replaces the pre-score diversity filter (≤ v3.1.2), which kept one candidate per
    3' end picked by |Tm_full − Ta| alone — Tm ties fell to generation order, so the
    12-nt region won over the 13-nt one just by being generated first — and dropped
    3' ends 1 nt from a kept one before anything was scored. Ties here break on the
    sequence, so the pool never depends on generation order.
    """
    by_length: dict[int, list] = {}
    for c in sorted(candidates, key=lambda x: (abs(x.get("tm_full", 0) - target_tm),
                                               x["sequence"])):
        kept = by_length.setdefault(c["specific_length"], [])
        if len(kept) < per_length:
            kept.append(c)
    return [c for length in sorted(by_length) for c in by_length[length]]


def select_diverse_top(ranked: list, n: int) -> list:
    """
    Pick n sets from score-ranked candidates (best first) — the score decides, and
    diversity only shapes the alternatives, relaxing in steps until n are found:

      1. 3' end ≥ MIN_CANDIDATE_3PRIME_DISTANCE nt from every pick [P3P]
      2. 3' end ≥ 1 nt away (adjacent specific lengths)
      3. same 3' end, different tail — same binding region, so same specificity

    Each pick is labelled in `selection` against the higher-ranked picks:
    'best' (rank 1), 'distinct_3prime', 'adjacent_3prime' or 'tail_variant'
    (+ `same_binding_as_rank`). The result is re-sorted by score.
    """
    chosen: list[int] = []                       # indices into `ranked`
    for spacing in (MIN_CANDIDATE_3PRIME_DISTANCE, 1, 0):
        for i, c in enumerate(ranked):
            if len(chosen) == n:
                break
            if i not in chosen and all(
                    abs(c["specific_length"] - ranked[j]["specific_length"]) >= spacing
                    for j in chosen):
                chosen.append(i)
    picked = [ranked[i] for i in sorted(chosen)]

    for i, c in enumerate(picked):
        gaps = [abs(c["specific_length"] - p["specific_length"]) for p in picked[:i]]
        if i == 0:
            c["selection"] = "best"
        elif 0 in gaps:
            c["selection"] = "tail_variant"
            c["same_binding_as_rank"] = gaps.index(0) + 1
        elif min(gaps) < MIN_CANDIDATE_3PRIME_DISTANCE:
            c["selection"] = "adjacent_3prime"
        else:
            c["selection"] = "distinct_3prime"
    return picked


def _compute_amplicon_size(tail_len: int, miRNA_len: int) -> int:
    """
    Exact amplicon size for stem-loop RT-qPCR (derived from cDNA geometry).

    TOP strand of amplicon (5'→3'):
      [tail] [specific(0:L)] [miRNA(L:N)] [RC(STEMLOOP[7:44])]
             |← fwd primer →|
                                           |← univ-rev complement →|

    Length = tail_len + specific_len + (miRNA_len - specific_len) + (44 - 7)
           = tail_len + miRNA_len + 37

    _AMPLICON_OFFSET = STEMLOOP_BODY_LENGTH - STEMLOOP_BODY.find(UNIVERSAL_REVERSE)
                     = 44 - 7 = 37
    """
    return tail_len + miRNA_len + _AMPLICON_OFFSET
