# ================================================================
# algorithm/hard_filters.py — Hard-filter gate (PROMPT 3)
#
# Eliminates candidates that violate evidence-based hard thresholds
# BEFORE the weighted scoring step. Busk 2014 showed that one
# catastrophic flaw (dimer, hairpin, 3'-overlap) collapses the
# entire assay — a weighted sum cannot compensate for it.
#
# Toggle via HARD_FILTER_ENABLED in constants.py for A/B comparison.
#
# Sources:
#   [Busk14]  DOI 10.1186/1471-2105-15-29
#   [Kang17]  DOI 10.1261/rna.061150.117
#   [PB]      Premier Biosoft qPCR guidelines
# ================================================================

from .constants import (
    DIMER_FULL_DG_CRITICAL,
    HARD_FILTER_ENABLED,
)


def apply_hard_filters(candidate: dict) -> list[str]:
    """
    Evaluate hard-filter rules against a scored candidate.

    Args:
        candidate: A forward primer candidate dict that already has
                   'structure_checks' and 'heterodimer_checks' populated
                   (i.e., after run_all_structure_checks and
                   check_all_heterodimers have run).

    Returns:
        List of rejection reasons (strings). Empty list = passes all filters.
        When HARD_FILTER_ENABLED is False, always returns [].
    """
    if not HARD_FILTER_ENABLED:
        return []

    sc = candidate.get("structure_checks", {})
    reasons = []

    # ── Rule 1: Full-structure dimer ΔG < -9 kcal/mol [Kang17] ──────
    sd_full = sc.get("self_dimer", {}).get("dg_overall", 0.0)
    hd_full = sc.get("hetero_dimer", {}).get("dg_overall", 0.0)
    if min(sd_full, hd_full) < DIMER_FULL_DG_CRITICAL:
        reasons.append(
            f"hard_dimer_full_dg (ΔG={min(sd_full, hd_full):.2f} < {DIMER_FULL_DG_CRITICAL})"
        )

    # ── Rule 2: 3'-end dimer critical — polymerase-extendable [PB] ───
    if sc.get("has_critical_flag", False):
        reasons.append("hard_dimer_3prime_critical")

    # ── Rule 3: Hairpin severity critical ────────────────────────────
    if sc.get("hairpin", {}).get("severity") == "critical":
        reasons.append(
            f"hard_hairpin_critical (ΔG={sc.get('hairpin', {}).get('dg', 0):.2f})"
        )

    return reasons
