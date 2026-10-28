"""
test_overhang_collision.py — assay-level ΔCq screen (2026-10-29; Week 2 SPEC_week2 C4 / §1.4).

Mismatch vectors are computed from backend/db/mirbase.db (2658 hsa mature) and MUST
NOT be edited. The labels are the ΔCq model's output (assay_model.py) and change when
its literature values do.
"""
import time

import pytest

from algorithm.specificity_check.overhang_collision import check_overhang_collision
from algorithm.specificity_check.family_crossreactivity import check_family_crossreactivity


# ── Fixture A — hsa-let-7a-5p, overhang 6, L_spec = 12 (SPEC_week2 §1.4) ──

_LET7A = "UGAGGUAGUAGGUUGUAUAGUU"
# name -> (rt_mismatch, fwd_mismatch, fwd_positions_1based)
_LET7A_GROUND_TRUTH = {
    "hsa-let-7d-5p": (0, 1, [1]),
    "hsa-let-7e-5p": (0, 1, [9]),
    "hsa-let-7f-5p": (0, 1, [12]),
}
# let-7b/c/g/i are resolved by the RT overhang alone: not reported, no forward evaluation.
_LET7A_LABELS = {
    "hsa-let-7d-5p": "CO-AMPLIFIED",   # differs at nt 1 and nt 16 — nt 16 lies outside both primer windows
    "hsa-let-7f-5p": "PARTIAL",        # 3'-terminal G–T (minor) + a 5.5 °C weaker duplex
    "hsa-let-7e-5p": "DISCRIMINATED",  # duplex far weaker (stability term capped at 8.3)
}


@pytest.fixture(scope="module")
def let7a_result():
    return check_overhang_collision(_LET7A, "hsa-let-7a-5p", {}, forward_specific_len=12)


@pytest.mark.parametrize("name,expected", _LET7A_GROUND_TRUTH.items())
def test_let7a_mismatch_vectors(let7a_result, name, expected):
    by = {e["mirna"]: e for e in let7a_result["collisions"]}
    assert name in by, f"{name} not reported"
    e = by[name]
    rt_mm, fwd_mm, fwd_pos = expected
    assert e["rt_mismatch"] == rt_mm
    assert e["fwd_mismatch"] == fwd_mm
    assert e["fwd_mismatch_positions_1based"] == fwd_pos


@pytest.mark.parametrize("name,label", _LET7A_LABELS.items())
def test_let7a_assay_labels(let7a_result, name, label):
    by = {e["mirna"]: e for e in let7a_result["collisions"]}
    assert by[name]["assay_label"] == label


def test_let7_rt_resolved_members_not_reported(let7a_result):
    names = {e["mirna"] for e in let7a_result["collisions"]}
    assert names.isdisjoint({"hsa-let-7b-5p", "hsa-let-7c-5p", "hsa-let-7g-5p", "hsa-let-7i-5p"})


def test_let7a_worst_and_family_is_context_only(let7a_result):
    assert let7a_result["worst_assay_label"] == "CO-AMPLIFIED"
    by = {e["mirna"]: e for e in let7a_result["collisions"]}
    assert by["hsa-let-7d-5p"]["same_seed_family"] is True    # reported, never exempted


# ── Fixture B — hsa-miR-503-5p, bucket CTGCAG (SPEC_week2 §1.4) ──

_MIR503 = "UAGCAGCGGGAACAGUUCUGCAG"
_CTGCAG_COLLIDERS = [
    "hsa-miR-4722-3p", "hsa-miR-4742-3p", "hsa-miR-6510-3p",
    "hsa-miR-6744-3p", "hsa-miR-6788-3p",
]


@pytest.fixture(scope="module")
def mir503_result():
    return check_overhang_collision(_MIR503, "hsa-miR-503-5p", {}, forward_specific_len=12)


def test_mir503_rt_identical_colliders_reported_as_discriminated(mir503_result):
    assert mir503_result["summary"]["rt_identical"] >= 5
    assert mir503_result["summary"]["CO-AMPLIFIED"] == 0
    assert mir503_result["worst_assay_label"] == "DISCRIMINATED"
    by = {e["mirna"]: e for e in mir503_result["collisions"]}
    for name in _CTGCAG_COLLIDERS:
        assert name in by, f"{name} (rt-identical) must still be reported"
        assert by[name]["rt_mismatch"] == 0
        assert by[name]["assay_label"] == "DISCRIMINATED"
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

def test_mir21_all_discriminated():
    r = check_overhang_collision("UAGCUUAUCAGACUGAUGUUGA", "hsa-miR-21-5p", {}, forward_specific_len=12)
    assert r["worst_assay_label"] == "DISCRIMINATED"
    assert r["summary"]["CO-AMPLIFIED"] == 0


# ── isomiRs are reported, not scored ─────────────────────────────

def test_isomir_entries_go_to_isomirs_not_worst(monkeypatch):
    import algorithm.specificity_check.overhang_collision as oc
    target = "UAGCUUAUCAGACUGAUGUUGA"
    fake = {"_metadata": {}, "mature": {"hsa": {
        "hsa-miR-21-5p": target,
        "hsa-miR-x-3p": target[:-1],          # 3' isomiR (co-amplified, RT shift −1)
        "hsa-miR-y-5p": target[1:],           # 5' isomiR
        "hsa-miR-z": "UAGCUUAUCAGACUGAUGUUGA"[::-1],
    }}}
    monkeypatch.setattr(oc, "_INDEX_CACHE", fake)
    r = check_overhang_collision(target, "hsa-miR-21-5p", {}, forward_specific_len=15)
    cats = {e["mirna"]: e["category"] for e in r["isomirs"]}
    assert cats == {"hsa-miR-x-3p": "isomir_3p", "hsa-miR-y-5p": "isomir_5p"}
    assert r["summary"]["isomir_3p"] == 1 and r["summary"]["isomir_5p"] == 1
    assert r["worst_assay_label"] == "DISCRIMINATED"          # isomiRs do not drive the score


# ── performance ──────────────────────────────────────────────────

def test_scan_is_fast():
    check_overhang_collision(_LET7A, "hsa-let-7a-5p", {}, forward_specific_len=12)
    t0 = time.perf_counter()
    check_overhang_collision(_LET7A, "hsa-let-7a-5p", {}, forward_specific_len=12)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.3, f"full hsa scan took {elapsed*1000:.0f} ms (target < 100 ms warm)"
