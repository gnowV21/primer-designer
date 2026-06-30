# ================================================================
# universal_reverse.py — Module 3: Universal reverse primer
# Fixed sequence — no design needed. Return constants only.
# ================================================================

import primer3
from .constants import (
    UNIVERSAL_REVERSE, UNIVERSAL_REVERSE_TM_PRECALC,
    UNIVERSAL_REVERSE_GC_PRECALC, UNIVERSAL_REVERSE_CHEN_2005,
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
    Fixed sequence — computed once per request (PCR buffer may vary per user params).
    """
    p3 = _get_p3_params(params)
    kw = dict(mv_conc=p3["mv_conc"], dv_conc=p3["dv_conc"],
              dntp_conc=p3["dntp_conc"], dna_conc=p3["dna_conc"])

    try:
        hp_dg = round(float(primer3.calc_hairpin(seq=sequence, **kw).dg) / 1000, 2)
    except Exception:
        hp_dg = 0.0

    try:
        sd_dg = round(float(primer3.calc_homodimer(seq=sequence, **kw).dg) / 1000, 2)
    except Exception:
        sd_dg = 0.0

    hp_risk = "critical" if hp_dg <= -3.0 else "warning" if hp_dg <= -2.0 else "safe"
    sd_risk = "critical" if sd_dg <= -6.0 else "warning" if sd_dg <= -4.0 else "safe"

    return {
        "hairpin_dg": hp_dg,
        "hairpin_risk": hp_risk,
        "self_dimer_dg": sd_dg,
        "self_dimer_risk": sd_risk,
        "any_issue": hp_risk != "safe" or sd_risk != "safe",
    }
