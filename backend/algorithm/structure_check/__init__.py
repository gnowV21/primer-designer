# ================================================================
# structure_check/__init__.py — Module 5: Secondary structure checks
# All checks use primer3-py thermodynamic alignment.
# Consistent with Primer3Plus P3_THERMODYNAMIC_OLIGO_ALIGNMENT=True
#
# Package note: heterodimer.py lives as a sub-module of this package.
# design.py imports: from algorithm.structure_check import run_all_structure_checks
#                    from algorithm.structure_check.heterodimer import check_all_heterodimers
# ================================================================

import primer3
from ..constants import (
    HAIRPIN_DG_MAX_INTERNAL,
    SELF_DIMER_DG_MAX, SELF_DIMER_DG_3PRIME_MAX,
    HETERO_DIMER_DG_MAX, HETERO_DIMER_DG_3PRIME_MAX,
    END_DIMER_DG_CRITICAL, END_STABILITY_MAX,
)
from ..thermodynamics import _get_p3_params, calculate_end_stability


def run_all_structure_checks(forward_seq: str, reverse_seq: str, params: dict) -> dict:
    """
    Run all four structure checks for a forward primer candidate.

    Checks:
    1. Self-hairpin ΔG
    2. Self-dimer ΔG (overall + 3' end)
    3. Hetero-dimer with universal reverse ΔG (overall + 3' end)
    4. 3' end stability (last 5 bases) [P3P PRIMER_MAX_END_STABILITY]
    """
    p3 = _get_p3_params(params)
    temp_c = float(params.get("annealingTemp", 60.0))

    hp  = _check_hairpin(forward_seq, p3, temp_c)
    sd  = _check_self_dimer(forward_seq, p3, temp_c)
    hd  = _check_hetero_dimer(forward_seq, reverse_seq, p3, temp_c)
    es  = _check_end_stability(forward_seq, p3)

    return {
        "hairpin":      hp,
        "self_dimer":   sd,
        "hetero_dimer": hd,
        "end_stability": es,
        "overall_pass": (
            hp["pass"] and
            sd["pass_overall"] and sd["pass_3prime"] and
            hd["pass_overall"] and hd["pass_3prime"] and
            es["pass"]
        ),
        "has_critical_flag": (
            sd.get("critical_3prime", False) or
            hd.get("critical_3prime", False)
        ),
    }


# ── Internal helpers ──────────────────────────────────────────────

def _check_hairpin(seq: str, p3: dict, temp_c: float) -> dict:
    """Self-hairpin. Threshold: ΔG > HAIRPIN_DG_MAX_INTERNAL (-3.0 kcal/mol). [ResearchGate qPCR]"""
    try:
        result = primer3.calc_hairpin(
            seq=seq,
            mv_conc=p3["mv_conc"], dv_conc=p3["dv_conc"],
            dntp_conc=p3["dntp_conc"], dna_conc=p3["dna_conc"],
            temp_c=temp_c,
        )
        dg = round(float(result.dg) / 1000, 2)
        tm = round(float(result.tm), 1)
    except Exception:
        dg, tm = 0.0, 0.0

    passes = dg > HAIRPIN_DG_MAX_INTERNAL
    severity = _hairpin_severity(dg)
    return {
        "dg": dg, "tm": tm,
        "pass": passes,
        "severity": severity,
        "threshold_used": HAIRPIN_DG_MAX_INTERNAL,
        "note": _hairpin_note(dg, severity),
    }


def _check_self_dimer(seq: str, p3: dict, temp_c: float) -> dict:
    """
    Self-dimer (homo-dimer) — overall and 3' end.
    3' end CRITICAL: polymerase can extend → primer-dimer artifacts. [IDT]
    """
    try:
        r_any = primer3.calc_homodimer(
            seq=seq,
            mv_conc=p3["mv_conc"], dv_conc=p3["dv_conc"],
            dntp_conc=p3["dntp_conc"], dna_conc=p3["dna_conc"],
            temp_c=temp_c,
        )
        dg_any = round(float(r_any.dg) / 1000, 2)
    except Exception:
        dg_any = 0.0

    # 3' end: use last 8 bases homo-dimer as proxy for end dimer
    try:
        end_seq = seq[-8:] if len(seq) >= 8 else seq
        r_end = primer3.calc_homodimer(
            seq=end_seq,
            mv_conc=p3["mv_conc"], dv_conc=p3["dv_conc"],
            dntp_conc=p3["dntp_conc"], dna_conc=p3["dna_conc"],
            temp_c=temp_c,
        )
        dg_end = round(float(r_end.dg) / 1000, 2)
    except Exception:
        dg_end = 0.0

    pass_overall    = dg_any > SELF_DIMER_DG_MAX
    pass_3prime     = dg_end > SELF_DIMER_DG_3PRIME_MAX
    critical_3prime = dg_end <= END_DIMER_DG_CRITICAL

    return {
        "dg_overall": dg_any, "dg_3prime": dg_end,
        "pass_overall": pass_overall, "pass_3prime": pass_3prime,
        "critical_3prime": critical_3prime,
        "threshold_overall": SELF_DIMER_DG_MAX,
        "threshold_3prime": SELF_DIMER_DG_3PRIME_MAX,
        "note": _dimer_note("self", dg_any, dg_end, critical_3prime),
    }


def _check_hetero_dimer(seq1: str, seq2: str, p3: dict, temp_c: float) -> dict:
    """
    Hetero-dimer: forward primer vs universal reverse.
    3' complementarity creates extendable primer-dimer artifacts. [IDT]
    """
    try:
        r_any = primer3.calc_heterodimer(
            seq1=seq1, seq2=seq2,
            mv_conc=p3["mv_conc"], dv_conc=p3["dv_conc"],
            dntp_conc=p3["dntp_conc"], dna_conc=p3["dna_conc"],
            temp_c=temp_c,
        )
        dg_any = round(float(r_any.dg) / 1000, 2)
    except Exception:
        dg_any = 0.0

    # 3' end hetero-dimer: last 8 bases of forward vs last 8 of reverse
    try:
        end1 = seq1[-8:] if len(seq1) >= 8 else seq1
        end2 = seq2[-8:] if len(seq2) >= 8 else seq2
        r_end = primer3.calc_heterodimer(
            seq1=end1, seq2=end2,
            mv_conc=p3["mv_conc"], dv_conc=p3["dv_conc"],
            dntp_conc=p3["dntp_conc"], dna_conc=p3["dna_conc"],
            temp_c=temp_c,
        )
        dg_end = round(float(r_end.dg) / 1000, 2)
    except Exception:
        dg_end = 0.0

    pass_overall    = dg_any > HETERO_DIMER_DG_MAX
    pass_3prime     = dg_end > HETERO_DIMER_DG_3PRIME_MAX
    critical_3prime = dg_end <= END_DIMER_DG_CRITICAL

    return {
        "dg_overall": dg_any, "dg_3prime": dg_end,
        "pass_overall": pass_overall, "pass_3prime": pass_3prime,
        "critical_3prime": critical_3prime,
        "threshold_overall": HETERO_DIMER_DG_MAX,
        "threshold_3prime": HETERO_DIMER_DG_3PRIME_MAX,
        "note": _dimer_note("hetero", dg_any, dg_end, critical_3prime),
    }


def _check_end_stability(seq: str, p3: dict) -> dict:
    """
    3' end stability of last 5 bases.
    Primer3Plus PRIMER_MAX_END_STABILITY = 9.0 kcal/mol. [P3P]
    High stability → increased mispriming risk.
    """
    last5 = seq[-5:] if len(seq) >= 5 else seq
    stability = calculate_end_stability(last5, p3)
    passes = stability <= END_STABILITY_MAX
    return {
        "last_5_bases": last5,
        "stability_kcal_mol": stability,
        "pass": passes,
        "threshold": END_STABILITY_MAX,
        "source": "Primer3Plus PRIMER_MAX_END_STABILITY = 9.0 kcal/mol",
        "note": (
            f"3' end stability = {stability:.2f} kcal/mol (threshold: ≤ {END_STABILITY_MAX} kcal/mol). "
            + ("PASS — low mispriming risk at 3' end." if passes
               else "FAIL — high 3' end stability may increase mispriming risk.")
        ),
    }


# ── Severity helpers ──────────────────────────────────────────────

def _hairpin_severity(dg: float) -> str:
    if dg > -2.0:   return "safe"
    elif dg > -3.0: return "acceptable"
    elif dg > -6.0: return "warning"
    else:           return "critical"


def _hairpin_note(dg: float, severity: str) -> str:
    notes = {
        "safe":       f"No significant hairpin (ΔG = {dg:.2f} kcal/mol). Primer is stable for annealing.",
        "acceptable": f"Weak hairpin (ΔG = {dg:.2f} kcal/mol) — acceptable for qPCR. Monitor amplification efficiency.",
        "warning":    f"Moderate hairpin (ΔG = {dg:.2f} kcal/mol) — may reduce primer availability. Consider alternative.",
        "critical":   f"Strong hairpin (ΔG = {dg:.2f} kcal/mol) — will significantly reduce primer effectiveness. Redesign recommended.",
    }
    return notes.get(severity, "")


def _dimer_note(dimer_type: str, dg_any: float, dg_end: float, critical: bool) -> str:
    label = "Self-dimer" if dimer_type == "self" else "Hetero-dimer (forward + reverse)"
    if critical:
        return (f"{label}: 3'-end ΔG = {dg_end:.2f} kcal/mol — CRITICAL. "
                "Polymerase can extend this dimer, generating primer-dimer artifacts.")
    elif dg_end <= SELF_DIMER_DG_3PRIME_MAX:
        return f"{label}: 3'-end ΔG = {dg_end:.2f} kcal/mol — WARNING. Close to the acceptable limit."
    else:
        return f"{label}: ΔG = {dg_any:.2f} kcal/mol (3'-end: {dg_end:.2f}) — within acceptable range."
