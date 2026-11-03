# ================================================================
# visualization/gel.py — PART D: simulated agarose gel (SPEC §D)
#
# Semi-log migration model [Helling63]: migration distance ∝ −log10(size).
#   y(N) = Y_TOP + H_LANE · [log10(N_max) − log10(N)] / [log10(N_max) − log10(N_min)]
# Larger fragment → smaller y (closer to the well). This is a RELATIVE-SIZE
# illustration, not a real migration-distance prediction (SPEC §2 note, §0.4).
# Deterministic; no noise/blur/fake photo gradient (SPEC §D.3).
# ================================================================

import math
from dataclasses import dataclass

from .constants import (
    VIZ_GEL_LADDER_BP, VIZ_GEL_REFERENCE_BP, VIZ_GEL_LANE_HEIGHT, VIZ_GEL_Y_TOP,
)


@dataclass
class GelModel:
    ladder_bands: list      # [(bp, y, is_reference), ...]
    product_band: tuple     # (bp, y)
    out_of_range: bool
    n_min: int
    n_max: int
    y_top: float
    lane_height: float


def _y_position(n, n_min, n_max, y_top, h_lane):
    """Semi-log migration y for size `n` bp (clamped to the ladder span)."""
    n_clamped = min(max(n, n_min), n_max)
    span = math.log10(n_max) - math.log10(n_min)
    frac = (math.log10(n_max) - math.log10(n_clamped)) / span
    return y_top + h_lane * frac


def simulate_gel(amplicon_bp: int, ladder=None) -> GelModel:
    ladder = list(ladder) if ladder is not None else list(VIZ_GEL_LADDER_BP)
    n_min, n_max = min(ladder), max(ladder)
    y_top, h_lane = VIZ_GEL_Y_TOP, VIZ_GEL_LANE_HEIGHT

    ladder_bands = [
        (bp, round(_y_position(bp, n_min, n_max, y_top, h_lane), 2), bp in VIZ_GEL_REFERENCE_BP)
        for bp in ladder
    ]
    product_y = round(_y_position(amplicon_bp, n_min, n_max, y_top, h_lane), 2)
    out_of_range = not (n_min <= amplicon_bp <= n_max)

    return GelModel(
        ladder_bands=ladder_bands,
        product_band=(amplicon_bp, product_y),
        out_of_range=out_of_range,
        n_min=n_min,
        n_max=n_max,
        y_top=y_top,
        lane_height=h_lane,
    )
