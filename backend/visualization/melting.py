# ================================================================
# visualization/melting.py — PART C: simulated melting curve (SPEC §C)
#
# Two-state van 't Hoff transition [SL98]. Tm ALWAYS comes from the caller
# (predicted_amplicon_tm) — never recomputed here (SPEC §C.1.3). ΔH sets peak
# WIDTH only: NN via thermodynamics.amplicon_dh_cal when the amplicon is short
# enough, else a per-bp fallback (dh_source='approximate').
#
# Derivative is analytic, not finite-difference (SPEC §C.1.2). Deterministic.
# ================================================================

import math
from dataclasses import dataclass

from algorithm.thermodynamics import amplicon_dh_cal
from .constants import (
    VIZ_MELT_T_START, VIZ_MELT_T_END, VIZ_MELT_T_STEP, VIZ_DH_PER_BP,
)

_R = 1.987          # cal/(mol·K) [SL98]
_KELVIN = 273.15


@dataclass
class MeltingModel:
    temperatures: list      # °C
    f_norm: list            # normalized fluorescence θ(T) in [0, 1]
    neg_dfdt: list          # −dF/dT
    peak_temperature: float # °C (== Tm)
    peak_height: float      # max of −dF/dT
    dh_cal_per_mol: float   # melting ΔH used (positive, cal/mol)
    dh_source: str          # 'provided' | 'nearest_neighbor' | 'approximate'
    tm_celsius: float


def _temperature_grid():
    # Integer tenths to avoid cumulative float error (SPEC §C.4).
    start = round(VIZ_MELT_T_START * 10)
    end = round(VIZ_MELT_T_END * 10)
    step = round(VIZ_MELT_T_STEP * 10)
    return [t / 10.0 for t in range(start, end + 1, step)]


def _resolve_dh(amplicon_seq, dh_cal_per_mol, params):
    """Return (dh_melting_positive_cal_per_mol, source)."""
    if dh_cal_per_mol is not None:
        return abs(float(dh_cal_per_mol)), "provided"
    raw = amplicon_dh_cal(amplicon_seq, params or {})
    if raw is not None:
        return abs(raw), "nearest_neighbor"        # formation ΔH is negative → melting = |ΔH|
    return float(VIZ_DH_PER_BP * len(amplicon_seq)), "approximate"


def simulate_melting(amplicon_seq: str, tm_celsius: float,
                     dh_cal_per_mol: float | None = None,
                     params: dict | None = None) -> MeltingModel:
    """Simulate the SYBR melt curve of `amplicon_seq` with peak at `tm_celsius`.

    θ(T)    = 1 / (1 + exp[(ΔH_m/R)·(1/Tm − 1/T)])              [SL98]
    −dF/dT  = [e^u / (1+e^u)²] · ΔH_m / (R·T²),  u = (ΔH_m/R)(1/Tm − 1/T)
    peak at T = Tm, peak height = ΔH_m / (4·R·Tm²)
    """
    dh_m, source = _resolve_dh(amplicon_seq, dh_cal_per_mol, params)
    tm_k = tm_celsius + _KELVIN

    temps = _temperature_grid()
    f_norm, neg_dfdt = [], []
    for t_c in temps:
        t_k = t_c + _KELVIN
        u = (dh_m / _R) * (1.0 / tm_k - 1.0 / t_k)
        eu = math.exp(u)
        theta = 1.0 / (1.0 + eu)
        f_norm.append(theta)
        neg_dfdt.append((eu / (1.0 + eu) ** 2) * dh_m / (_R * t_k * t_k))

    peak_height = dh_m / (4.0 * _R * tm_k * tm_k)   # analytic value at T = Tm

    return MeltingModel(
        temperatures=temps,
        f_norm=f_norm,
        neg_dfdt=neg_dfdt,
        peak_temperature=tm_celsius,
        peak_height=peak_height,
        dh_cal_per_mol=dh_m,
        dh_source=source,
        tm_celsius=tm_celsius,
    )
