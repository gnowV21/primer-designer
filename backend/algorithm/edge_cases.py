# ================================================================
# algorithm/edge_cases.py — Phase 4: Edge-case detection module
#
# detect_edge_cases(seq) → list[dict]
# Runs inside /api/design (synchronous, O(n), no thermodynamics).
# All thresholds in constants.py SECTION Q.
# ================================================================

from .constants import (
    MIRNA_LEN_CRITICAL_SHORT,
    MIRNA_LEN_WARN_SHORT,
    MIRNA_LEN_INFO_LONG,
    MIRNA_GC_LOW,
    MIRNA_GC_HIGH,
    HOMOPOLYMER_RUN_MIN,
    POLY_G_RUN_MIN,
    LOW_COMPLEXITY_TOP2_PCT,
    LOW_COMPLEXITY_DINUC_REP,
)


def detect_edge_cases(seq: str) -> list[dict]:
    """
    Analyse a mature miRNA sequence for conditions that reduce primer design reliability.

    Args:
        seq: Mature miRNA sequence (RNA or DNA, uppercase or lowercase).

    Returns:
        list of {code, severity, message, value} — empty list if no issues.
        severity: 'critical' | 'warning' | 'info'
    """
    seq = seq.upper().strip()
    cases = []

    # E8: ambiguous / invalid bases — checked first; return immediately if found
    valid_bases = set("ACGTU")
    invalid_chars = sorted(set(seq) - valid_bases)
    if invalid_chars:
        cases.append({
            "code": "E8",
            "severity": "critical",
            "message": f"Ambiguous/invalid base detected ({', '.join(invalid_chars)}); cannot design reliably.",
            "value": invalid_chars,
        })
        return cases

    n = len(seq)
    seq_dna = seq.replace("U", "T")

    # E1 / E2: length checks (too short)
    if n < MIRNA_LEN_CRITICAL_SHORT:
        cases.append({
            "code": "E1",
            "severity": "critical",
            "message": (
                f"miRNA length {n} nt is unusually short; the 6-nt overhang + specific region "
                f"may be unreliable."
            ),
            "value": n,
        })
    elif n < MIRNA_LEN_WARN_SHORT:
        cases.append({
            "code": "E2",
            "severity": "warning",
            "message": f"Short miRNA ({n} nt) — consider verifying forward primer Tm.",
            "value": n,
        })

    # E3: length check (too long)
    if n > MIRNA_LEN_INFO_LONG:
        cases.append({
            "code": "E3",
            "severity": "info",
            "message": (
                f"miRNA longer than typical mature length (~22 nt); verify this is a mature "
                f"sequence, not a pre-miRNA."
            ),
            "value": n,
        })

    # E4 / E5: GC content
    gc_count = sum(1 for b in seq_dna if b in "GC")
    gc_pct = round(gc_count / n * 100, 1) if n > 0 else 0.0
    if gc_pct < MIRNA_GC_LOW:
        cases.append({
            "code": "E4",
            "severity": "warning",
            "message": f"Low miRNA GC ({gc_pct}%) → low primer Tm; a longer 5’ tail may be needed.",
            "value": gc_pct,
        })
    elif gc_pct > MIRNA_GC_HIGH:
        cases.append({
            "code": "E5",
            "severity": "warning",
            "message": f"High miRNA GC ({gc_pct}%) → strong secondary structure / melting difficulty.",
            "value": gc_pct,
        })

    # E6: homopolymer run (any base ≥ HOMOPOLYMER_RUN_MIN, or poly-G ≥ POLY_G_RUN_MIN)
    max_run_len, max_run_base = _max_run(seq_dna)
    poly_g_len = _max_run_of(seq_dna, "G")
    if max_run_len >= HOMOPOLYMER_RUN_MIN or poly_g_len >= POLY_G_RUN_MIN:
        run_str = max_run_base * max_run_len
        cases.append({
            "code": "E6",
            "severity": "warning",
            "message": (
                f"Homopolymer run detected ({run_str}); may cause polymerase slippage / mispriming."
            ),
            "value": max_run_len,
        })

    # E7: low complexity (top-2 bases dominate, or dinucleotide repeat)
    counts = {b: seq_dna.count(b) for b in "ACGT"}
    top2_count = sum(sorted(counts.values(), reverse=True)[:2])
    top2_pct = top2_count / n * 100 if n > 0 else 0.0
    e7_found = top2_pct >= LOW_COMPLEXITY_TOP2_PCT
    if not e7_found:
        for i in range(len(seq_dna) - 1):
            di = seq_dna[i:i+2]
            if len(set(di)) == 2 and (di * LOW_COMPLEXITY_DINUC_REP) in seq_dna:
                e7_found = True
                break
    if e7_found:
        cases.append({
            "code": "E7",
            "severity": "info",
            "message": "Low sequence complexity — specificity may be reduced.",
            "value": round(top2_pct, 1),
        })

    return cases


# ── Helpers ──────────────────────────────────────────────────────

def _max_run_of(seq: str, base: str) -> int:
    """Max consecutive run of a single base character."""
    max_r = cur = 0
    for c in seq:
        cur = cur + 1 if c == base else 0
        max_r = max(max_r, cur)
    return max_r


def _max_run(seq: str) -> tuple[int, str]:
    """Max run of any base. Returns (length, base_char)."""
    if not seq:
        return 0, ""
    max_r, cur, best, cur_b = 0, 0, seq[0], seq[0]
    for c in seq:
        if c == cur_b:
            cur += 1
        else:
            cur_b = c
            cur = 1
        if cur > max_r:
            max_r = cur
            best = cur_b
    return max_r, best
