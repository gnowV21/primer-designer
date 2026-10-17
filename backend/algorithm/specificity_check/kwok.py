"""
kwok.py — position-weighted mismatch distance, anchored to the PRIMER 3' terminus.

[Kwok90] Kwok S et al. Nucleic Acids Res 1990;18(4):999-1005 — a mismatch at or near
the primer 3' terminus blocks polymerase extension; a mismatch near the primer 5' end
is largely tolerated.

Geometry note (this is the whole point of the module):
  The weight index MUST be counted from the primer's 3' terminus, not from the miRNA's
  3' end. For the two primer classes in stem-loop RT-qPCR these map to OPPOSITE ends of
  the miRNA window:

    RT primer  = revcomp(mature[-N:])      -> primer 3' terminus pairs with window[0]
                                              (the 5'-most nt of the 3' overhang window)
    FWD primer = mature[:L] (same sense)   -> primer 3' terminus is window[L-1]
                                              (the 3'-most nt of the 5' prefix window)
"""

from ..constants import KWOK_POSITION_WEIGHTS

PRIMER_3P_AT_WINDOW_START = "window_start"   # RT primer
PRIMER_3P_AT_WINDOW_END = "window_end"       # forward primer


def kwok_weighted_distance(a: str, b: str, primer_3prime_at: str) -> float:
    """
    Position-weighted mismatch distance between two equal-length windows.

    Args:
        a, b: equal-length sequence windows (same alphabet, same orientation).
        primer_3prime_at: PRIMER_3P_AT_WINDOW_START (RT) or
                          PRIMER_3P_AT_WINDOW_END (forward).

    Returns 0.0 when lengths differ (caller must handle that case explicitly).
    Higher value = mismatches sit closer to the primer 3' terminus = better
    discrimination = LESS likely to co-amplify.
    """
    if primer_3prime_at == PRIMER_3P_AT_WINDOW_START:
        pairs = enumerate(zip(a, b))
    elif primer_3prime_at == PRIMER_3P_AT_WINDOW_END:
        pairs = enumerate(zip(reversed(a), reversed(b)))
    else:
        raise ValueError(
            f"primer_3prime_at must be {PRIMER_3P_AT_WINDOW_START!r} or "
            f"{PRIMER_3P_AT_WINDOW_END!r}, got {primer_3prime_at!r}."
        )

    if len(a) != len(b):
        return 0.0

    total = 0.0
    for i, (c1, c2) in pairs:
        if c1 != c2:
            total += KWOK_POSITION_WEIGHTS[i] if i < len(KWOK_POSITION_WEIGHTS) else 1.0
    return total
