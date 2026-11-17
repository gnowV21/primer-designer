# ================================================================
# bound_fraction.py — Module 7: Bound Fraction 2-step (Phase 3)
#
# Calculates the percentage of template strands bound by the primer (primer in
# excess, two-state duplex model).
# Two-step model mirrors Phase 2's 2-step Tm:
#   Round 1 — binding region only (specific_region on first-strand cDNA in PCR
#             cycle 1, at the user's Ta) — informational, NOT scored
#             (UNSCORED_CRITERIA_V4, audit SCI-02)
#   Round 2 — full primer on the amplicon (after tail-complement) [weight 0.03]
#
# dH and dS obtained from primer3.calc_heterodimer(seq, revcomp(seq)):
#   thermodynamics of perfect duplex == heterodimer with own reverse-complement.
#   Verified: ThermoResult.dh, .ds, .dg, .tm are all accessible. [spec §4.4]
#
# Thermodynamics: nearest-neighbour dH/dS [SL98] (primer3, design salts; Mg²⁺ via
# von Ahsen 2001), two-state duplex model [SL04] SantaLucia & Hicks 2004, Annu Rev
# Biophys Biomol Struct 33:415-440:
#   dG  = dH - T * dS          (T in Kelvin, dH/dS in cal/mol and cal/(mol·K))
#   K   = exp(-dG / (R * T))   (association constant, M⁻¹)
# Occupancy — mass action for P + T ⇌ PT with the primer in large excess over its
# template (PCR: primer 200 nM, template orders of magnitude lower), so the free
# primer concentration stays ≈ C_P:
#   θ   = K·C_P / (1 + K·C_P) × 100   (% of TEMPLATE strands bound by primer)
#   C_P = primer concentration (nM → M)
# Since algorithm 3.8.1 (AUDIT REV-24). Until 3.8.0 the code used
#   f = 1 / (1 + sqrt(1 / ((C_T/4)·K)))
# which equals the two-state solution only at 50 % and is not a mass-action result:
# at 60 °C it put the 12–17 nt specific region at a median ~1.5 % where mass action
# gives ~0.1 %. Not a scoring change: the full-primer criterion scores 100 for every
# hsa candidate either way, and the cycle-1 value is unscored.
# ================================================================

import math
import algorithm.primer3_safe as primer3  # thread-safe wrapper (see primer3_safe.py)
from functools import lru_cache
from .constants import (
    BOUND_FRACTION_ANNEALING_TEMP,
    TM_ANNEALING_TEMP_DEFAULT,
    BOUND_FRACTION_OPT,
    BOUND_FRACTION_MIN,
    P3_DEFAULT_DNA_CONC,
)
from .sequence_utils import reverse_complement as _reverse_complement, rna_to_dna as _rna_to_dna
from .thermodynamics import _get_p3_params

# Gas constant [SL04]
_R = 1.987  # cal / (mol·K)


# ── Core thermodynamics via primer3-py ────────────────────────────

@lru_cache(maxsize=4096)
def _get_dh_ds_cached(
    sequence: str,
    mv_conc: float,
    dv_conc: float,
    dntp_conc: float,
    dna_conc: float,
) -> tuple[float, float]:
    """
    Return (dH cal/mol, dS cal/(mol·K)) for perfect duplex formation.
    Uses calc_heterodimer(seq, revcomp(seq)) — the heterodimer of a sequence
    with its own reverse complement IS the perfect duplex thermodynamics. [spec §4.4]
    """
    revcomp = _reverse_complement(sequence)
    result = primer3.calc_heterodimer(
        seq1=sequence,
        seq2=revcomp,
        mv_conc=mv_conc,
        dv_conc=dv_conc,
        dntp_conc=dntp_conc,
        dna_conc=dna_conc,
    )
    return float(result.dh), float(result.ds)


def _to_dna(sequence: str) -> str:
    """Normalize to uppercase DNA (U→T) before passing to primer3."""
    return _rna_to_dna(sequence.upper())


def _get_dh_ds(sequence: str, params: dict) -> tuple[float, float]:
    p3 = _get_p3_params(params)
    return _get_dh_ds_cached(
        _to_dna(sequence),
        p3["mv_conc"],
        p3["dv_conc"],
        p3["dntp_conc"],
        p3["dna_conc"],
    )


# ── Bound fraction calculation ────────────────────────────────────

def _calculate_bound_fraction(sequence: str, params: dict, temp_c: float) -> float:
    """
    Percentage of template strands bound by the primer at temp_c, two-state
    model with the primer in excess (see the module header):

        θ = K·C_P / (1 + K·C_P) × 100   (%)
    where:
        T   = temp_c + 273.15            (Kelvin)
        dG  = dH - T * dS                (cal/mol; dH, dS of the perfect duplex)
        K   = exp(-dG / (R * T))         (M⁻¹)
        C_P = primerConcentration [nM] / 1e9   [M]

    Sequence is normalized to DNA (U→T) before thermodynamic calculation —
    primers are synthesized as DNA regardless of the RNA template.
    """
    primer_conc_nm = float(params.get("primerConcentration", P3_DEFAULT_DNA_CONC))
    if primer_conc_nm <= 0:
        return 0.0
    dH, dS = _get_dh_ds(_to_dna(sequence), params)
    T = temp_c + 273.15   # Kelvin
    dG = dH - T * dS      # cal/mol
    # K·C_P = exp(ln C_P − ΔG/RT), computed in log space so a very stable duplex
    # cannot overflow math.exp.
    x = math.log(primer_conc_nm / 1e9) - dG / (_R * T)
    theta = 1.0 / (1.0 + math.exp(-x)) if x > -700 else 0.0   # = K·C_P / (1 + K·C_P)
    return round(theta * 100, 3)


# ── Public API ────────────────────────────────────────────────────

def calculate_bound_fraction_binding(specific_region: str, params: dict) -> float:
    """
    Round 1: % of first-strand cDNA bound by the specific region (12-17 nt) in
    PCR cycle 1. The forward primer is not present during RT, so this is evaluated
    at the qPCR annealing temperature (params["annealingTemp"], default 60 °C).
    Only the specific region can pair in cycle 1 — the 5' tail has no template yet.
    Primer concentration: params["primerConcentration"], default 200 nM.
    Informational only (audit SCI-02).
    """
    return _calculate_bound_fraction(specific_region, params, annealing_temp_c(params))


def annealing_temp_c(params: dict) -> float:
    """User's qPCR annealing temperature (°C), falling back to the default Ta."""
    try:
        return float(params.get("annealingTemp", TM_ANNEALING_TEMP_DEFAULT))
    except (TypeError, ValueError):
        return float(TM_ANNEALING_TEMP_DEFAULT)


def calculate_bound_fraction_full(full_primer: str, params: dict) -> float:
    """
    Round 2: % of amplicon strands bound by the full primer.
    Evaluated at BOUND_FRACTION_ANNEALING_TEMP = 55°C = Tm_target − 5°C.
    Evaluating at Tm itself (60°C) gives ~50% by definition of Tm, which is
    uninformative. Ta = Tm−5°C is the effective primer-binding step. [spec §4.5]
    """
    return _calculate_bound_fraction(full_primer, params, BOUND_FRACTION_ANNEALING_TEMP)


# ── Scoring ───────────────────────────────────────────────────────

def score_bound_fraction(fract: float) -> dict:
    """
    Score a bound fraction value (%). [spec §4.6]
        fract >= OPT (80%):              100
        MIN (60%) <= fract < OPT (80%):  70–100  (linear)
        fract < MIN (60%):               0–70    (proportional to MIN)
    Returns {"score": int, "fraction_pct": float, "band": str}
    """
    if fract >= BOUND_FRACTION_OPT:
        score = 100
        band = "optimal"
    elif fract >= BOUND_FRACTION_MIN:
        score = round(70 + (fract - BOUND_FRACTION_MIN) / (BOUND_FRACTION_OPT - BOUND_FRACTION_MIN) * 30, 1)
        band = "acceptable"
    else:
        # Linear: 0% → 0, BOUND_FRACTION_MIN → 70
        score = round(max(0.0, fract / BOUND_FRACTION_MIN * 70), 1)
        band = "suboptimal"

    return {
        "score": score,
        "fraction_pct": fract,
        "band": band,
    }
