"""
normalization_advisor.py — Rule-based normalization advisory (Phase 7 PART D).

Advisory only — does NOT affect SCORING_WEIGHTS_V4 or candidate ranking.
All recommendations have source_doi + verified status per spec §D.2.

Rules N1–N4 from SPEC_phase7 PART D:
  N1 — tissue / cell-line: endogenous panel (geNorm/NormFinder)
  N2 — plasma / serum / biofluid: spike-in + global-mean
  N3 — FFPE / low-input: LNA-enhanced + validate stability
  N4 — large panel (>=10 targets): global-mean

Sources (DOIs verified via PubMed):
  [Hellemans14]  10.1007/978-1-4939-0733-5_3
  [Hacimoto24]   10.1371/journal.pone.0306657
  [Fujimoto18]   10.1016/j.fsigen.2018.08.010
  [Liang18]      10.1371/journal.pone.0194436
  [Tan15]        10.1093/nar/gkv007   (corrected from 10.1038/srep09430)
  [McDonald11]   10.1373/clinchem.2010.157198
  [Andreasen10]  10.1016/j.ymeth.2010.01.006
"""

import json
import os

_REFERENCE_MIRNAS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "reference_mirnas.json"
)

_DISCLAIMER = (
    "Advisory only. Reference selection must be validated experimentally "
    "before quantification. For research use only."
)
_VALIDATION_NOTE = (
    "Confirm reference stability with geNorm or NormFinder before use. [Hellemans14] "
    "doi:10.1007/978-1-4939-0733-5_3"
)

_GENORM_URL = "https://genorm.cmgg.be/"
_NORMFINDER_URL = "https://moma.dk/normfinder-software"

# ── Rule definitions (N1–N4) ─────────────────────────────────────────────────

_RULES = {
    "N1": {
        "label": "Endogenous reference panel (tissue / cell line)",
        "sample_types": ["tissue", "cell_line", "cell-line", "cell", "cells"],
        "panel_min": None,  # no panel size threshold
        "strategy": (
            "Select ≥3 stable endogenous reference miRNAs using geNorm or NormFinder. "
            "Reference stability is tissue-specific — validate in your tissue type."
        ),
        "cautions": [
            {
                "text": (
                    "Reference miRNA stability is tissue-specific. "
                    "Validate in your tissue cohort before quantification."
                ),
                "source_doi": "10.1016/j.fsigen.2018.08.010",
                "verified": True,
            }
        ],
        "source_dois": [
            "10.1007/978-1-4939-0733-5_3",   # Hellemans14
            "10.1371/journal.pone.0306657",   # Hacimoto24
            "10.1016/j.fsigen.2018.08.010",   # Fujimoto18
        ],
        "verified": True,
    },
    "N2": {
        "label": "Biofluid (plasma / serum): spike-in + global-mean",
        "sample_types": [
            "plasma", "serum", "cfrna", "cfRNA",
            "urine", "saliva", "biofluid", "biofluid-other",
        ],
        "panel_min": None,
        "strategy": (
            "Add exogenous spike-in (cel-miR-39-3p) before RNA extraction to correct "
            "extraction efficiency variation. For panels ≥10 targets, use global-mean "
            "normalization instead of a single reference miRNA."
        ),
        "cautions": [
            {
                "text": (
                    "Hemolysis significantly skews miR-16 and miR-451a in plasma. "
                    "Run hemolysis QC (miR-451a / miR-16 ratio) before quantification. [McDonald11]"
                ),
                "source_doi": "10.1373/clinchem.2010.157198",
                "verified": True,
            },
            {
                "text": (
                    "Add spike-in BEFORE lysis/extraction, not after — incorrect timing "
                    "invalidates extraction efficiency correction. [Tan15]"
                ),
                "source_doi": "10.1093/nar/gkv007",
                "verified": True,
            },
        ],
        "source_dois": [
            "10.1093/nar/gkv007",           # Tan15
            "10.1373/clinchem.2010.157198", # McDonald11
        ],
        "verified": True,
    },
    "N3": {
        "label": "FFPE / low-input: LNA-enhanced + validate stability",
        "sample_types": ["ffpe", "low_input", "low-input", "degraded"],
        "panel_min": None,
        "strategy": (
            "Use LNA-enhanced primers for improved sensitivity at low RNA input. "
            "Validate reference stability empirically — extraction variability is high "
            "in FFPE and low-input samples."
        ),
        "cautions": [
            {
                "text": (
                    "FFPE samples have high RNA fragmentation and extraction variability. "
                    "Use ≥2 reference miRNAs and validate stability. [Andreasen10]"
                ),
                "source_doi": "10.1016/j.ymeth.2010.01.006",
                "verified": True,
            }
        ],
        "source_dois": [
            "10.1016/j.ymeth.2010.01.006",  # Andreasen10
            "10.3390/diagnostics13132170",   # Kunwar23
        ],
        "verified": True,
    },
    "N4": {
        "label": "Large panel (≥10 targets): global-mean normalization",
        "sample_types": [],       # triggered by panel_size alone
        "panel_min": 10,
        "strategy": (
            "For panels ≥10 miRNA targets, global-mean normalization avoids the need "
            "to pre-select reference miRNAs. Assumes the majority of miRNAs are "
            "unchanged — validate this assumption in your experimental context."
        ),
        "cautions": [
            {
                "text": (
                    "Global-mean normalization assumes the majority of miRNAs are "
                    "unchanged between conditions — may not hold in highly dysregulated states. [Hellemans14]"
                ),
                "source_doi": "10.1007/978-1-4939-0733-5_3",
                "verified": True,
            }
        ],
        "source_dois": [
            "10.1007/978-1-4939-0733-5_3",  # Hellemans14
        ],
        "verified": True,
    },
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_reference_mirnas() -> list:
    try:
        with open(_REFERENCE_MIRNAS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _match_rules(sample_type: str, panel_size: int) -> list:
    st_lower = (sample_type or "").lower().strip()
    matched = []
    for rule_id, rule in _RULES.items():
        # N4 triggered by panel size
        if rule["panel_min"] is not None and panel_size >= rule["panel_min"]:
            matched.append((rule_id, rule))
            continue
        # Sample-type match (case-insensitive)
        if st_lower and st_lower in [s.lower() for s in rule["sample_types"]]:
            matched.append((rule_id, rule))
    return matched


# ── Public API ────────────────────────────────────────────────────────────────

def advise_normalization(sample_type: str, panel_size: int = 1) -> dict:
    """
    Return normalization advisory for the given sample_type and panel_size.

    Args:
        sample_type: one of tissue, plasma, serum, ffpe, cell_line, urine, biofluid, etc.
        panel_size:  number of miRNA targets; triggers N4 when >= 10.

    Returns advisory dict with keys:
        sample_type, recommended_strategy, rule_id, reference_candidates,
        cautions, validation_note, disclaimer, sources, external_tools, verified.
    """
    matched = _match_rules(sample_type, panel_size)

    # If no specific rule matched, default to N1 (general case)
    if not matched:
        matched = [("N1", _RULES["N1"])]

    # Primary = first match; merge cautions from all matched
    primary_id, primary_rule = matched[0]
    all_cautions = []
    for _, r in matched:
        all_cautions.extend(r.get("cautions", []))

    # Reference candidates filtered by sample_type
    all_refs = _load_reference_mirnas()
    st_lower = (sample_type or "").lower().strip()
    candidates = [
        ref for ref in all_refs
        if st_lower in [s.lower() for s in ref.get("suitable_sample_types", [])]
    ]
    # For biofluid types with no specific matches, include spike-ins
    _biofluid_types = {"plasma", "serum", "cfrna", "urine", "saliva", "biofluid", "biofluid-other"}
    if not candidates and st_lower in _biofluid_types:
        candidates = [r for r in all_refs if r.get("role") == "exogenous spike-in"]

    return {
        "sample_type": sample_type,
        "recommended_strategy": primary_rule["strategy"],
        "rule_id": primary_id,
        "rule_label": primary_rule["label"],
        "reference_candidates": candidates,
        "cautions": all_cautions,
        "validation_note": _VALIDATION_NOTE,
        "disclaimer": _DISCLAIMER,
        "sources": primary_rule.get("source_dois", []),
        "external_tools": [
            {"name": "geNorm", "url": _GENORM_URL},
            {"name": "NormFinder", "url": _NORMFINDER_URL},
        ],
        "verified": primary_rule.get("verified", False),
    }
