# ================================================================
# specificity_check/family_crossreactivity.py
# Cross-reactivity analysis: stemloop RT primer vs family members
#
# Algorithm:
#   1. Extract overhang (last N nt) of target mature miRNA.
#   2. Identify family from miRNA name → lookup siblings in JSON DB.
#   3. For each sibling, compute Hamming distance AND Kwok weighted distance on overhang.
#   4. Estimate Tm discrimination via SantaLucia 1998 NN model
#      (reuses existing calculate_tm_nn).
#   5. Classify risk: IDENTICAL / HIGH / LOW.
#      Kwok weighted distance: 3'-proximal mismatches block extension → downgrade to LOW [Kwok90].
#   6. If any HIGH risk → auto-extend overhang up to OVERHANG_LENGTH_MAX (7 nt) and repeat.
#
# Data: backend/data/mirbase_family_overhangs.json (offline — no API calls)
# WARNING: Family sequences in JSON are PLACEHOLDER — verify vs miRBase v22+.
#
# Sources: [Chen05] Chen et al. 2005; [K11] Kramer 2011; [SL98] SantaLucia 1998;
#          [Kwok90] Kwok et al. 1990 NAR 18(4):999-1005 — position-weighted mismatch discrimination
# ================================================================

import json
import os
import re
from ..thermodynamics import calculate_tm_nn
from ..sequence_utils import rna_to_dna
from ..constants import (
    KWOK_POSITION_WEIGHTS, KWOK_DIST_DISCRIMINATING, MIRBASE_HUMAN_PREFIX, OVERHANG_LENGTH_MAX,
)
from .kwok import kwok_weighted_distance, PRIMER_3P_AT_WINDOW_START

# UI species value → miRBase 3-letter prefix
_SPECIES_TO_PREFIX = {"human": "hsa", "mouse": "mmu", "rat": "rno"}

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "mirbase_family_overhangs.json")
_DB_CACHE: dict | None = None

# Maximum overhang length to attempt when resolving HIGH risk
_OVERHANG_MAX_NT = OVERHANG_LENGTH_MAX


def _resolve_species_prefix(mirna_name: str, species: str | None = None) -> str:
    """
    Return the miRBase species prefix (e.g. 'hsa-') used to scope family
    cross-reactivity to a single organism. [A3]

    Priority:
      1. A real prefix parsed from `mirna_name` — authoritative for what the
         miRNA actually is (reuses blast_offtarget._extract_species_prefix; the
         import is deferred to avoid a circular import, since that module
         imports get_family_id from here).
      2. The form-selected `species` ('human'|'mouse'|'rat' or a raw prefix),
         used when the sequence was pasted without a miRBase name.
      3. Human default.
    """
    if mirna_name and re.match(r"^[a-z]{3}-", mirna_name.strip().lower()):
        from .blast_offtarget import _extract_species_prefix
        return _extract_species_prefix(mirna_name)
    if species:
        s = species.strip().lower()
        s = _SPECIES_TO_PREFIX.get(s, s)
        return s if s.endswith("-") else s + "-"
    return MIRBASE_HUMAN_PREFIX


def check_family_crossreactivity(
    mature_seq: str,
    mirna_name: str,
    params: dict,
    overhang_len: int = 6,
    species: str | None = None,
) -> dict:
    """
    Analyse cross-reactivity of a stemloop RT primer with family members.

    Args:
        mature_seq:  Mature miRNA sequence (RNA, 5'→3').
        mirna_name:  miRNA identifier, e.g. 'hsa-let-7a-5p' or 'hsa-miR-21-5p'.
        params:      User formData (for Tm calculation salt conditions).
        overhang_len: Stemloop RT primer binding length (default 6 nt per Chen 2005).
        species:     Optional species override ('human'|'mouse'|'rat' or a raw
                     miRBase prefix). Used only when `mirna_name` carries no
                     prefix. Family cross-reactivity is scoped to one species —
                     same-family orthologs in other species are NOT off-targets
                     for a single-organism sample (consistent with the BLAST
                     `cross_species_excluded` logic). [A3]

    Returns dict with keys:
        family, species, overhang_used, target_overhang, cross_reactivity,
        cross_species_excluded, recommendation, data_warning.
    """
    db = _load_db()
    family_name, siblings = _find_family(db, mirna_name, mature_seq)

    if not siblings:
        return _no_family_result(family_name, overhang_len)

    # ── A3: scope siblings to the target species ────────────────────
    target_prefix = _resolve_species_prefix(mirna_name, species)
    same_species = {k: v for k, v in siblings.items() if k.lower().startswith(target_prefix)}
    cross_species_excluded = len(siblings) - len(same_species)
    siblings = same_species

    if not siblings:
        res = _no_family_result(family_name, overhang_len)
        res["species"] = target_prefix.rstrip("-")
        res["cross_species_excluded"] = cross_species_excluded
        res["data_warning"] = (
            f"Family '{family_name}' has no {target_prefix.rstrip('-')} sibling in the current "
            f"dataset — {cross_species_excluded} same-family ortholog(s) in other species were "
            "excluded (not off-targets for a single-species sample)."
        )
        return res

    target_overhang = _get_overhang(mature_seq, overhang_len)
    results = _evaluate(target_overhang, mature_seq, mirna_name, siblings, overhang_len, params)

    high_risk_siblings = [r for r in results if r["risk"] == "HIGH"]
    recommendation = _build_recommendation(
        high_risk_siblings, siblings, mature_seq, mirna_name, params, overhang_len
    )

    # Surface provenance from Phase 7 _metadata
    db_meta = get_family_db_metadata()
    provenance = db_meta.get("provenance", "unknown")
    canonical = db_meta.get("canonical", False)
    if canonical:
        data_warning = (
            f"Family grouping: miRBase canonical classification (miFam.dat, provenance={provenance}). "
            "Re-run scripts/build_family_db.py after each miRBase release update."
        )
    else:
        data_warning = (
            "Family grouping: seed-based classification (positions 2-8, not canonical miRBase miFam.dat). "
            "Re-run scripts/build_family_db.py with FTP access for canonical data."
        )

    return {
        "family": family_name,
        "species": target_prefix.rstrip("-"),
        "overhang_used": overhang_len,
        "target_overhang": target_overhang,
        "cross_reactivity": results,
        "cross_species_excluded": cross_species_excluded,
        "recommendation": recommendation,
        "data_warning": data_warning,
        "data_provenance": {
            "provenance": provenance,
            "canonical": canonical,
            "verified": db_meta.get("verified", False),
            "build_date": db_meta.get("build_date"),
        },
    }


# ── Internal helpers ──────────────────────────────────────────────

_RAW_CACHE: dict | None = None   # raw JSON (may have _metadata + families wrapper)


def _load_raw() -> dict:
    """Load and cache the raw JSON file (Phase 7 format or legacy flat format)."""
    global _RAW_CACHE
    if _RAW_CACHE is not None:
        return _RAW_CACHE
    try:
        with open(_DB_PATH, encoding="utf-8") as f:
            _RAW_CACHE = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _RAW_CACHE = {}
    return _RAW_CACHE


def _load_db() -> dict:
    """
    Return the families dict (backward-compat with both Phase 7 and legacy formats).

    Phase 7 format: {"_metadata": {...}, "families": {...}}
    Legacy format:  families at top-level (no "_metadata" key)
    One-liner fix: data.get("families", data)
    """
    global _DB_CACHE
    if _DB_CACHE is not None:
        return _DB_CACHE
    raw = _load_raw()
    # Phase 7 wraps families in "families" key; legacy has them flat at top-level
    _DB_CACHE = raw.get("families", raw)
    return _DB_CACHE


def get_family_db_metadata() -> dict:
    """
    Return the _metadata block from the JSON (Phase 7 only).
    Returns {} for legacy JSON files without _metadata.
    Used by routes/design.py to surface data_provenance in the response.
    """
    raw = _load_raw()
    return raw.get("_metadata", {})


def get_family_id(mirna_name: str) -> str | None:
    """
    Return the seed-family id for a mature miRNA name (e.g. 'hsa-let-7a-5p'),
    or None if the name is not in the family DB index.

    Public helper reused by the BLAST off-target module (blast_offtarget.py) to
    fold same-family hits into one aggregated bucket instead of listing each
    family member as a separate critical off-target. Uses the O(1)
    `_mirna_to_family` index built by build_family_db.py.
    """
    index = _load_db().get("_mirna_to_family", {})
    return index.get(mirna_name)


def _find_family(db: dict, mirna_name: str, mature_seq: str) -> tuple:
    """
    Look up miRNA family. Returns (family_name, {member: seq}).

    Two strategies (tried in order):
      1. _mirna_to_family index — O(1) direct lookup (new JSON format from
         build_mirbase_data.py).  Handles families like mir-17 whose member
         names (miR-17, miR-18a, …) don't share a common name prefix.
      2. Name-substring fallback — O(n) scan for backward compatibility with
         the old hand-curated PLACEHOLDER JSON (family key ⊂ miRNA name).
    """
    # Strategy 1: direct index lookup (generated JSON has _mirna_to_family)
    index = db.get("_mirna_to_family")
    if index and mirna_name in index:
        family_name = index[mirna_name]
        members = db.get(family_name, {})
        filtered = {
            k: v for k, v in members.items()
            if not k.startswith("_") and v != mature_seq
        }
        return family_name, filtered

    # Strategy 2: substring match — backward compat with PLACEHOLDER JSON
    name_lower = mirna_name.lower()
    for family_key, members in db.items():
        if family_key.startswith("_"):
            continue
        if family_key.lower() in name_lower or name_lower.startswith(f"hsa-{family_key}"):
            filtered = {
                k: v for k, v in members.items()
                if not k.startswith("_") and v != mature_seq
            }
            return family_key, filtered

    return None, {}


def _get_overhang(mature_seq: str, length: int) -> str:
    """Extract the last N nt of a mature miRNA sequence (RNA)."""
    return mature_seq[-length:].upper()


def _hamming(s1: str, s2: str) -> int:
    """Hamming distance for equal-length strings; returns max length if lengths differ."""
    if len(s1) != len(s2):
        return max(len(s1), len(s2))
    return sum(c1 != c2 for c1, c2 in zip(s1, s2))


def _kwok_distance(s1: str, s2: str) -> float:
    """Thin wrapper for the RT-primer axis (SPEC_week2 C2).

    The two windows are the miRNA 3'-overhang (mature[-N:]); the RT primer is their
    reverse complement, so the RT primer 3' terminus pairs with window[0] (the 5'-most
    nucleotide of the overhang). Weights must therefore be indexed from the window START,
    not the window end. See specificity_check.kwok for the geometry rationale [Kwok90].
    """
    return kwok_weighted_distance(s1, s2, PRIMER_3P_AT_WINDOW_START)


def _calc_tm(seq_rna: str, params: dict) -> float:
    """
    Tm of the N-nt RNA overhang binding to its perfect DNA complement,
    using the NN model (SantaLucia 1998) + Mg2+ salt correction.
    Reuses existing calculate_tm_nn on the DNA equivalent of the RNA sequence.
    """
    dna = rna_to_dna(seq_rna)
    return calculate_tm_nn(dna, params)


def _classify_risk(mismatch: int, delta_tm: float, kwok_dist: float = 0.0) -> str:
    """
    Risk classification for a sibling with `mismatch` mismatches in the overhang.

      0 mismatch                                → IDENTICAL
      1 mismatch, kwok_dist ≥ KWOK_DIST_DISCRIMINATING → LOW
          (mismatch is 3'-proximal — blocks extension per Kwok90, independent of ΔTm)
      1 mismatch, ΔTm ≥ 5°C                    → LOW
      1 mismatch, ΔTm < 5°C                    → HIGH
      2 mismatches                              → LOW
      ≥ 3 mismatches                            → SAFE
    """
    if mismatch == 0:
        return "IDENTICAL"
    if mismatch == 1:
        if kwok_dist >= KWOK_DIST_DISCRIMINATING:
            return "LOW"   # 3'-proximal mismatch discriminates well regardless of ΔTm [Kwok90]
        return "HIGH" if delta_tm < 5.0 else "LOW"
    if mismatch == 2:
        return "LOW"
    return "SAFE"


def _evaluate(
    target_overhang: str,
    mature_seq: str,
    mirna_name: str,
    siblings: dict,
    overhang_len: int,
    params: dict,
) -> list:
    """Evaluate cross-reactivity for each sibling. Omits SAFE results."""
    tm_target = _calc_tm(target_overhang, params)
    results = []

    for sibling_name, sibling_seq in siblings.items():
        if not sibling_seq or sibling_seq.startswith("PLACEHOLDER"):
            continue
        sibling_overhang = _get_overhang(sibling_seq, overhang_len)
        if len(sibling_overhang) < overhang_len:
            continue  # sibling sequence too short

        mismatch = _hamming(target_overhang, sibling_overhang)
        if mismatch >= 3:
            continue  # SAFE — omit from output

        kwok_dist = _kwok_distance(target_overhang, sibling_overhang)
        tm_sibling = _calc_tm(sibling_overhang, params)
        delta_tm = round(tm_target - tm_sibling, 1)
        risk = _classify_risk(mismatch, delta_tm, kwok_dist)

        results.append({
            "sibling": sibling_name,
            "sibling_overhang": sibling_overhang,
            "mismatch": mismatch,
            "kwok_distance": round(kwok_dist, 1),
            "tm_target_overhang": round(tm_target, 1),
            "tm_sibling_overhang": round(tm_sibling, 1),
            "delta_tm": delta_tm,
            "risk": risk,
        })

    return sorted(results, key=lambda x: (x["mismatch"], -x["delta_tm"]))


def _build_recommendation(
    high_risk_siblings: list,
    siblings: dict,
    mature_seq: str,
    mirna_name: str,
    params: dict,
    current_len: int,
) -> dict:
    """
    If HIGH risk exists, auto-extend overhang from current_len+1 up to _OVERHANG_MAX_NT.
    Return recommendation with suggested length and whether resolved.
    """
    if not high_risk_siblings:
        return {
            "suggested_overhang_length": current_len,
            "resolved": True,
            "reason": "No HIGH risk siblings at current overhang length.",
            "remaining_high_risk_siblings": [],
        }

    suggested_len = current_len
    remaining_high = high_risk_siblings

    for try_len in range(current_len + 1, _OVERHANG_MAX_NT + 1):
        target_overhang = _get_overhang(mature_seq, try_len)
        extended_results = _evaluate(target_overhang, mature_seq, mirna_name, siblings, try_len, params)
        remaining_high = [r for r in extended_results if r["risk"] == "HIGH"]
        suggested_len = try_len
        if not remaining_high:
            break

    resolved = len(remaining_high) == 0
    reason = (
        f"Extending to {suggested_len} nt resolves all HIGH risk cross-reactivity."
        if resolved else
        f"HIGH risk persists at {suggested_len} nt (maximum allowed = {_OVERHANG_MAX_NT} nt). "
        f"These siblings may be indistinguishable with the stemloop RT-qPCR approach alone."
    )

    return {
        "suggested_overhang_length": suggested_len,
        "resolved": resolved,
        "reason": reason,
        "remaining_high_risk_siblings": [r["sibling"] for r in remaining_high],
        "off_label_warning": (
            None if suggested_len == 6 else
            f"Off-label: {suggested_len} nt binding region has not been experimentally "
            f"validated. Chen et al. 2005 only tested 6 nt. Interpret with caution."
        ),
    }


def identify_family_by_accession(accession: str) -> dict | None:
    """
    Look up a family by mature miRNA accession (e.g. 'MIMAT0000062').
    Returns {"id": family_id, "members": {...}} or None if not found.
    Fixes Limitation #4 from Phase 2 (heuristic failed for accession inputs).
    Requires _mirna_to_family index built by build_family_db.py.
    """
    db = _load_db()
    index = db.get("_mirna_to_family", {})
    # index maps mature names → family id; accessions are NOT in this index.
    # Scan all family members to find which one has the matching accession in their key
    # (accessions appear if build_family_db.py stored them, or fall through to None).
    acc_upper = accession.strip().upper()
    for mature_name, fam_id in index.items():
        if mature_name.upper() == acc_upper:
            members = db.get(fam_id, {})
            return {"id": fam_id, "members": {k: v for k, v in members.items() if not k.startswith("_")}}
    return None


def _no_family_result(family_name, overhang_len: int) -> dict:
    db_meta = get_family_db_metadata()
    return {
        "family": family_name,
        "overhang_used": overhang_len,
        "target_overhang": None,
        "cross_reactivity": [],
        "recommendation": {
            "suggested_overhang_length": overhang_len,
            "resolved": True,
            "reason": "No family data available for this miRNA. Cannot assess cross-reactivity.",
            "remaining_high_risk_siblings": [],
        },
        "data_warning": (
            "This miRNA has no family siblings in the current dataset "
            "(may be unique or not covered by the current family DB). "
            "Re-run scripts/build_family_db.py to refresh."
        ),
        "data_provenance": {
            "provenance": db_meta.get("provenance", "unknown"),
            "canonical": db_meta.get("canonical", False),
            "verified": db_meta.get("verified", False),
            "build_date": db_meta.get("build_date"),
        },
    }
