"""
test_v4_382_fixes.py — algorithm 3.8.2 fixes to V4 (AUDIT REV-21, §10.5).

REV-21: hard-filter rule 2 is the Primer3 3'-anchored dimer Tm (PRIMER_MAX_SELF_END_TH /
PRIMER_PAIR_MAX_COMPL_END_TH, 47 °C). The old rule (ΔG of the last 8 nt ≤ −5 kcal/mol)
never fired on 168,929 hsa gate candidates.

end_stability: Primer3's definition (ΔG to disrupt the last 5 bases as a perfect duplex,
SantaLucia 1998). The old code folded the 5-mer as a hairpin and always returned 0.00.
"""
import itertools

import pytest

from algorithm.constants import END_DIMER_TM_HARD_MAX, END_STABILITY_MAX, UNIVERSAL_REVERSE
from algorithm.hard_filters import apply_hard_filters
from algorithm.structure_check import run_all_structure_checks
from algorithm.thermodynamics import calculate_end_stability

# hsa-miR-17-3p candidate (3.8.1 pool): its 3' end CTGCAGTGAAG pairs with itself
# (PstI-like palindrome CTGCAG) — self 3'-end dimer Tm 53.4 °C.
_SELF_END = "TCCGCTTCACTGCAGTGAAG"
# hsa-miR-21-5p #1 of 3.8.1 — no 3'-anchored dimer.
_CLEAN = "ACCGCCTAGCTTATCAGACTGA"


def _checks(seq):
    return run_all_structure_checks(seq, UNIVERSAL_REVERSE, {})


def test_self_end_dimer_tm_flags_critical():
    sc = _checks(_SELF_END)
    assert sc["self_dimer"]["end_tm"] >= END_DIMER_TM_HARD_MAX
    assert sc["self_dimer"]["critical_3prime"] is True
    assert sc["has_critical_flag"] is True
    assert "hard_dimer_3prime_critical" in apply_hard_filters({"structure_checks": sc})


def test_clean_primer_not_flagged():
    sc = _checks(_CLEAN)
    assert sc["self_dimer"]["end_tm"] < END_DIMER_TM_HARD_MAX
    assert sc["hetero_dimer"]["end_tm"] < END_DIMER_TM_HARD_MAX
    assert sc["has_critical_flag"] is False
    assert "hard_dimer_3prime_critical" not in apply_hard_filters({"structure_checks": sc})


def test_end_tm_is_json_safe():
    sc = _checks(_CLEAN)
    for k in ("self_dimer", "hetero_dimer"):
        v = sc[k]["end_tm"]
        assert v is None or (isinstance(v, float) and v == v and abs(v) != float("inf"))


@pytest.mark.parametrize("five, expected", [
    # hand sums of SantaLucia 1998 NN ΔG37 + init 1.96 (+0.05 per terminal A·T)
    ("GCGCG", 6.86),   # 2.24 + 2.17 + 2.24 + 2.17 − 1.96
    ("AAAAA", 1.94),   # 4 × 1.00 − 1.96 − 0.10
    ("CAGAC", 3.51),   # CA 1.45 + AG 1.28 + GA 1.30 + AC 1.44 − 1.96
])
def test_end_stability_primer3_definition(five, expected):
    assert calculate_end_stability(five, {}) == pytest.approx(expected, abs=0.005)


def test_end_stability_never_reaches_the_primer3plus_limit():
    worst = max(calculate_end_stability("".join(p), {})
                for p in itertools.product("ACGT", repeat=5))
    assert worst == pytest.approx(6.86, abs=0.005)
    assert worst < END_STABILITY_MAX


def test_end_stability_no_longer_zero():
    assert _checks(_CLEAN)["end_stability"]["stability_kcal_mol"] > 0
