"""Pair model of the cross-reactivity matrix (crossreactivity/model.py)."""

import random

import pytest

from crossreactivity.model import Assay, AssayScorer, level_for, load_config, load_mature

CFG = load_config()
MATURE = load_mature(CFG["mirbase_index_path"], "hsa")
NONE_AT = CFG["levels"]["low_below_delta_cq"]


def scorer(name, overhang=6, fwd_len=14):
    return AssayScorer(Assay(name, MATURE[name], overhang, fwd_len, "", ""), CFG)


def test_diagonal_is_one_and_high():
    for name in ("hsa-let-7a-5p", "hsa-miR-21-5p", "hsa-miR-200c-3p"):
        rec = scorer(name).score(name, MATURE[name])
        assert rec["R"] == 1.0 and rec["level"] == "HIGH"
        assert rec["p_RT"] == 1.0 and rec["p_PCR"] == 1.0


def test_r_is_product_of_steps():
    rec = scorer("hsa-let-7a-5p").score("hsa-let-7c-5p", MATURE["hsa-let-7c-5p"])
    assert rec["R"] == pytest.approx(rec["p_RT"] * rec["p_PCR"])
    # let-7a assay on let-7c: rG·dT at RT position 3 → 2^-4.75 ≈ 3.7 % [Chen 2005]
    assert rec["p_RT"] == pytest.approx(2 ** -4.75)


def test_same_overhang_paralog_is_high():
    # let-7a vs let-7d: identical 3' 6 nt, difference at nt 1 and 16 (blind spot)
    rec = scorer("hsa-let-7a-5p").score("hsa-let-7d-5p", MATURE["hsa-let-7d-5p"])
    assert rec["level"] == "HIGH" and rec["rt_mismatches"] == 0


def test_matrix_is_asymmetric():
    a, b = "hsa-miR-17-5p", "hsa-miR-20a-5p"
    ab = scorer(a).score(b, MATURE[b])["R"]
    ba = scorer(b).score(a, MATURE[a])["R"]
    assert ab != ba


def test_unrelated_pair_is_none_with_zero_r():
    rec = scorer("hsa-let-7a-5p").score("hsa-miR-21-5p", MATURE["hsa-miR-21-5p"])
    assert rec["level"] == "NONE" and rec["R"] == 0.0


@pytest.mark.parametrize("dcq,level", [(0, "HIGH"), (3.29, "HIGH"), (3.3, "MEDIUM"),
                                       (4.3, "LOW"), (9.99, "LOW"), (10, "NONE")])
def test_level_cut_offs(dcq, level):
    assert level_for(dcq, CFG["levels"]) == level


def test_screen_is_a_lower_bound():
    """The screen drops a pair only when its Tm-free ΔCq is ≥ the NONE cut-off; that
    is safe only if the Tm-free ΔCq never exceeds the exact one."""
    rng = random.Random(7)
    names = sorted(MATURE)
    for a in rng.sample(names, 6):
        s = scorer(a)
        for t in rng.sample(names, 150) + [a]:
            lb = s.lower_bound(MATURE[t])
            assert lb <= s.score(t, MATURE[t], with_dg=False)["delta_cq"] + 1e-9


FAMILIES = {
    "let-7": ["hsa-let-7a-5p", "hsa-let-7b-5p", "hsa-let-7c-5p", "hsa-let-7d-5p",
              "hsa-let-7e-5p", "hsa-let-7f-5p", "hsa-let-7g-5p", "hsa-let-7i-5p",
              "hsa-miR-98-5p"],
    "miR-17": ["hsa-miR-17-5p", "hsa-miR-20a-5p", "hsa-miR-20b-5p", "hsa-miR-106a-5p",
               "hsa-miR-106b-5p", "hsa-miR-93-5p"],
    "miR-200bc/429": ["hsa-miR-200b-3p", "hsa-miR-200c-3p", "hsa-miR-429"],
    "miR-30": ["hsa-miR-30a-5p", "hsa-miR-30b-5p", "hsa-miR-30c-5p", "hsa-miR-30d-5p",
               "hsa-miR-30e-5p"],
}


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_screen_keeps_every_known_family_pair_it_should(family):
    """No family pair the exact model scores above NONE is dropped by the screen."""
    ms = FAMILIES[family]
    for a in ms:
        s = scorer(a)
        for t in ms:
            exact = s.score(t, MATURE[t], with_dg=False)
            if exact["level"] != "NONE":
                assert s.lower_bound(MATURE[t]) < NONE_AT, (a, t)


def test_family_pairs_score_above_random_pairs():
    """Sanity: 1–2 nt family paralogues score far above random unrelated pairs."""
    fam = []
    for ms in FAMILIES.values():
        for a in ms:
            s = scorer(a)
            fam += [s.score(t, MATURE[t], with_dg=False)["R"] for t in ms if t != a]
    rng = random.Random(3)
    names = sorted(MATURE)
    rnd = []
    for a in rng.sample(names, 20):
        s = scorer(a)
        rnd += [s.score(t, MATURE[t], with_dg=False)["R"] for t in rng.sample(names, 50) if t != a]
    assert sum(fam) / len(fam) > 50 * (sum(rnd) / len(rnd))


def test_dg_columns_are_reported_and_flagged_approximate():
    rec = scorer("hsa-let-7a-5p").score("hsa-let-7c-5p", MATURE["hsa-let-7c-5p"])
    assert rec["approx_hybrid"] is True
    assert rec["dG_rt"] is not None and rec["dG_pcr"] is not None


def test_overhang_length_is_taken_from_the_assay():
    s5 = scorer("hsa-let-7a-5p", overhang=5).score("hsa-let-7c-5p", MATURE["hsa-let-7c-5p"])
    s7 = scorer("hsa-let-7a-5p", overhang=7).score("hsa-let-7c-5p", MATURE["hsa-let-7c-5p"])
    # the G·T sits at position 3 from the 3' terminus of the 6-nt overhang;
    # shorter/longer overhangs move it to positions 2 and 4
    assert s5["p_RT"] != s7["p_RT"]
