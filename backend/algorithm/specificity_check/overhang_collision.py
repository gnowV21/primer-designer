"""
overhang_collision.py — assay-level specificity screen for stem-loop RT-qPCR.

Every mature miRNA of the species (data/mirbase_overhang_index.json) is run through
the ΔCq model of assay_model.py: RT capture by the 3' overhang + forward priming on
the cDNA, each offset-aware, ΔCq_assay = ΔCq_RT + ΔCq_FWD (2026-10-29; replaces the
Week 2 RT x FWD risk matrix and its fixed-position windows).

Off-targets fall into two groups:
  * other miRNAs — labelled CO-AMPLIFIED / PARTIAL / DISCRIMINATED; the worst label
    drives scoring and the headline;
  * miRBase entries carrying the same sequence or one shifted ≤ 2 nt at an end
    (synonyms/renamed entries, paralogues from another locus) — reported with their
    predicted ΔCq but not scored, because no primer design separates them [Magee17].
    These are NOT biological isomiRs: processing variants and tailed forms have no
    miRBase entries of their own; they are covered by the isomiRdb-based flags on
    the RT primer (isomir_flag.py).

Seed-family membership (positions 2-8) is the mRNA-targeting axis and is reported
for context only (`same_seed_family`), never used to classify risk.
"""

import json
import os

import algorithm.primer3_safe as primer3

from ..constants import (
    FWD_PREFIX_LEN_FALLBACK,
    COLLISION_MAX_REPORT,
    OVERHANG_LENGTH_MAX,
    FORWARD_SPECIFIC_LENGTH_MAX,
    VIRUS_HOST_SPECIES,
    REFERENCE_ANNOTATED_SPECIES,
)
from ..thermodynamics import _get_p3_params
from .assay_model import evaluate
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

_LABEL_ORDER = {"CO-AMPLIFIED": 0, "PARTIAL": 1, "DISCRIMINATED": 2}
_VARIANT_CATEGORIES = ("same_sequence", "shifted_5p", "shifted_3p")


# ── helpers ───────────────────────────────────────────────────────

def _dna(rna: str) -> str:
    return rna.upper().replace("U", "T")


def _revcomp(dna: str) -> str:
    return "".join(_COMP.get(b, "N") for b in reversed(dna))


def _load_index() -> dict:
    global _INDEX_CACHE
    if _INDEX_CACHE is not None:
        return _INDEX_CACHE
    with open(_INDEX_PATH, encoding="utf-8") as f:
        _INDEX_CACHE = json.load(f)
    return _INDEX_CACHE


def known_species() -> frozenset[str]:
    """miRBase species codes present in the index (same release as the BLAST DB)."""
    return frozenset((_load_index().get("mature") or {}).keys())


def _duplex_tm(region: str, sense_window: str, p3: dict) -> float:
    """Tm of the forward specific region on the cDNA of `sense_window`."""
    return float(primer3.calc_heterodimer(region, _revcomp(sense_window), **p3).tm)


def _tm_gap_fn(target_dna: str, fwd_len: int, p3: dict):
    """tm_gap(other, r) = Tm_on − Tm_off for the forward specific region in register r.

    Window = off-target bases opposite the region + 1 downstream base (thal's
    dangling-end term): on the target it gives exactly the full-sequence Tm, the
    same convention as the BLAST classifier v4.
    """
    region = target_dna[:fwd_len]
    tm_on = _duplex_tm(region, target_dna[:fwd_len + 1], p3)
    cache: dict = {}

    def gap(other: str, r: int):
        key = (other, r)
        if key not in cache:
            window = other[max(r, 0): fwd_len + r + 1]
            cache[key] = tm_on - _duplex_tm(region, window, p3) if window else None
        return cache[key]
    return gap


def _opposite(other: str, start: int, length: int) -> str:
    """other[start:start+length] with '-' where the index falls outside other."""
    return "".join(other[j] if 0 <= j < len(other) else "-" for j in range(start, start + length))


def _evaluate_pair(target_dna, other_dna, overhang_len, fwd_len, tm_gap) -> dict:
    """ΔCq evaluation of one off-target plus the windows the UI diffs against."""
    ev = evaluate(target_dna, other_dna, overhang_len, fwd_len, tm_gap)
    rt, fwd = ev["rt"], ev["fwd"]
    ev["rt_window_dna"] = _opposite(other_dna, len(other_dna) - rt["shift_3p"] - overhang_len,
                                    overhang_len)
    ev["rt_mismatch"] = len(rt["mismatch_positions"])
    if fwd is not None:
        ev["fwd_window_dna"] = _opposite(other_dna, fwd["shift_5p"], fwd_len)
        ev["fwd_mismatch"] = len(fwd["mismatch_from_3p"])
        ev["fwd_mismatch_positions_1based"] = sorted(fwd_len - q + 1 for q in fwd["mismatch_from_3p"])
    return ev


def _annotation_note(sp: str, host: str | None, by_species: dict) -> str | None:
    """How complete the screened miRBase set is — DISCRIMINATED only means 'no
    ANNOTATED off-target'."""
    if sp not in by_species:
        return None
    parts = []
    if host and host in by_species:
        parts.append(f"Viral miRNA: screened {len(by_species[sp])} {sp} plus "
                     f"{len(by_species[host])} host ({host}) miRNAs, since the assay runs on "
                     "infected host cells.")
    elif host:
        parts.append(f"Viral miRNA: host species '{host}' has no miRBase entries — "
                     "host miRNAs are not screened.")
    if sp not in REFERENCE_ANNOTATED_SPECIES and not host:
        parts.append(f"miRBase 22.1 annotates {len(by_species[sp])} mature miRNAs for {sp}. "
                     "DISCRIMINATED means no ANNOTATED off-target; miRNAs of this species "
                     "that miRBase does not list are not screened.")
    return " ".join(parts) or None


# ── recommendation (§1.4) ─────────────────────────────────────────

def _recommend(target_dna, overhang_len, fwd_len, coamp_seqs, p3):
    """Only ever suggest a fix the module can VERIFY by recomputation in this response."""
    if not coamp_seqs:
        return {
            "action": "none",
            "reason": "No other miRNA is predicted to co-amplify (ΔCq_assay ≥ 3.3 for all).",
        }

    def all_resolved(n, lp):
        gap = _tm_gap_fn(target_dna, lp, p3)
        return all(evaluate(target_dna, o, n, lp, gap)["assay_label"] != "CO-AMPLIFIED"
                   for o in coamp_seqs)

    # 1. Try a longer RT overhang (up to OVERHANG_LENGTH_MAX).
    for n in range(overhang_len + 1, OVERHANG_LENGTH_MAX + 1):
        if all_resolved(n, fwd_len):
            return {
                "action": "increase_overhang",
                "suggested_overhang_len": n,
                "off_label_warning": _OFF_LABEL_WARNING,
                "reason": (
                    f"Extending the RT overhang to {n} nt lifts every currently co-amplified "
                    "miRNA above ΔCq 3.3 (verified by recomputation)."
                ),
            }

    # 2. Try a longer forward specific region.
    for lp in range(fwd_len + 1, FORWARD_SPECIFIC_LENGTH_MAX + 1):
        if all_resolved(overhang_len, lp):
            return {
                "action": "increase_forward_specific_len",
                "suggested_forward_specific_len": lp,
                "reason": (
                    f"Extending the forward specific region to {lp} nt brings the differing "
                    "base(s) close enough to the primer 3' end to lift every co-amplified "
                    "miRNA above ΔCq 3.3 (verified by recomputation)."
                ),
            }

    # 3. Neither axis can be rescued by geometry alone.
    return {
        "action": "orthogonal_assay",
        "reason": (
            "These miRNAs cannot be distinguished by stem-loop RT-qPCR geometry alone: the "
            "RT overhang and the forward primer both fail to discriminate even at their length "
            "limits. Use a hydrolysis (TaqMan) probe spanning the differing region, an LNA-"
            "substituted primer, or an orthogonal method."
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
    """Assay-level (RT + forward) ΔCq screen vs the full per-species mature index.
    See the module docstring and assay_model.py for the science."""
    mature = (mature_seq or "").upper().strip()
    target_dna = _dna(mature)

    fwd_len = forward_specific_len or FWD_PREFIX_LEN_FALLBACK
    forward_axis_estimated = forward_specific_len is None

    prefix = _resolve_species_prefix(mirna_name, species)   # e.g. "hsa-"
    sp = prefix.rstrip("-")

    index = _load_index()
    by_species = index.get("mature") or {}
    # A viral miRNA is measured in infected host cells: screen the host's miRNAs too.
    host = VIRUS_HOST_SPECIES.get(sp)
    screened_species = [s for s in (sp, host) if s and s in by_species]
    mature_map = {}
    for s in screened_species:
        mature_map.update(by_species[s])
    meta = index.get("_metadata", {})
    provenance = {
        "source": meta.get("source"),
        "build_date": meta.get("build_date"),
        "mirbase_release": meta.get("mirbase_release"),
        "mature_fa_sha256": meta.get("mature_fa_sha256"),
    }

    base = {
        "axis_model": "delta_cq",
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
        "screened_species": screened_species,
        "host_species": host,
        "annotation_note": _annotation_note(sp, host, by_species),
        "interpretation": (
            "An off-target gives signal only if the RT overhang captures it AND the forward "
            "primer primes its cDNA; the delays add (ΔCq_assay ≈ ΔCq_RT + ΔCq_FWD, cross-"
            "reactivity ≈ 2^−ΔCq). Values are lower bounds of published data (Chen 2005, "
            "Czimmerer 2013, Schamberger 2014, Stadhouders 2010) measured with TaqMan probes; "
            "for SYBR the prediction is optimistic. miRBase entries carrying the same "
            "sequence, or one shifted ≤ 2 nt at an end (synonyms, paralogues), cannot be "
            "separated by any primer design and are listed apart (Magee 2017). Biological "
            "isomiRs have no miRBase entries and are covered by the RT-primer isomiR flags. "
            "Seed-family membership is reported for context only."
        ),
        "thresholds": {"co_amplified_below": 3.3, "discriminated_at": 4.3},
    }

    if not mature_map:
        base.update({
            "n_screened": 0,
            "collisions": [],
            "same_molecule_entries": [],
            "summary": {"CO-AMPLIFIED": 0, "PARTIAL": 0, "rt_identical": 0,
                        "shifted_5p": 0, "shifted_3p": 0, "same_sequence": 0,
                        "n_reported": 0, "truncated": False, "n_total_flagged": 0},
            "worst_assay_label": "no_index_data",
            "recommendation": {"action": "none", "reason": "No overhang index for this species."},
            "data_note": (
                f"No mature index for species '{sp}'. Run scripts/build_overhang_index.py "
                "to (re)build data/mirbase_overhang_index.json."
            ),
        })
        return base

    p3 = _get_p3_params(params or {})
    tm_gap = _tm_gap_fn(target_dna, fwd_len, p3)
    target_family = get_family_id(mirna_name)
    target_rt = target_dna[-overhang_len:]
    others, variants = [], []
    n_screened = 0
    for name, seq_rna in mature_map.items():
        o_dna = _dna(seq_rna)
        # Exclude ONLY the target itself: by name when known, so a DIFFERENT miRNA with
        # an identical mature sequence (paralogous locus) is still reported; by
        # sequence only when the target has no name (raw sequence pasted).
        if mirna_name:
            if name == mirna_name:
                continue
        elif o_dna == target_dna:
            continue
        n_screened += 1
        ev = _evaluate_pair(target_dna, o_dna, overhang_len, fwd_len, tm_gap)
        ev["mirna"] = name
        ev["same_seed_family"] = (target_family is not None and target_family == get_family_id(name))
        ev["rt_identical"] = o_dna.endswith(target_rt) and len(o_dna) >= overhang_len
        (variants if ev["category"] in _VARIANT_CATEGORIES else others).append(ev)

    # Report every non-discriminated other miRNA, plus every RT-identical one (needed
    # for multiplex / RT-primer pooling even when the forward primer resolves it).
    flagged = [e for e in others if e["assay_label"] != "DISCRIMINATED" or e["rt_identical"]]
    flagged.sort(key=lambda e: (_LABEL_ORDER[e["assay_label"]], e["delta_cq"], e["mirna"]))
    truncated = len(flagged) > max_report
    reported = flagged[:max_report]
    variants.sort(key=lambda e: (e["delta_cq"], e["mirna"]))

    worst = min((e["assay_label"] for e in others), key=_LABEL_ORDER.get, default="DISCRIMINATED")
    coamp_seqs = [_dna(mature_map[e["mirna"]]) for e in others if e["assay_label"] == "CO-AMPLIFIED"]

    for e in reported:
        if e["assay_label"] == "CO-AMPLIFIED":
            e["note"] = (f"Predicted cross-signal ≈ {e['cross_reactivity_pct']:.1f} % "
                         f"(RT: {e['rt']['basis']}; forward: {e['fwd']['basis']}).")
    for e in variants:
        e["note"] = {
            "same_sequence": ("Another miRBase entry with the identical mature sequence "
                              "(synonym, renamed entry, or a paralogue from another locus) "
                              "— no primer can separate it from the target."),
            "shifted_5p": ("Another miRBase entry whose 5′ end is shifted ≤ 2 nt: both "
                           "primers bind it, so it is co-amplified."),
            "shifted_3p": ("Another miRBase entry whose 3′ end is shifted ≤ 2 nt: the RT "
                           "overhang resolves it only partly."),
        }[e["category"]]

    base.update({
        "n_screened": n_screened,
        "collisions": reported,
        "same_molecule_entries": variants,
        "summary": {
            "CO-AMPLIFIED": sum(1 for e in others if e["assay_label"] == "CO-AMPLIFIED"),
            "PARTIAL": sum(1 for e in others if e["assay_label"] == "PARTIAL"),
            "rt_identical": sum(1 for e in others if e["rt_identical"]),
            "shifted_5p": sum(1 for e in variants if e["category"] == "shifted_5p"),
            "shifted_3p": sum(1 for e in variants if e["category"] == "shifted_3p"),
            "same_sequence": sum(1 for e in variants if e["category"] == "same_sequence"),
            "n_reported": len(reported),
            "truncated": truncated,
            "n_total_flagged": len(flagged),
        },
        "worst_assay_label": worst,
        "recommendation": _recommend(target_dna, overhang_len, fwd_len, coamp_seqs, p3),
    })
    return base
