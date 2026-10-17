"""
overhang_collision.py — dual-axis primer-binding specificity for stem-loop RT-qPCR
(SPEC_week2 P1 / C4).

Specificity here is the product of two INDEPENDENT primer-binding axes, not the seed:
  * RT axis  — the stem-loop RT primer binds the 3'-terminal `overhang_len` nt of the
               mature miRNA. Its 3' terminus (the discriminating end, [Kwok90]) pairs
               with the 5'-most nt of that window (the RT primer is the reverse complement).
  * FWD axis — the forward qPCR primer binds the 5' prefix; its 3' terminus is the
               3'-most nt of the prefix window.

An off-target is co-amplified only when BOTH axes fail to discriminate. Seed-family
membership (positions 2-8) is the mRNA-targeting axis and is reported for CONTEXT only
(via `same_seed_family`), never used to classify risk.

Screens the full per-species mature index (data/mirbase_overhang_index.json), so it
catches colliders that share a 3' overhang but sit in different seed families — exactly
the case the seed map is blind to.
"""

import json
import os

from ..constants import (
    RT_MM_REPORT_MAX,
    FWD_MM_REPORT_MAX,
    FWD_PREFIX_LEN_FALLBACK,
    COLLISION_MAX_REPORT,
    COMBINED_RISK_MATRIX,
    KWOK_DIST_DISCRIMINATING,
    OVERHANG_LENGTH_DEFAULT,
    OVERHANG_LENGTH_MAX,
    FORWARD_SPECIFIC_LENGTH_MAX,
)
from .kwok import (
    kwok_weighted_distance,
    PRIMER_3P_AT_WINDOW_START,
    PRIMER_3P_AT_WINDOW_END,
)
from .family_crossreactivity import _resolve_species_prefix, get_family_id

_INDEX_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "mirbase_overhang_index.json")
)
_INDEX_CACHE: dict | None = None

_COMP = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}

_OFF_LABEL_WARNING = (
    "Changing from 6 nt may reduce steric hindrance against pri-/pre-miRNA precursors "
    "(Chen et al. 2005)."
)

_RT_RISK_ORDER = {"IDENTICAL": 0, "HIGH": 1, "LOW": 2, "SAFE": 3}
_COMBINED_ORDER = {"CRITICAL": 0, "LOW": 1, "SAFE": 2}


# ── helpers ───────────────────────────────────────────────────────

def _dna(rna: str) -> str:
    return rna.upper().replace("U", "T")


def _revcomp(dna: str) -> str:
    return "".join(_COMP.get(b, "N") for b in reversed(dna))


def _hamming(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b))


def _axis_risk(mismatch: int, kwok: float) -> str:
    if mismatch == 0:
        return "IDENTICAL"
    if mismatch == 1:
        return "LOW" if kwok >= KWOK_DIST_DISCRIMINATING else "HIGH"
    if mismatch == 2:
        return "LOW"
    return "SAFE"


def _load_index() -> dict:
    global _INDEX_CACHE
    if _INDEX_CACHE is not None:
        return _INDEX_CACHE
    with open(_INDEX_PATH, encoding="utf-8") as f:
        _INDEX_CACHE = json.load(f)
    return _INDEX_CACHE


def _evaluate_pair(target_dna: str, other_dna: str, overhang_len: int, fwd_len: int) -> dict:
    """Evaluate both binding axes for one target/collider pair. Pure; reused by the
    main scan and by the recommender's what-if recomputations."""
    # RT axis — 3' overhang window (compare on equal length only).
    t_rt = target_dna[-overhang_len:]
    o_rt = other_dna[-overhang_len:]
    if len(o_rt) < overhang_len:
        rt_mm = overhang_len          # miRNA shorter than the window → treat as fully divergent
        rt_kwok = 0.0
    else:
        rt_mm = _hamming(t_rt, o_rt)
        rt_kwok = kwok_weighted_distance(t_rt, o_rt, PRIMER_3P_AT_WINDOW_START)
    rt_risk = _axis_risk(rt_mm, rt_kwok)

    # FWD axis — 5' prefix window (compare on the overlap when the collider is shorter).
    lc = min(fwd_len, len(other_dna))
    t_fwd = target_dna[:lc]
    o_fwd = other_dna[:lc]
    forward_truncated = len(other_dna) < fwd_len
    fwd_mm = _hamming(t_fwd, o_fwd)
    fwd_positions = [i + 1 for i in range(lc) if t_fwd[i] != o_fwd[i]]
    fwd_kwok = kwok_weighted_distance(t_fwd, o_fwd, PRIMER_3P_AT_WINDOW_END)
    fwd_risk = _axis_risk(fwd_mm, fwd_kwok)

    combined = COMBINED_RISK_MATRIX[(rt_risk, fwd_risk)]
    return {
        "rt_window_dna": o_rt,
        "rt_mismatch": rt_mm,
        "rt_kwok": round(rt_kwok, 2),
        "rt_risk": rt_risk,
        "fwd_window_dna": o_fwd,
        "fwd_mismatch": fwd_mm,
        "fwd_mismatch_positions_1based": fwd_positions,
        "fwd_kwok": round(fwd_kwok, 2),
        "fwd_risk": fwd_risk,
        "forward_truncated": forward_truncated,
        "combined_risk": combined,
    }


# ── recommendation (§1.4) ─────────────────────────────────────────

def _recommend(target_dna, overhang_len, fwd_len, crit_colliders, worst_combined):
    """Only ever suggest a fix the module can VERIFY by recomputation in this response."""
    if worst_combined == "SAFE" or not crit_colliders:
        return {
            "action": "none",
            "reason": "Both primer axes discriminate every co-amplifiable miRNA screened.",
        }

    # 1. Try a longer RT overhang (7, 8) — re-evaluate every CRITICAL collider.
    for n in range(overhang_len + 1, OVERHANG_LENGTH_MAX + 1):
        if all(_evaluate_pair(target_dna, o, n, fwd_len)["combined_risk"] != "CRITICAL"
               for o in crit_colliders):
            return {
                "action": "increase_overhang",
                "suggested_overhang_len": n,
                "off_label_warning": _OFF_LABEL_WARNING,
                "reason": (
                    f"Extending the RT overhang to {n} nt makes every currently-CRITICAL "
                    "collider discriminable on the RT axis (verified by recomputation)."
                ),
            }

    # 2. Try a longer forward specific region — re-evaluate the forward axis.
    for lp in range(fwd_len + 1, FORWARD_SPECIFIC_LENGTH_MAX + 1):
        if all(_evaluate_pair(target_dna, o, overhang_len, lp)["combined_risk"] != "CRITICAL"
               for o in crit_colliders):
            return {
                "action": "increase_forward_specific_len",
                "suggested_forward_specific_len": lp,
                "reason": (
                    f"Extending the forward specific region to {lp} nt places the discriminating "
                    "mismatch within the forward primer 3' end for every CRITICAL collider "
                    "(verified by recomputation)."
                ),
            }

    # 3. Neither axis can be rescued by geometry alone.
    return {
        "action": "orthogonal_assay",
        "reason": (
            "These miRNAs cannot be distinguished by stem-loop RT-qPCR geometry alone: the "
            "RT overhang and the forward primer both fail to discriminate even at their length "
            "limits. Use a hydrolysis (TaqMan) probe spanning the differing region, an LNA-"
            "substituted primer, or an orthogonal method.",
        ),
    }


# ── public entry point ────────────────────────────────────────────

def check_overhang_collision(
    mature_seq: str,
    mirna_name: str,
    params: dict,
    overhang_len: int = 6,
    forward_specific_len: int | None = None,
    species: str | None = None,
    max_report: int = COLLISION_MAX_REPORT,
) -> dict:
    """Dual-axis (RT 3' overhang + forward 5' prefix) collision screen vs the full
    per-species mature index. See module docstring for the science."""
    mature = (mature_seq or "").upper().strip()
    target_dna = _dna(mature)

    fwd_len = forward_specific_len or FWD_PREFIX_LEN_FALLBACK
    forward_axis_estimated = forward_specific_len is None

    prefix = _resolve_species_prefix(mirna_name, species)   # e.g. "hsa-"
    sp = prefix.rstrip("-")

    index = _load_index()
    mature_map = (index.get("mature") or {}).get(sp, {})
    meta = index.get("_metadata", {})
    provenance = {
        "source": meta.get("source"),
        "build_date": meta.get("build_date"),
        "mirbase_release": meta.get("mirbase_release"),
    }

    base = {
        "axis_model": "dual",
        "species": sp,
        "overhang_len": overhang_len,
        "forward_specific_len": fwd_len,
        "forward_axis_estimated": forward_axis_estimated,
        "target": {
            "name": mirna_name,
            "rt_window_rna": mature[-overhang_len:],
            "rt_window_dna": target_dna[-overhang_len:],
            "rt_primer_3prime_segment": _revcomp(target_dna[-overhang_len:]),
            "fwd_window_dna": target_dna[:fwd_len],
        },
        "data_provenance": provenance,
        "interpretation": (
            "Specificity of stem-loop RT-qPCR is the product of two independent axes: the RT "
            "primer binds the 3'-terminal 6 nt, the forward primer binds the 5' region. An "
            "off-target is co-amplified only when BOTH axes fail. Seed-family membership "
            "(positions 2-8) is a biological mRNA-targeting axis and is reported separately for "
            "context only."
        ),
    }

    if not mature_map:
        base.update({
            "n_screened": 0,
            "collisions": [],
            "summary": {"CRITICAL": 0, "LOW": 0, "rt_identical": 0, "n_reported": 0, "truncated": False},
            "worst_rt_risk": "no_index_data",
            "worst_combined_risk": "no_index_data",
            "recommendation": {"action": "none", "reason": "No overhang index for this species."},
            "data_note": (
                f"No mature index for species '{sp}'. Run scripts/build_overhang_index.py "
                "to (re)build data/mirbase_overhang_index.json."
            ),
        })
        return base

    target_family = get_family_id(mirna_name)
    _target_has_name = bool(mirna_name)
    entries = []
    n_screened = 0
    for name, seq_rna in mature_map.items():
        o_dna = _dna(seq_rna)
        # Exclude ONLY the target itself. When the target name is known, exclude by
        # name so a DIFFERENT miRNA sharing an identical mature sequence (paralogous
        # locus / duplicated mature) is still screened — that byte-identical collider
        # (RT + forward both IDENTICAL → combined CRITICAL) is the single worst
        # co-amplification case and must not be silently dropped. Fall back to
        # sequence identity only when the target has no name (raw sequence pasted).
        if _target_has_name:
            if name == mirna_name:
                continue
        elif o_dna == target_dna:
            continue
        n_screened += 1

        # Cheap early prune before the weighted work (O(n), n ~ 2.7k → < 5 ms).
        rt_mm_quick = (
            overhang_len if len(o_dna) < overhang_len
            else _hamming(target_dna[-overhang_len:], o_dna[-overhang_len:])
        )
        lc = min(fwd_len, len(o_dna))
        fwd_mm_quick = _hamming(target_dna[:lc], o_dna[:lc])
        if rt_mm_quick > RT_MM_REPORT_MAX and fwd_mm_quick > FWD_MM_REPORT_MAX:
            continue

        ev = _evaluate_pair(target_dna, o_dna, overhang_len, fwd_len)
        ev["mirna"] = name
        ev["same_seed_family"] = (target_family is not None and target_family == get_family_id(name))
        entries.append(ev)

    # Keep every non-SAFE collision, PLUS every rt-IDENTICAL one (needed for multiplex /
    # RT-primer pooling even when the forward primer rescues specificity).
    reported = [e for e in entries if e["combined_risk"] != "SAFE" or e["rt_risk"] == "IDENTICAL"]
    reported.sort(key=lambda e: (
        _COMBINED_ORDER.get(e["combined_risk"], 9), e["rt_mismatch"], e["fwd_mismatch"]
    ))

    n_total_non_safe = sum(1 for e in entries if e["combined_risk"] != "SAFE")
    truncated = len(reported) > max_report
    reported = reported[:max_report]

    worst_rt = min((e["rt_risk"] for e in entries), key=lambda r: _RT_RISK_ORDER.get(r, 9), default="SAFE")
    worst_combined = min((e["combined_risk"] for e in entries), key=lambda r: _COMBINED_ORDER.get(r, 9), default="SAFE")

    crit_seqs = [_dna(mature_map[e["mirna"]]) for e in entries if e["combined_risk"] == "CRITICAL"]

    for e in reported:
        if e["combined_risk"] == "CRITICAL":
            if e["rt_risk"] in ("IDENTICAL", "HIGH") and e["fwd_mismatch"] == 0:
                e["note"] = ("RT and forward windows are both non-discriminating; this off-target "
                             "will co-amplify. An orthogonal discriminator is required.")
            else:
                pos = e["fwd_mismatch_positions_1based"]
                e["note"] = (f"The only discriminator is the forward primer, whose mismatch"
                             f"{'es' if len(pos) != 1 else ''} at position {pos} sits too far from "
                             "its 3' end to block extension.")

    base.update({
        "n_screened": n_screened,
        "collisions": reported,
        "summary": {
            "CRITICAL": sum(1 for e in reported if e["combined_risk"] == "CRITICAL"),
            "LOW": sum(1 for e in reported if e["combined_risk"] == "LOW"),
            "rt_identical": sum(1 for e in reported if e["rt_risk"] == "IDENTICAL"),
            "n_reported": len(reported),
            "truncated": truncated,
            "n_total_non_safe": n_total_non_safe,
        },
        "worst_rt_risk": worst_rt,
        "worst_combined_risk": worst_combined,
        "recommendation": _recommend(target_dna, overhang_len, fwd_len, crit_seqs, worst_combined),
    })
    return base
