# ================================================================
# algorithm/protocol_advisor.py — PART A (SPEC_phase5 §A.4)
#
# Evidence-based protocol advisor: maps design result + form params
# to relevant published protocol recommendations (P1-P6) with match
# score, pros/cons, and citation DOIs.
#
# Descriptive only — never prescriptive. Every advice item carries:
#   id, recommendation, match (high/medium/low), pros, cons,
#   sources [{tag, doi, pmid, note}], disclaimer.
#
# Sources: [Wang17] DOI 10.3892/mmr.2017.8297;
#          [Andreasen10] DOI 10.1016/j.ymeth.2010.01.006;
#          [Kunwar23] DOI 10.3390/diagnostics13132170;
#          [Lagatie17] DOI 10.1007/s00436-017-5382-5;
#          [Cao23] DOI 10.1016/j.ab.2023.115267.
# ================================================================

import json
import os

_KB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "protocol_kb.json")
_KB_CACHE: dict | None = None

_LOW_INPUT_SAMPLE_TYPES = {"ffpe", "plasma", "serum", "cfrna", "low_input", "exosome", "urine"}
_CLINICAL_CONTEXTS = {"clinical", "diagnostic", "cap_clia", "regulatory", "ivd"}
# [RESEARCH_QUESTIONS_UX B1/B2] sample types that trigger normalization/biofluid advisors
_BIOFLUID_SAMPLE_TYPES = {"plasma", "serum", "cfrna", "urine", "saliva", "csf"}


def _load_kb() -> dict:
    global _KB_CACHE
    if _KB_CACHE is None:
        try:
            with open(_KB_PATH, encoding="utf-8") as f:
                _KB_CACHE = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Do not cache the error — retry on next request after the file is fixed
            return {"rules": [], "kb_version": "error", "updated": "unknown"}
    return _KB_CACHE


def _match_level(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def advise_protocol(design_result: dict, form_params: dict) -> list[dict]:
    """
    Map design result + form params to evidence-backed protocol suggestions.

    Args:
        design_result: Full /api/design response object.
        form_params:   Merged flat dict of all form groups from the request body.

    Returns list of advice dicts, sorted by match level (high first).
    Each item: {id, title, recommendation, match, pros, cons, sources, disclaimer}
    """
    kb = _load_kb()
    rules = kb.get("rules", [])
    kb_version = kb.get("kb_version", "?")
    kb_updated = kb.get("updated", "?")

    # ── Extract signals from design_result ─────────────────────────
    signal_method = (form_params.get("signalMethod") or "taqman").lower()
    multiplex = bool(form_params.get("multiplex") or form_params.get("isMultiplex"))
    sample_type = (form_params.get("sampleType") or form_params.get("sample_type") or "").lower()
    application = (form_params.get("applicationContext") or form_params.get("application") or "").lower()

    try:
        input_amount = float(form_params.get("inputAmount") or form_params.get("input_amount_ng") or 999)
    except (TypeError, ValueError):
        input_amount = 999.0

    # Family risk from specificity_warnings
    xr = (design_result.get("specificity_warnings") or {}).get("cross_reactivity") or {}
    cr_list = xr.get("cross_reactivity") or []
    family_risk_high = any(r.get("risk") in ("HIGH", "IDENTICAL") for r in cr_list)

    # Edge cases
    edge_codes = {ec.get("code") for ec in (design_result.get("edge_cases") or [])}

    # ── Evaluate each rule ──────────────────────────────────────────
    advice = []
    for rule in rules:
        rid = rule["id"]
        score = 0.0
        weights = rule.get("match_weights", {})
        total_weight = sum(weights.values()) or 1.0

        if rid == "P1":
            if signal_method == "sybr":
                score += weights.get("signal_method_sybr", 0)
            if family_risk_high:
                score += weights.get("family_risk_high", 0)

        elif rid == "P2":
            if sample_type in _LOW_INPUT_SAMPLE_TYPES:
                score += weights.get("sample_type_difficult", 0)
            if input_amount <= 10:
                score += weights.get("low_input", 0)

        elif rid == "P3":
            if signal_method == "sybr":
                score += weights.get("signal_method_sybr", 0)

        elif rid == "P4":
            if multiplex:
                score += weights.get("multiplex", 0)

        elif rid == "P5":
            if "E1" in edge_codes:
                score += weights.get("edge_E1", 0)
            if "E4" in edge_codes:
                score += weights.get("edge_E4", 0)

        elif rid == "P6":
            if application in _CLINICAL_CONTEXTS:
                score += weights.get("clinical_context", 0)

        # [RESEARCH_QUESTIONS_UX B1] normalization advisor — always relevant at medium
        # priority; elevated to high when panel ≥3 targets or sample_type is biological
        elif rid == "P7":
            # Normalization matters for every miRNA qPCR experiment
            score += weights.get("always", 0)
            if multiplex or sample_type:
                score += weights.get("multi_target", 0)
            if sample_type in _LOW_INPUT_SAMPLE_TYPES:
                score += weights.get("difficult_sample", 0)

        # [RESEARCH_QUESTIONS_UX B2] biofluid preanalytical advisor
        elif rid == "P8":
            if sample_type in _BIOFLUID_SAMPLE_TYPES:
                score += weights.get("biofluid_sample", 0)
            elif sample_type in _LOW_INPUT_SAMPLE_TYPES:
                # FFPE, low_input, exosome — partial overlap
                score += weights.get("low_input_sample", 0)

        if score <= 0:
            continue  # rule not triggered

        match = _match_level(score / total_weight)
        advice.append({
            "id": rid,
            "title": rule.get("title", ""),
            "recommendation": rule.get("recommendation", ""),
            "match": match,
            "pros": rule.get("pros", []),
            "cons": rule.get("cons", []),
            "sources": rule.get("sources", []),
            "disclaimer": rule.get("disclaimer", "For research use only."),
            "kb_version": kb_version,
            "kb_updated": kb_updated,
        })

    # Sort: high → medium → low
    _order = {"high": 0, "medium": 1, "low": 2}
    advice.sort(key=lambda a: _order.get(a["match"], 3))
    return advice
