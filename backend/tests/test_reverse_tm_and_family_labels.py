# Decisions of 2026-11-23 (docs/REVIEW_ui_polish_2026-11.md, "Decisions"):
#  - universal_reverse.tm is the primer3 Tm at the request conditions (the value the
#    tiered ranking uses); V4 keeps the fixed legacy 60.4 °C so its scores do not change.
#  - family labels are name prefixes that end at a name boundary (no cut numbers).
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.constants import UNIVERSAL_REVERSE, V4_REVERSE_TM_LEGACY
from algorithm.scoring import score_candidate
from algorithm.thermodynamics import calculate_tm_nn
from algorithm.universal_reverse import get_universal_reverse
from scripts.build_mirbase_data import OUTPUT_PATH, _derive_family_label, relabel_family_db
from tests.test_gc_clamp import _make_forward

_STEMLOOP = {"mfe": -11.5, "mfe_method": "primer3-py", "gc_percent": 55, "tm_full": 70.0}


# ── Reverse-primer Tm ────────────────────────────────────────────

def test_reverse_tm_is_computed_at_the_request_conditions():
    assert get_universal_reverse({})["tm"] == round(calculate_tm_nn(UNIVERSAL_REVERSE, {}), 2) == 62.93
    high_mg = {"magnesiumConcentration": 3.0}
    assert get_universal_reverse(high_mg)["tm"] == round(calculate_tm_nn(UNIVERSAL_REVERSE, high_mg), 2)
    assert get_universal_reverse(high_mg)["tm"] != 62.93


def test_v4_tm_pair_match_uses_the_legacy_constant_not_reverse_tm():
    assert V4_REVERSE_TM_LEGACY == 60.4
    fwd = _make_forward("ACG")
    a = score_candidate(fwd, _STEMLOOP, {"tm": 60.4}, {}, cross_reactivity=None, use_v4=True)
    b = score_candidate(fwd, _STEMLOOP, {"tm": 62.93}, {}, cross_reactivity=None, use_v4=True)
    assert a["scores"]["tm_pair_match"] == b["scores"]["tm_pair_match"]
    assert a["total_score"] == b["total_score"]


# ── Family labels ────────────────────────────────────────────────

def test_label_does_not_cut_a_number():
    # miR-15a / miR-16 / miR-195 share only "miR-1", which is a cut number
    assert _derive_family_label("AGCAGCA", ["hsa-miR-15a-5p", "hsa-miR-15b-5p", "hsa-miR-16-5p",
                                            "hsa-miR-195-5p"]) == "miR-15"
    assert _derive_family_label("AAAGUGC", ["hsa-miR-17-5p", "hsa-miR-93-5p"]) == "seed_AAAGUGC"
    assert _derive_family_label("GAGGUAG", ["hsa-let-7a-5p", "hsa-let-7b-5p", "hsa-miR-98-5p"]) == "let-7"
    assert _derive_family_label("GGAAUGU", ["hsa-miR-1-3p", "mmu-miR-1a-3p", "hsa-miR-206"]) == "miR-1"


def _strip(n):
    return re.sub(r"-(5p|3p)$", "", re.sub(r"^[a-z]{2,4}-", "", n))


def test_family_data_labels_are_real_name_prefixes_and_groups_unchanged():
    db = json.load(open(OUTPUT_PATH, encoding="utf-8"))
    for label, members in ((k, v) for k, v in db.items() if not k.startswith("_")):
        base = label.split("_")[0]
        if base == "seed":
            continue
        names = [_strip(m) for m in members]
        assert any(s == base or (s.startswith(base) and not s[len(base)].isdigit()) for s in names), label
    # relabelling the committed file again changes nothing (the file is the rule's output)
    assert relabel_family_db(db)["_mirna_to_family"] == db["_mirna_to_family"]
    idx = db["_mirna_to_family"]
    assert idx["hsa-miR-16-5p"] == idx["hsa-miR-15a-5p"] == "miR-15"
    assert idx["hsa-miR-92a-3p"] != "miR-3"
    assert idx["hsa-let-7a-5p"] == "let-7"


def test_unindexed_mirna_has_no_family():
    """No name-substring fallback: hsa-miR-662 is in no seed group, so it has no family
    (before 2026-11-23 the label "miR-6" matched it and gave it unrelated siblings)."""
    from algorithm.specificity_check.family_crossreactivity import _find_family, _load_db
    db = _load_db()
    assert "hsa-miR-662" not in db["_mirna_to_family"]
    assert _find_family(db, "hsa-miR-662", "UCCCACGUUGUGGCCCAGCAG") == (None, {})
    fam, sibs = _find_family(db, "hsa-miR-16-5p", "UAGCAGCACGUAAAUAUUGGCG")
    assert fam == "miR-15" and "hsa-miR-15a-5p" in sibs
