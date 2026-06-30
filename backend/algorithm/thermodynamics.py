# ================================================================
# thermodynamics.py — Tm and ΔG calculations via primer3-py
# Method: SantaLucia 1998 nearest-neighbor + Owczarzy 2004 Mg2+ correction
# Consistent with Primer3Plus PRIMER_TM_FORMULA=1, PRIMER_SALT_CORRECTIONS=1
# ================================================================

import primer3
from .constants import (
    P3_DEFAULT_MV_CONC, P3_DEFAULT_DV_CONC,
    P3_DEFAULT_DNTP_CONC, P3_DEFAULT_DNA_CONC,
)


def _get_p3_params(params: dict) -> dict:
    """Extract primer3-py calculation parameters from user formData."""
    return {
        "mv_conc":   float(params.get("saltConcentration",       P3_DEFAULT_MV_CONC)),
        "dv_conc":   float(params.get("magnesiumConcentration",  P3_DEFAULT_DV_CONC)),
        "dntp_conc": float(params.get("dntpTotal",               P3_DEFAULT_DNTP_CONC)),
        "dna_conc":  float(params.get("primerConcentration",     P3_DEFAULT_DNA_CONC)),
    }


def calculate_tm_nn(sequence: str, params: dict) -> float:
    """
    Tm via nearest-neighbor (SantaLucia 1998) + Mg2+ salt correction.
    Mirrors Primer3Plus PRIMER_TM_FORMULA=1, PRIMER_SALT_CORRECTIONS=1. [P3P][SL98]
    """
    p3 = _get_p3_params(params)
    tm = primer3.calc_tm(
        seq=sequence,
        mv_conc=p3["mv_conc"],
        dv_conc=p3["dv_conc"],
        dntp_conc=p3["dntp_conc"],
        dna_conc=p3["dna_conc"],
    )
    return round(float(tm), 2)


def calculate_tm_binding_only(specific_region: str, params: dict) -> float:
    """
    Tm of the binding region only (specific 12-17 nt portion).
    Primer3Plus 2-step logic: Tm calculated only for template-binding 3' portion. [P3P]
    """
    return calculate_tm_nn(specific_region, params)


def calculate_end_stability(last_5_bases: str, params: dict) -> float:
    """
    Stability of the last 5 bases at 3' end (|ΔG| at 37°C).
    Mapping: Primer3Plus PRIMER_MAX_END_STABILITY = 9.0 kcal/mol. [P3P]
    Returns absolute value (positive kcal/mol).
    """
    p3 = _get_p3_params(params)
    try:
        result = primer3.calc_hairpin(
            seq=last_5_bases,
            mv_conc=p3["mv_conc"],
            dv_conc=p3["dv_conc"],
            dntp_conc=p3["dntp_conc"],
            dna_conc=p3["dna_conc"],
            temp_c=37.0,
        )
        return round(abs(float(result.dg) / 1000), 2)
    except Exception:
        return 0.0
