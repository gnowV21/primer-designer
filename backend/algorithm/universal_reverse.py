# ================================================================
# universal_reverse.py — Module 3: Universal reverse primer
# Fixed sequence — no design needed. Return constants only.
# ================================================================

import algorithm.primer3_safe as primer3  # thread-safe wrapper (see primer3_safe.py)
from functools import lru_cache
from .constants import (
    UNIVERSAL_REVERSE, UNIVERSAL_REVERSE_TM_PRECALC,
    UNIVERSAL_REVERSE_GC_PRECALC, UNIVERSAL_REVERSE_CHEN_2005,
    HAIRPIN_DG_MAX_INTERNAL, HAIRPIN_DG_MAX_3PRIME,
    SELF_DIMER_DG_MAX, SELF_DIMER_DG_3PRIME_MAX,
)
from .thermodynamics import _get_p3_params


def get_universal_reverse(params: dict) -> dict:
    """
    Universal reverse primer — FIXED, no design needed.

    Current: 5'-CCAGTGCAGGGTCCGAGGTA-3' (20 nt) [K11]
    Origin: Chen et al. 2005 (16 nt: 5'-GTGCAGGGTCCGAGGT-3')
    Improvement: Kramer 2011 extended to 20 nt for higher sensitivity.
    """
    return {
        "sequence": UNIVERSAL_REVERSE,
        "length": len(UNIVERSAL_REVERSE),
        "gc_percent": UNIVERSAL_REVERSE_GC_PRECALC,
        "tm": UNIVERSAL_REVERSE_TM_PRECALC,
        "self_structure_check": _check_self_structure(UNIVERSAL_REVERSE, params),
        "design_rationale": {
            "original_chen_2005": f"5'-{UNIVERSAL_REVERSE_CHEN_2005}-3' (16 nt)",
            "current_improved": f"5'-{UNIVERSAL_REVERSE}-3' (20 nt)",
            "improvement": "Extended by 4 nt to improve sensitivity vs. the 16-nt original. Confirmed by Kramer 2011.",
            "mechanism": "During PCR, this primer anneals within the stem-loop body of the cDNA and unfolds the hairpin structure as polymerase extends.",
        },
        "note": "This primer is universal — the same sequence works for ALL miRNA assays using this stem-loop system.",
    }


def _check_self_structure(sequence: str, params: dict) -> dict:
    """
    Hairpin and self-dimer check for the universal reverse primer under PCR conditions.
    Fixed sequence — result cached per unique buffer conditions (lru_cache on inner func).
    """
    p3 = _get_p3_params(params)
    return _check_self_structure_cached(
        sequence, p3["mv_conc"], p3["dv_conc"], p3["dntp_conc"], p3["dna_conc"]
    )


@lru_cache(maxsize=32)
def _check_self_structure_cached(
    sequence: str, mv_conc: float, dv_conc: float, dntp_conc: float, dna_conc: float
) -> dict:
    """Inner cached call — keyed on buffer primitives. maxsize=32 covers all realistic buffer combos."""
    kw = dict(mv_conc=mv_conc, dv_conc=dv_conc, dntp_conc=dntp_conc, dna_conc=dna_conc)

    hp_error = False
    try:
        hp_dg = round(float(primer3.calc_hairpin(seq=sequence, **kw).dg) / 1000, 2)
    except Exception:
        hp_dg = None
        hp_error = True

    sd_error = False
    try:
        sd_dg = round(float(primer3.calc_homodimer(seq=sequence, **kw).dg) / 1000, 2)
    except Exception:
        sd_dg = None
        sd_error = True

    # Use named constants so thresholds stay in sync with structure_check module.
    # HAIRPIN_DG_MAX_INTERNAL = -3.0, HAIRPIN_DG_MAX_3PRIME = -2.0
    # SELF_DIMER_DG_MAX = -6.0, SELF_DIMER_DG_3PRIME_MAX = -5.0
    if hp_error:
        hp_risk = "unknown"
    else:
        hp_risk = "critical" if hp_dg <= HAIRPIN_DG_MAX_INTERNAL else "warning" if hp_dg <= HAIRPIN_DG_MAX_3PRIME else "safe"

    if sd_error:
        sd_risk = "unknown"
    else:
        sd_risk = "critical" if sd_dg <= SELF_DIMER_DG_MAX else "warning" if sd_dg <= SELF_DIMER_DG_3PRIME_MAX else "safe"

    return {
        "hairpin_dg": hp_dg,
        "hairpin_risk": hp_risk,
        "self_dimer_dg": sd_dg,
        "self_dimer_risk": sd_risk,
        "any_issue": hp_risk not in ("safe", "unknown") or sd_risk not in ("safe", "unknown"),
        "calculation_error": hp_error or sd_error,
    }
