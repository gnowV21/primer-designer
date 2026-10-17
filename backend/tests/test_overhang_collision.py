"""
test_overhang_collision.py — dual-axis primer collision (SPEC_week2 C4 / §1.4).

Ground-truth vectors are computed from backend/db/mirbase.db (2658 hsa mature) and MUST
NOT be edited. The full-index scan legitimately reports colliders beyond the illustrative
let-7 table (e.g. miR-98, a bona-fide let-7 family member), so tests assert the named
ground-truth entries exactly rather than an exhaustive count.
"""
import time

import pytest

from algorithm.specificity_check.overhang_collision import check_overhang_collision
from algorithm.specificity_check.family_crossreactivity import check_family_crossreactivity


# ── Fixture A — hsa-let-7a-5p, overhang 6, L_spec = 12 (SPEC_week2 §1.4) ──

_LET7A = "UGAGGUAGUAGGUUGUAUAGUU"
# name -> (rt_mismatch, fwd_mismatch, fwd_positions_1based, combined_risk)
_LET7A_GROUND_TRUTH = {
    "hsa-let-7d-5p": (0, 1, [1], "CRITICAL"),
    "hsa-let-7e-5p": (0, 1, [9], "CRITICAL"),
    "hsa-let-7f-5p": (0, 1, [12], "LOW"),
    "hsa-let-7b-5p": (2, 0, [], "LOW"),
    "hsa-let-7c-5p": (1, 0, [], "CRITICAL"),
    "hsa-let-7g-5p": (1, 1, [12], "LOW"),
}


@pytest.fixture(scope="module")
def let7a_result():
    return check_overhang_collision(_LET7A, "hsa-let-7a-5p", {}, forward_specific_len=12)


@pytest.mark.parametrize("name,expected", _LET7A_GROUND_TRUTH.items())
def test_let7a_ground_truth(let7a_result, name, expected):
    by = {e["mirna"]: e for e in let7a_result["collisions"]}
    assert name in by, f"{name} not reported"
    e = by[name]
    rt_mm, fwd_mm, fwd_pos, combined = expected
    assert e["rt_mismatch"] == rt_mm
    assert e["fwd_mismatch"] == fwd_mm
    assert e["fwd_mismatch_positions_1based"] == fwd_pos
    assert e["combined_risk"] == combined, f"{name}: {e['combined_risk']} != {combined}"


def test_let7i_is_safe_and_not_reported(let7a_result):
    # let-7i overhang GCTGTT (rt_mm=3 → SAFE) → below reporting threshold.
    assert "hsa-let-7i-5p" not in {e["mirna"] for e in let7a_result["collisions"]}


def test_let7a_worst_and_gate(let7a_result):
    # SPEC §7.3 gate #1: let-7c CRITICAL, let-7b LOW.
    assert let7a_result["worst_combined_risk"] == "CRITICAL"
    by = {e["mirna"]: e for e in let7a_result["collisions"]}
    assert by["hsa-let-7c-5p"]["combined_risk"] == "CRITICAL"
    assert by["hsa-let-7b-5p"]["combined_risk"] == "LOW"


def test_let7b_rt_is_sole_discriminator(let7a_result):
    # Same seed, forward identical (fwd_mm=0) — only the RT axis (2 mismatches) saves it.
    e = {x["mirna"]: x for x in let7a_result["collisions"]}["hsa-let-7b-5p"]
    assert e["fwd_mismatch"] == 0 and e["rt_mismatch"] == 2
    assert e["same_seed_family"] is True


# ── Fixture B — hsa-miR-503-5p, bucket CTGCAG (SPEC_week2 §1.4) ──

_MIR503 = "UAGCAGCGGGAACAGUUCUGCAG"
_CTGCAG_COLLIDERS = [
    "hsa-miR-4722-3p", "hsa-miR-4742-3p", "hsa-miR-6510-3p",
    "hsa-miR-6744-3p", "hsa-miR-6788-3p",
]


@pytest.fixture(scope="module")
def mir503_result():
    return check_overhang_collision(_MIR503, "hsa-miR-503-5p", {}, forward_specific_len=12)


def test_mir503_rt_identical_colliders_reported_as_safe(mir503_result):
    assert mir503_result["summary"]["rt_identical"] >= 5
    assert mir503_result["summary"]["CRITICAL"] == 0
    assert mir503_result["worst_combined_risk"] == "SAFE"
    by = {e["mirna"]: e for e in mir503_result["collisions"]}
    for name in _CTGCAG_COLLIDERS:
        assert name in by, f"{name} (rt-identical) must still be reported"
        assert by[name]["rt_mismatch"] == 0
        assert by[name]["combined_risk"] == "SAFE"
        assert by[name]["same_seed_family"] is False


def test_seed_map_misses_rt_axis_colliders():
    """The seed-based family map flags NONE of the CTGCAG RT-axis colliders — direct
    proof that seed grouping is blind to the RT primer-binding axis."""
    fam = check_family_crossreactivity(_MIR503, "hsa-miR-503-5p", {})
    flagged = {e.get("sibling") for e in fam.get("cross_reactivity", [])}
    assert flagged.isdisjoint(set(_CTGCAG_COLLIDERS)), (
        f"seed map unexpectedly flagged {flagged & set(_CTGCAG_COLLIDERS)}"
    )


# ── Fixture C — hsa-miR-21-5p (SPEC_week2 §1.4) ──

def test_mir21_all_safe():
    r = check_overhang_collision("UAGCUUAUCAGACUGAUGUUGA", "hsa-miR-21-5p", {}, forward_specific_len=12)
    assert r["worst_combined_risk"] == "SAFE"
    assert r["summary"]["CRITICAL"] == 0


# ── performance ──────────────────────────────────────────────────

def test_scan_is_fast():
    t0 = time.perf_counter()
    check_overhang_collision(_LET7A, "hsa-let-7a-5p", {}, forward_specific_len=12)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.2, f"full hsa scan took {elapsed*1000:.0f} ms (target < 50 ms warm)"
