# ================================================================
# structure_check/heterodimer.py — Cross-primer heterodimer check
#
# Checks two critical pairs per forward primer candidate:
#   1. forward × stemloop RT primer  (RT step — Kramer 2011 buffer)
#   2. forward × universal reverse   (PCR step — user params buffer)
#
# Two-layer risk classification:
#   HIGH     : dG ≤ HIGH_RISK_DG  AND  3' end complementarity ≥ 3 bp
#              → polymerase CAN extend this dimer (extension artifact risk)
#   MODERATE : dG ≤ HIGH_RISK_DG  AND  no 3' end complementarity
#              → strong internal binding, but extension is impeded
#   LOW      : HIGH_RISK_DG < dG ≤ LOW_RISK_DG
#   PASS     : dG > LOW_RISK_DG
#
# Sources: [IDT] OligoAnalyzer guidelines; [K11] Kramer 2011 Table 2
# ================================================================

import primer3
from ..thermodynamics import _get_p3_params
from ..constants import (
    HETERODIMER_HIGH_RISK_DG, HETERODIMER_LOW_RISK_DG, HETERODIMER_3PRIME_MIN_BP,
    P3_RT_MV_CONC, P3_RT_DV_CONC, P3_RT_DNTP_CONC, P3_RT_DNA_CONC,
)

# Complement table — handles both DNA (T) and RNA (U) input
_COMP_TRANS = str.maketrans("ACGTU", "TGCAA")


def check_all_heterodimers(
    forward_seq: str,
    stemloop_seq: str,
    reverse_seq: str,
    params: dict,
) -> dict:
    """
    Compute heterodimer ΔG and 3'-end complementarity for both primer pairs.

    Reaction-specific buffer conditions:
      - forward × stemloop RT  → RT buffer (Kramer 2011 Table 2)
      - forward × universal reverse → PCR buffer (user params)

    Returns a dict matching the 'heterodimer_checks' key in the API response.
    """
    rt_p3  = _rt_p3_params()
    pcr_p3 = _get_p3_params(params)
    temp_c = float(params.get("annealingTemp", 60.0))

    fwd_sl  = _check_pair(forward_seq, stemloop_seq, rt_p3,  temp_c, label="fwd_stemloop")
    fwd_rev = _check_pair(forward_seq, reverse_seq,  pcr_p3, temp_c, label="fwd_reverse")

    return {
        "heterodimer_fwd_stemloop": fwd_sl,
        "heterodimer_fwd_reverse":  fwd_rev,
        "any_high_risk": (
            fwd_sl["risk_level"] == "HIGH" or fwd_rev["risk_level"] == "HIGH"
        ),
        "any_moderate_or_above": (
            fwd_sl["risk_level"] in ("HIGH", "MODERATE") or
            fwd_rev["risk_level"] in ("HIGH", "MODERATE")
        ),
    }


# ── Internal helpers ──────────────────────────────────────────────

def _rt_p3_params() -> dict:
    """Kramer 2011 RT buffer conditions (Table 2). Independent of user params."""
    return {
        "mv_conc":   P3_RT_MV_CONC,
        "dv_conc":   P3_RT_DV_CONC,
        "dntp_conc": P3_RT_DNTP_CONC,
        "dna_conc":  P3_RT_DNA_CONC,
    }


def _check_pair(seq1: str, seq2: str, p3: dict, temp_c: float, label: str) -> dict:
    """Run calc_heterodimer on the pair and classify risk."""
    dg = _calc_heterodimer_dg(seq1, seq2, p3, temp_c)
    overlap, bp_count = _detect_3prime_complementarity(
        seq1, seq2, min_bp=HETERODIMER_3PRIME_MIN_BP
    )
    risk = _classify_risk(dg, overlap)

    return {
        "dg": dg,
        "risk_level": risk,
        "three_prime_overlap": overlap,
        "three_prime_bp": bp_count,
        "note": _risk_note(label, dg, risk, overlap, bp_count),
    }


def _calc_heterodimer_dg(seq1: str, seq2: str, p3: dict, temp_c: float) -> float:
    """Return ΔG (kcal/mol) of the most stable heterodimer conformation."""
    try:
        result = primer3.calc_heterodimer(
            seq1=seq1, seq2=seq2,
            mv_conc=p3["mv_conc"],
            dv_conc=p3["dv_conc"],
            dntp_conc=p3["dntp_conc"],
            dna_conc=p3["dna_conc"],
            temp_c=temp_c,
        )
        return round(float(result.dg) / 1000, 2)
    except Exception:
        return 0.0


def _detect_3prime_complementarity(seq1: str, seq2: str, min_bp: int = 3) -> tuple:
    """
    Check whether the 3' terminal bases of seq1 and seq2 form a consecutive
    antiparallel duplex that a polymerase could extend.

    Physical basis (3'-3' junction model):
        seq1 (primer):   5'---A  B  C-3'
        seq2 (template): 5'---C' B' A'-3'  (read 3'→5' as template)

    Condition for position i (counting from 3' end):
        complement(seq1[-i]) == seq2[-i]

    This is a PAIRWISE complement check — NOT a reverse-complement check —
    because both 3' ends face each other in the antiparallel alignment.

    Returns (has_overlap: bool, consecutive_bp: int).
    """
    s1 = seq1.upper()
    s2 = seq2.upper()
    max_check = min(len(s1), len(s2))

    consecutive = 0
    for i in range(1, max_check + 1):
        if _complement_base(s1[-i]) == s2[-i]:
            consecutive += 1
        else:
            break

    return consecutive >= min_bp, consecutive


def _complement_base(base: str) -> str:
    """Single-base Watson-Crick complement (DNA/RNA)."""
    return base.translate(_COMP_TRANS)


def _classify_risk(dg: float, three_prime_overlap: bool) -> str:
    """Two-layer risk classification per task spec."""
    if dg <= HETERODIMER_HIGH_RISK_DG and three_prime_overlap:
        return "HIGH"
    if dg <= HETERODIMER_HIGH_RISK_DG:
        return "MODERATE"
    if dg <= HETERODIMER_LOW_RISK_DG:
        return "LOW"
    return "PASS"


def _risk_note(label: str, dg: float, risk: str, overlap: bool, bp_count: int) -> str:
    pair_label = {
        "fwd_stemloop": "Forward × Stem-loop RT (RT step)",
        "fwd_reverse":  "Forward × Universal Reverse (PCR step)",
    }.get(label, label)

    if risk == "HIGH":
        return (
            f"{pair_label}: ΔG = {dg:.2f} kcal/mol — HIGH RISK. "
            f"3' end forms {bp_count}-bp duplex — polymerase extension artifact likely. "
            f"Redesign forward primer or choose a candidate without this overlap."
        )
    if risk == "MODERATE":
        return (
            f"{pair_label}: ΔG = {dg:.2f} kcal/mol — MODERATE RISK. "
            f"Strong internal binding (no 3' complementarity) — extension impeded "
            f"but primer availability may be reduced."
        )
    if risk == "LOW":
        return (
            f"{pair_label}: ΔG = {dg:.2f} kcal/mol — LOW RISK. "
            f"Weak heterodimer within acceptable range. Monitor efficiency."
        )
    return (
        f"{pair_label}: ΔG = {dg:.2f} kcal/mol — PASS. "
        f"No significant heterodimer interaction detected."
    )
