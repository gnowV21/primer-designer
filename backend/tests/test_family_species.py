# ================================================================
# tests/test_family_species.py
# A3 — Species expansion acceptance tests.
#
# The family DB (mirbase_family_overhangs.json) must now cover hsa + mmu + rno,
# and cross-reactivity analysis must be SCOPED to a single species: a same-family
# ortholog in another organism is NOT an off-target for a single-species sample
# (consistent with the BLAST cross_species_excluded logic).
# ================================================================

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.specificity_check.family_crossreactivity import (
    check_family_crossreactivity,
    _load_db,
    _resolve_species_prefix,
    get_family_id,
)

DEFAULT_PARAMS = {
    "saltConcentration": 50.0,
    "magnesiumConcentration": 1.5,
    "dntpTotal": 0.8,
    "primerConcentration": 200.0,
}

LET7A_SEQ = "UGAGGUAGUAGGUUGUAUAGUU"   # 22 nt — identical across hsa/mmu/rno let-7a-5p


# ── Acceptance: multi-species family DB loaded ────────────────────

def test_let7a_family_loaded_from_miFam():
    """
    The let-7 family must contain let-7a-5p for BOTH human (hsa) and mouse (mmu)
    after the A3 multi-species rebuild. (Kept the spec's name; grouping is
    seed-based, miFam.dat having been removed from miRBase CURRENT.)
    """
    assert get_family_id("hsa-let-7a-5p") == "let-7"
    assert get_family_id("mmu-let-7a-5p") == "let-7"

    db = _load_db()
    members = db.get("let-7", {})
    assert "hsa-let-7a-5p" in members
    assert "mmu-let-7a-5p" in members


def test_family_db_covers_mouse_and_rat():
    """Index must contain mmu- and rno- entries, not only hsa-."""
    index = _load_db().get("_mirna_to_family", {})
    prefixes = {name.split("-")[0] for name in index}
    assert {"hsa", "mmu", "rno"}.issubset(prefixes)


# ── Species scoping ───────────────────────────────────────────────

def test_human_query_excludes_cross_species_siblings():
    """hsa query → only hsa siblings; mmu/rno orthologs excluded and counted."""
    res = check_family_crossreactivity(LET7A_SEQ, "hsa-let-7a-5p", DEFAULT_PARAMS, 6)
    assert res["species"] == "hsa"
    assert all(s["sibling"].startswith("hsa-") for s in res["cross_reactivity"])
    assert res["cross_species_excluded"] > 0


def test_mouse_query_scopes_to_mouse():
    """mmu query → only mmu siblings."""
    res = check_family_crossreactivity(LET7A_SEQ, "mmu-let-7a-5p", DEFAULT_PARAMS, 6)
    assert res["species"] == "mmu"
    assert all(s["sibling"].startswith("mmu-") for s in res["cross_reactivity"])


def test_species_prefix_resolution_priority():
    """miRNA name prefix is authoritative; form species is the no-name fallback."""
    assert _resolve_species_prefix("hsa-let-7a-5p") == "hsa-"
    assert _resolve_species_prefix("mmu-let-7a-5p") == "mmu-"
    # nameless sequence → form species override ('human'|'mouse'|'rat' or prefix)
    assert _resolve_species_prefix("", "mouse") == "mmu-"
    assert _resolve_species_prefix("", "rat") == "rno-"
    assert _resolve_species_prefix("", None) == "hsa-"
    # name prefix wins even if a conflicting form species is passed
    assert _resolve_species_prefix("hsa-let-7a-5p", "mouse") == "hsa-"


def test_nameless_sequence_returns_no_family_gracefully():
    """
    Family lookup is name-based: a sequence pasted without a miRNA name cannot
    locate its family, so cross-reactivity is not assessed (graceful no-family
    result, no crash). Species scoping is therefore driven by the name prefix;
    the form `species` is only a defensive fallback once a family is found.
    """
    res = check_family_crossreactivity(LET7A_SEQ, "", DEFAULT_PARAMS, 6, species="mouse")
    assert res["family"] is None
    assert res["cross_reactivity"] == []
