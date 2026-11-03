"""
test_kwok.py — primer-anchored Kwok geometry (SPEC_week2 C1).

The weight index is counted from the PRIMER 3' terminus. For stem-loop RT-qPCR the two
primer classes anchor at OPPOSITE ends of the miRNA window:
  RT primer  (revcomp of the 3' overhang)  -> 3' terminus at window START -> index 0 = window[0]
  FWD primer (5' prefix, same sense)        -> 3' terminus at window END   -> index 0 = window[-1]

Ground-truth vectors are the real let-7a windows (verified against backend/db/mirbase.db,
2658 hsa mature): let-7a 3'-6mer = ATAGTT, 5'-12mer = TGAGGTAGTAGG.
"""
import pytest

from algorithm.specificity_check.kwok import (
    kwok_weighted_distance,
    PRIMER_3P_AT_WINDOW_START,
    PRIMER_3P_AT_WINDOW_END,
)
from algorithm.constants import KWOK_POSITION_WEIGHTS


# ── basic geometry ────────────────────────────────────────────────

def test_perfect_match_is_zero():
    assert kwok_weighted_distance("ATAGTT", "ATAGTT", PRIMER_3P_AT_WINDOW_START) == 0.0
    assert kwok_weighted_distance("ATAGTT", "ATAGTT", PRIMER_3P_AT_WINDOW_END) == 0.0


def test_window_start_weights_first_char_highest():
    # RT axis: mismatch at window[0] (5'-most nt of overhang) = primer 3' terminus.
    assert kwok_weighted_distance("ATAGTT", "GTAGTT", PRIMER_3P_AT_WINDOW_START) == KWOK_POSITION_WEIGHTS[0]
    # mismatch at window[-1] is far from the RT primer 3' terminus -> weight 1.0
    assert kwok_weighted_distance("ATAGTT", "ATAGTA", PRIMER_3P_AT_WINDOW_START) == KWOK_POSITION_WEIGHTS[5]


def test_window_end_weights_last_char_highest():
    # FWD axis: mismatch at window[-1] (3'-most nt of prefix) = primer 3' terminus.
    assert kwok_weighted_distance("ATAGTT", "ATAGTA", PRIMER_3P_AT_WINDOW_END) == KWOK_POSITION_WEIGHTS[0]
    assert kwok_weighted_distance("ATAGTT", "GTAGTT", PRIMER_3P_AT_WINDOW_END) == KWOK_POSITION_WEIGHTS[5]


def test_two_axes_are_mirror_images():
    a, b = "ATAGTT", "GTAGTA"  # mismatches at both ends
    start = kwok_weighted_distance(a, b, PRIMER_3P_AT_WINDOW_START)
    end = kwok_weighted_distance(a, b, PRIMER_3P_AT_WINDOW_END)
    # 4.0 + 1.0 either way, but each end weights the opposite terminus
    assert start == KWOK_POSITION_WEIGHTS[0] + KWOK_POSITION_WEIGHTS[5]
    assert end == KWOK_POSITION_WEIGHTS[5] + KWOK_POSITION_WEIGHTS[0]


def test_unequal_length_returns_zero():
    assert kwok_weighted_distance("ATAG", "ATAGTT", PRIMER_3P_AT_WINDOW_START) == 0.0


def test_invalid_anchor_raises():
    with pytest.raises(ValueError):
        kwok_weighted_distance("ATAGTT", "ATAGTT", "somewhere")


# ── RT-axis ground truth: real let-7a 3'-overhang windows (mirbase.db) ──
# target let-7a 3'-6mer = ATAGTT; expected values are SPEC_week2 §1.1.
_LET7A_RT = [
    ("let-7b", "GTGGTT", 5.5),   # mismatch at window[0] and window[2]
    ("let-7c", "ATGGTT", 1.5),   # single mismatch at window[2]
    ("let-7g", "ACAGTT", 2.0),   # single mismatch at window[1]
    ("let-7i", "GCTGTT", 7.5),   # mismatches at window[0], [1], [2]
    ("let-7d", "ATAGTT", 0.0),   # identical overhang
]


@pytest.mark.parametrize("name,window,expected", _LET7A_RT)
def test_rt_axis_let7a_ground_truth(name, window, expected):
    got = kwok_weighted_distance("ATAGTT", window, PRIMER_3P_AT_WINDOW_START)
    assert got == expected, f"{name}: RT-axis kwok {got} != expected {expected}"


# ── FWD-axis ground truth: real let-7a 5'-prefix windows (mirbase.db) ──
# target let-7a 5'-12mer = TGAGGTAGTAGG. A mismatch at the forward primer 3' terminus
# (window END, position 12) discriminates; one at the 5' end (position 1) is tolerated.
def test_fwd_axis_mismatch_at_3prime_terminus_discriminates():
    # let-7f 5'-12mer differs only at position 12 (window END) -> primer 3' terminus.
    assert kwok_weighted_distance("TGAGGTAGTAGG", "TGAGGTAGTAGA", PRIMER_3P_AT_WINDOW_END) == KWOK_POSITION_WEIGHTS[0]


def test_fwd_axis_mismatch_at_5prime_end_is_tolerated():
    # let-7d 5'-12mer differs only at position 1 (window START) -> far from primer 3' terminus.
    assert kwok_weighted_distance("TGAGGTAGTAGG", "AGAGGTAGTAGG", PRIMER_3P_AT_WINDOW_END) == KWOK_POSITION_WEIGHTS[5]
