# ================================================================
# algorithm/hard_filters.py — Hard-filter gate (PROMPT 3)
#
# Eliminates candidates that violate hard thresholds BEFORE the weighted
# scoring step. The rationale is this tool's own: in a weighted SUM a
# severe structural flaw can be offset by good scores on other criteria,
# so the worst cases are rejected outright instead of only penalised.
#
# Not a Busk 2014 finding. Busk scores MULTIPLICATIVELY ("all the scores
# for each parameter are multiplied"; pair score = forward × reverse ×
# anneal terms × primer dimer) and only penalises structure: 3'
# self-annealing/dimer of 5 nt × 0.1, 4 nt × 0.2; internal 8/7/6 nt ×
# 0.1/0.3/0.8 (Table 1). A primer scoring 0.2 "will not be designed in
# practice if alternatives with more optimal 3′-ends are available" —
# ranked down, not excluded. Busk's only outright exclusion is pairing
# forward and reverse primers that overlap ≥ 2 nt at the 3' end. Busk
# supports the idea only in part: a product lets one small factor drag
# the score down, which a weighted sum does not.
#
# Scope — forward primer candidates only (structure_check.run_all_structure_checks):
#   rule 1  strongest dimer anywhere: forward self-dimer and forward × universal
#           reverse, ΔG < DIMER_FULL_DG_CRITICAL (−9 kcal/mol). ΔG by RNAcofold,
#           DNA parameters, 37 °C — Kang 2017's method (structure_check.full_dimer_dg;
#           primer3 at Ta only if ViennaRNA is missing). Since algorithm 3.6.0.
#   rule 2  3'-end dimer: duplex of the LAST 8 nt (forward self, and forward vs
#           universal reverse) ΔG ≤ END_DIMER_DG_CRITICAL (−5 kcal/mol). A proxy:
#           it does not check that the 3'-terminal base itself is paired.
#   rule 3  forward hairpin ΔG ≤ −6 kcal/mol (the "critical" tier of
#           structure_check._hairpin_severity)
# The stem-loop RT primer is a hairpin by design and is never hairpin-filtered
# (its fold is scored as mfe_stemloop); the fixed universal reverse primer is
# checked once per design and only warns.
# Conditions, rules 2–3: primer3 thal (SantaLucia 2004 NN) at the annealing
# temperature (default 60 °C), mv 50 mM, Mg²⁺ 1.5 mM, dNTP 0.8 mM, primer 200 nM
# unless the user changes them. Rule 1: RNAcofold defaults (37 °C, 1.021 M Na⁺) —
# fixed, because the −9 limit was set on that scale; the user's salts do not apply.
#
# Toggle via HARD_FILTER_ENABLED in constants.py for A/B comparison.
#
# Sources (thresholds):
#   [Kang17]  DOI 10.1261/rna.061150.117 (miPrimer, RNA 24:304) — rule 1. Methods:
#             forward self-dimer and forward × universal reverse judged by ΔG,
#             limit "−9.0 ± 1 kcal/mol"; below it Kang modifies the primer (swap
#             the 5' tail or drop the dimer-forming bases). Same scope as rule 1;
#             this tool rejects the candidate instead and uses a sharp −9.0.
#             Kang computes ΔG with RNAcofold, DNA parameters (Gruber 2008), and
#             checks borderline cases in OligoAnalyzer 3.1; so does rule 1 (no
#             OligoAnalyzer step). Before 3.6.0 rule 1 used primer3 at Ta, on
#             average 5.4 kcal/mol less negative — a much looser gate
#             (benchmark/dimer_dg_method_compare.json, AUDIT REV-19).
#   [PB]      Premier Biosoft qPCR guidelines (web page) — rule 2
#   rule 3    the −6 kcal/mol tier is this tool's own, no published source
# Contrast (scoring scheme, not a source for the gate):
#   [Busk14]  DOI 10.1186/1471-2105-15-29, PMC3922658
# ================================================================

from .constants import (
    DIMER_FULL_DG_CRITICAL,
    HARD_FILTER_ENABLED,
)
from .structure_check import full_dimer_dg


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

    # ── Rule 1: Full-structure dimer ΔG < -9 kcal/mol, RNAcofold DNA [Kang17] ──
    dg_full, _method = full_dimer_dg(sc)
    if dg_full < DIMER_FULL_DG_CRITICAL:
        reasons.append(
            f"hard_dimer_full_dg (ΔG={dg_full:.2f} < {DIMER_FULL_DG_CRITICAL})"
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
