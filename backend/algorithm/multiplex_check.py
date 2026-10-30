# ================================================================
# multiplex_check.py — Cross-dimer check for multiplex miRNA panels
# Phase 6 PART B (SPEC_phase6 §B.2)
#
# Pairwise forward×forward, forward×probe, probe×probe, each×universal_reverse.
# Universal reverse is fixed → checked once per forward primer, not pairwise.
#
# Risk thresholds reuse existing HETERODIMER_* constants [IDT][Kang17].
# Panel size cap: MULTIPLEX_PANEL_MAX [Bell17] — warn if exceeded.
#
# Sources: [Bell17] Bell 2017 Methods Mol Biol; [Murray21] Murray 2021;
#          [IDT] OligoAnalyzer; [Kang17] dimer −9 kcal/mol threshold
# ================================================================

import algorithm.primer3_safe as primer3  # thread-safe wrapper (see primer3_safe.py)

from .constants import (
    HETERODIMER_HIGH_RISK_DG, HETERODIMER_LOW_RISK_DG, HETERODIMER_3PRIME_MIN_BP,
    UNIVERSAL_REVERSE_PRIMER, MULTIPLEX_PANEL_MAX,
)
from .thermodynamics import _get_p3_params

_COMP_TRANS = str.maketrans("ACGTU", "TGCAA")


def check_multiplex_panel(primer_sets: list, params: dict) -> dict:
    """
    Check pairwise cross-dimer interactions for a multiplex miRNA panel.

    Args:
        primer_sets: list of dicts, each with:
            {"mirna_id": str, "forward": str, "probe": str | None}
        params: user formData for salt/Mg conditions.

    Returns:
        {pairs, worst_risk, panel_ok, warnings, recommendations}
    """
    warnings = []
    if len(primer_sets) > MULTIPLEX_PANEL_MAX:
        warnings.append(
            f"Panel size {len(primer_sets)} exceeds recommended maximum "
            f"of {MULTIPLEX_PANEL_MAX} assays [Bell17]. Cross-interaction risk increases. "
            f"Consider splitting into sub-panels."
        )

    p3    = _get_p3_params(params)
    temp  = float(params.get("annealingTemp", 60.0))
    pairs = []

    n = len(primer_sets)
    for i in range(n):
        for j in range(i + 1, n):
            a = primer_sets[i]
            b = primer_sets[j]
            # forward × forward
            pairs.append(_check_pair_entry(
                a["mirna_id"], b["mirna_id"],
                a["forward"], b["forward"],
                "forward×forward", p3, temp
            ))
            # forward_a × probe_b
            if b.get("probe"):
                pairs.append(_check_pair_entry(
                    a["mirna_id"], b["mirna_id"],
                    a["forward"], b["probe"],
                    "forward×probe", p3, temp
                ))
            # probe_a × forward_b
            if a.get("probe"):
                pairs.append(_check_pair_entry(
                    a["mirna_id"], b["mirna_id"],
                    a["probe"], b["forward"],
                    "probe×forward", p3, temp
                ))
            # probe_a × probe_b
            if a.get("probe") and b.get("probe"):
                pairs.append(_check_pair_entry(
                    a["mirna_id"], b["mirna_id"],
                    a["probe"], b["probe"],
                    "probe×probe", p3, temp
                ))

        # each forward × universal reverse (once per assay, not pairwise)
        pairs.append(_check_pair_entry(
            primer_sets[i]["mirna_id"], "universal_reverse",
            primer_sets[i]["forward"], UNIVERSAL_REVERSE_PRIMER,
            "forward×universal_reverse", p3, temp
        ))

    risk_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "SAFE": 0}
    worst_risk = max((p["risk"] for p in pairs), key=lambda r: risk_order.get(r, 0), default="SAFE")
    panel_ok   = worst_risk not in ("HIGH",)

    high_pairs = [p for p in pairs if p["risk"] == "HIGH"]
    recommendations = _build_recommendations(high_pairs) if high_pairs else [
        "No HIGH-risk cross-interactions detected. Panel appears compatible."
    ]

    warnings.append(
        "Note: this check covers multiplex RT/pre-amplification (all primers in same tube). "
        "singleplex qPCR readout: cross-interactions occur during RT and pre-amp steps only [Bell17][Murray21]."
    )

    return {
        "pairs":           pairs,
        "worst_risk":      worst_risk,
        "panel_ok":        panel_ok,
        "warnings":        warnings,
        "recommendations": recommendations,
    }


# ── Internal helpers ──────────────────────────────────────────────

def _check_pair_entry(id_a: str, id_b: str, seq_a: str, seq_b: str, pair_type: str, p3: dict, temp: float) -> dict:
    dg      = _calc_hetero_dg(seq_a, seq_b, p3, temp)
    overlap, bp = _detect_3prime_overlap(seq_a, seq_b)
    risk    = _classify_risk(dg, overlap)
    return {
        "assay_a":    id_a,
        "assay_b":    id_b,
        "type":       pair_type,
        "dg":         dg,
        "three_prime_overlap": overlap,
        "three_prime_bp":      bp,
        "risk":       risk,
        "note":       _risk_note(id_a, id_b, pair_type, dg, risk, overlap, bp),
    }


def _calc_hetero_dg(seq1: str, seq2: str, p3: dict, temp_c: float) -> float:
    try:
        r = primer3.calc_heterodimer(
            seq1=seq1, seq2=seq2,
            mv_conc=p3["mv_conc"], dv_conc=p3["dv_conc"],
            dntp_conc=p3["dntp_conc"], dna_conc=p3["dna_conc"],
            temp_c=temp_c,
        )
        return round(float(r.dg) / 1000, 2)
    except Exception:
        return 0.0


def _detect_3prime_overlap(seq1: str, seq2: str) -> tuple:
    """Detect consecutive Watson-Crick complement at 3' ends (same as heterodimer.py)."""
    s1, s2 = seq1.upper(), seq2.upper()
    limit   = min(len(s1), len(s2))
    count   = 0
    for i in range(1, limit + 1):
        if s1[-i].translate(_COMP_TRANS) == s2[-i]:
            count += 1
        else:
            break
    return count >= HETERODIMER_3PRIME_MIN_BP, count


def _classify_risk(dg: float, three_prime_overlap: bool) -> str:
    """§B.4 risk classification (SAFE / LOW / MEDIUM / HIGH)."""
    if three_prime_overlap and dg <= HETERODIMER_HIGH_RISK_DG:
        return "HIGH"
    if dg <= HETERODIMER_HIGH_RISK_DG:
        return "MEDIUM"
    if dg <= HETERODIMER_LOW_RISK_DG:
        return "LOW"
    return "SAFE"


def _risk_note(id_a: str, id_b: str, pair_type: str, dg: float, risk: str, overlap: bool, bp: int) -> str:
    base = f"{id_a} × {id_b} [{pair_type}]: ΔG = {dg:.2f} kcal/mol"
    if risk == "HIGH":
        return f"{base} — HIGH: strong 3'-end interaction ({bp} bp), extension artifact likely."
    if risk == "MEDIUM":
        return f"{base} — MEDIUM: strong dimer, no 3'-overlap; primer availability may drop."
    if risk == "LOW":
        return f"{base} — LOW: weak dimer, monitor efficiency."
    return f"{base} — SAFE."


def _build_recommendations(high_pairs: list) -> list:
    assay_ids = set()
    for p in high_pairs:
        assay_ids.add(p["assay_a"])
        assay_ids.add(p["assay_b"])
    recs = [
        f"HIGH cross-dimer risk between: {', '.join(sorted(assay_ids))}. "
        "Recommendations: (1) Run affected assays in separate tubes. "
        "(2) For multiplex RT, check overhang×overhang only (body is shared). "
        "(3) Optimize primer concentrations to minimise competition."
    ]
    return recs
