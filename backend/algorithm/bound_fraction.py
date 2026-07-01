# ================================================================
# bound_fraction.py — Module 7: Bound Fraction 2-step (Phase 3)
#
# Calculates the fraction (%) of primer molecules bound to target at Ta.
# Two-step model mirrors Phase 2's 2-step Tm:
#   Round 1 — binding region only (specific_region binds cDNA)  [weight 0.05]
#   Round 2 — full primer binds amplicon (after tail-complement) [weight 0.03]
#
# dH and dS obtained from primer3.calc_heterodimer(seq, revcomp(seq)):
#   thermodynamics of perfect duplex == heterodimer with own reverse-complement.
#   Verified: ThermoResult.dh, .ds, .dg, .tm are all accessible. [spec §4.4]
#
# Formula: [SL04] SantaLucia & Hicks 2004, Annual Review of Biophysics 33:415-440
#   dG  = dH - T * dS          (T in Kelvin, dH/dS in cal/mol and cal/(mol·K))
#   K   = exp(-dG / (R * T))
#   f   = 1 / (1 + sqrt(1 / ((Ct/4) * K)))  * 100  (%)
#   where Ct = total strand concentration = dna_conc / 1e9 (mol/L from nM)
# ================================================================

import math
import primer3
from functools import lru_cache
from .constants import (
    BOUND_FRACTION_RT_TEMP,
    BOUND_FRACTION_ANNEALING_TEMP,
    BOUND_FRACTION_OPT,
    BOUND_FRACTION_MIN,
    P3_DEFAULT_DNA_CONC,
)
from .thermodynamics import _get_p3_params

# Gas constant [SL04]
_R = 1.987  # cal / (mol·K)


# ── Sequence utility ──────────────────────────────────────────────

_COMPLEMENT = str.maketrans("ACGTU", "TGCAA")

def _reverse_complement(seq: str) -> str:
    return seq.upper().translate(_COMPLEMENT)[::-1]


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
    return sequence.upper().replace("U", "T")


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
    [SL04] fraction of primer molecules in duplex at the given temperature.

    fract = 1 / (1 + sqrt(1 / (Ct/4 * K))) * 100   (%)
    where:
        T  = temp_c + 273.15  (Kelvin)
        dG = dH - T * dS      (cal/mol)
        K  = exp(-dG / (R * T))
        Ct = dna_conc [nM] / 1e9  [mol/L]

    Sequence is normalized to DNA (U→T) before thermodynamic calculation —
    primers are synthesized as DNA regardless of the RNA template.
    """
    dna_conc_nm = float(params.get("primerConcentration", P3_DEFAULT_DNA_CONC))
    dH, dS = _get_dh_ds(_to_dna(sequence), params)
    T = temp_c + 273.15   # Kelvin
    dG = dH - T * dS      # cal/mol
    K = math.exp(-dG / (_R * T))
    Ct = dna_conc_nm / 1e9
    fract = (1 / (1 + math.sqrt(1 / ((Ct / 4) * K)))) * 100
    return round(min(fract, 100.0), 2)


# ── Public API ────────────────────────────────────────────────────

def calculate_bound_fraction_binding(specific_region: str, params: dict) -> float:
    """
    Round 1: % specific region (12-17 nt) bound to cDNA during RT extension step.
    Evaluated at BOUND_FRACTION_RT_TEMP = 42°C (SuperScript III RT temperature [K11]).
    Concentration: P3_DEFAULT_DNA_CONC = 200 nM (equimolar convention per [SL04]).
    [spec §4.5]
    """
    return _calculate_bound_fraction(specific_region, params, BOUND_FRACTION_RT_TEMP)


def calculate_bound_fraction_full(full_primer: str, params: dict) -> float:
    """
    Round 2: % full primer bound to amplicon at qPCR annealing temperature (60°C).
    Evaluated at BOUND_FRACTION_ANNEALING_TEMP = 60°C = Ta. [spec §4.5]
    """
    return _calculate_bound_fraction(full_primer, params, BOUND_FRACTION_ANNEALING_TEMP)


# ── Scoring ───────────────────────────────────────────────────────

def score_bound_fraction(fract: float) -> dict:
    """
    Score a bound fraction value (%). [spec §4.6]
        fract >= OPT (97%):   100
        90 <= fract < 97:     70 + (fract-90)/7 * 30  (linear)
        fract < 90:           max(0, (fract-50)/40 * 70)
    Returns {"score": int, "fraction_pct": float, "explanation": str}
    """
    if fract >= BOUND_FRACTION_OPT:
        score = 100
        band = "optimal"
    elif fract >= BOUND_FRACTION_MIN:
        score = round(70 + (fract - BOUND_FRACTION_MIN) / (BOUND_FRACTION_OPT - BOUND_FRACTION_MIN) * 30, 1)
        band = "acceptable"
    else:
        score = round(max(0.0, (fract - 50) / 40 * 70), 1)
        band = "suboptimal"

    return {
        "score": score,
        "fraction_pct": fract,
        "band": band,
    }
