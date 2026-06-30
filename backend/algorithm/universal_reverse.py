# ================================================================
# universal_reverse.py — Module 3: Universal reverse primer
# Fixed sequence — no design needed. Return constants only.
# ================================================================

from .constants import (
    UNIVERSAL_REVERSE, UNIVERSAL_REVERSE_TM_PRECALC,
    UNIVERSAL_REVERSE_GC_PRECALC, UNIVERSAL_REVERSE_CHEN_2005,
)


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
        "design_rationale": {
            "original_chen_2005": f"5'-{UNIVERSAL_REVERSE_CHEN_2005}-3' (16 nt)",
            "current_improved": f"5'-{UNIVERSAL_REVERSE}-3' (20 nt)",
            "improvement": "Extended by 4 nt to improve sensitivity vs. the 16-nt original. Confirmed by Kramer 2011.",
            "mechanism": "During PCR, this primer anneals within the stem-loop body of the cDNA and unfolds the hairpin structure as polymerase extends.",
        },
        "note": "This primer is universal — the same sequence works for ALL miRNA assays using this stem-loop system.",
    }
