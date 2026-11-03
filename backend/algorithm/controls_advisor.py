# ================================================================
# controls_advisor.py — Controls & contamination advice (audit SCI-11)
#
# Part 1: the control reactions this specific assay needs, with pass criteria.
# Part 2: whether this miRNA carries an elevated contamination risk.
#
# Descriptive only — nothing here is scored. Numbers that are lab policy, not
# literature, are labelled as such (NTC_DELTA_CQ_MIN, ABUNDANCE_PERCENTILE_HIGH).
# Reporting of NTC / no-RT controls: MIQE 2.0 (Bustin 2025, PMID 40272429).
# Melt-curve product identity: Ririe 1997 (PMID 9056205).
# ================================================================

import json
import os

from .constants import NTC_DELTA_CQ_MIN, ABUNDANCE_PERCENTILE_HIGH
from .specificity_check.isomir_flag import _load_db3, _find_entry

_LAB_CONTROLS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "lab_controls.json")

_NTC_CRITERION = (
    f"No amplification, or Cq ≥ {NTC_DELTA_CQ_MIN} cycles later than the "
    "latest-Cq sample (HG Lab convention)"
)


def _lab_synthetic_controls() -> list[str]:
    """miRNAs the lab handles as synthetic oligos / spike-ins (data/lab_controls.json)."""
    try:
        with open(_LAB_CONTROLS_PATH, encoding="utf-8") as f:
            return [s.lower() for s in json.load(f).get("synthetic_controls", [])]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def advise_controls(mirna_id: str, mature_rna: str, signal_method: str,
                    amplicon_tm_span: dict | None = None) -> dict:
    """Control table + contamination risk for one designed assay."""
    sybr = signal_method == "sybr"
    controls = [
        {
            "name": "NTC (water)",
            "setup": "qPCR master mix + forward + universal reverse"
                     + ("" if sybr else " + probe") + ", water instead of template",
            "checks": "Contaminated reagents or carried-over amplicon",
            "pass": _NTC_CRITERION,
        },
        {
            "name": "RT-NTC",
            "setup": "Full RT reaction (stem-loop RT primer + enzyme), water instead of RNA; "
                     "then qPCR as for samples",
            "checks": "Contamination introduced at the RT step; background from excess RT primer",
            "pass": _NTC_CRITERION,
        },
        {
            "name": "No-RT",
            "setup": "Sample RNA through the RT step without reverse transcriptase",
            "checks": "DNA in the sample (the target is RNA, so any signal is not the miRNA)",
            "pass": _NTC_CRITERION,
        },
        {
            "name": "Positive control",
            "setup": f"Synthetic RNA oligo of the mature miRNA: 5'-{mature_rna}-3'",
            "checks": "The assay amplifies its target",
            "pass": "Amplifies with Cq inside the standard-curve range",
        },
        {
            "name": "Pre-miRNA (optional)",
            "setup": "Synthetic pre-miRNA of this miRNA (hairpin sequence from miRBase)",
            "checks": "Mature vs precursor discrimination — not guaranteed for every miRNA",
            "pass": "Cq clearly later than the same amount of mature miRNA",
        },
    ]

    melt_note = None
    if sybr and amplicon_tm_span and amplicon_tm_span.get("tm_c"):
        lo, hi = amplicon_tm_span["tm_c"]
        # Identity is judged against the positive control on the same plate, not the
        # prediction: the empirical Tm formula is only good to a few °C (audit SCI-07).
        melt_note = (
            "SYBR: compare any NTC / RT-NTC melt peak with the positive control's peak on "
            "the same plate. Same temperature → it is the target amplicon (contamination); "
            "a clearly lower peak → primer-dimer. Predicted amplicon peak for orientation: "
            f"{lo}–{hi} °C depending on Mg2+."
        )

    # ── Part 2: contamination risk ────────────────────────────────
    reasons = []
    entry = _find_entry(_load_db3(), mirna_id) if mirna_id else None
    pct = (entry or {}).get("abundance_percentile")
    if pct is not None and pct >= ABUNDANCE_PERCENTILE_HIGH:
        reasons.append(
            f"Highly abundant: median {entry['median_total_rpm']:g} RPM across human samples "
            f"in isomiRdb (top {100 - pct:.0f} % of miRNAs). Abundant targets contaminate "
            "reagents and surfaces easily."
        )
    if mirna_id and mirna_id.lower() in _lab_synthetic_controls():
        reasons.append("Listed by the lab as a synthetic control / spike-in handled in the same space.")

    precautions = [
        "Prepare RT and qPCR mixes in a pre-PCR area; open amplified plates only post-PCR.",
        "Aliquot primers, water and master mix; discard an aliquot after a positive NTC.",
    ]
    if reasons:
        precautions.append("Run NTC and RT-NTC in triplicate on every plate.")

    return {
        "controls": controls,
        "melt_note": melt_note,
        "ntc_delta_cq_min": NTC_DELTA_CQ_MIN,
        "contamination": {
            "risk": "elevated" if reasons else "standard",
            "reasons": reasons,
            "precautions": precautions,
            "abundance_data": "isomiRdb (PMID 36243964)" if pct is not None else "no data for this miRNA",
        },
    }
