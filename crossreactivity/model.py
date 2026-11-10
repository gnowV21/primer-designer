"""
model.py — R(i, j): how strongly the assay designed for miRNA i reports miRNA j.

The webtool's own assay model (backend/algorithm/specificity_check/assay_model.py)
is reused unchanged, so the matrix and the webtool can never disagree:

    ΔCq_assay = ΔCq_RT + ΔCq_FWD        (both offset-aware, ±2 nt at each end)
    p_RT  = 2^−ΔCq_RT                   fraction of j reverse-transcribed by i's RT primer
    p_PCR = 2^−ΔCq_FWD                  efficiency of i's forward primer on j's cDNA
    R     = p_RT × p_PCR = 2^−ΔCq_assay (cross-signal relative to the perfect match)

R(i, i) = 1. The matrix is asymmetric: the RT overhang and forward region are
those of assay i, read against miRNA j.

ΔG columns are reported, not used in R (R's thermodynamic term is the forward
duplex Tm gap already inside ΔCq_FWD). dG_rt uses DNA:DNA parameters on the DNA
analogue of the RNA:DNA duplex (approx_hybrid = True): Sugimoto 1995 RNA:DNA
parameters exist in the backend but cover Watson–Crick pairs only, and most pairs
here carry mismatches.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from functools import lru_cache

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_BACKEND = os.path.join(_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import algorithm.primer3_safe as primer3  # noqa: E402
from algorithm.constants import (  # noqa: E402
    ASSAY_FWD_TERMINAL_GROUP,
    P3_RT_DNA_CONC, P3_RT_DNTP_CONC, P3_RT_DV_CONC, P3_RT_MV_CONC,
)
from algorithm.specificity_check.assay_model import evaluate  # noqa: E402
from algorithm.specificity_check.overhang_collision import _tm_gap_fn  # noqa: E402
from algorithm.thermodynamics import _get_p3_params  # noqa: E402

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
_COMP = {"A": "T", "T": "A", "G": "C", "C": "G"}

LEVELS = ("HIGH", "MEDIUM", "LOW", "NONE")


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dna(seq: str) -> str:
    return seq.upper().replace("U", "T")


def revcomp(seq: str) -> str:
    return "".join(_COMP.get(b, "N") for b in reversed(seq))


def level_for(delta_cq: float, levels: dict) -> str:
    if delta_cq < levels["high_below_delta_cq"]:
        return "HIGH"
    if delta_cq < levels["medium_below_delta_cq"]:
        return "MEDIUM"
    if delta_cq < levels["low_below_delta_cq"]:
        return "LOW"
    return "NONE"


@dataclass(frozen=True)
class Assay:
    """Primer set #1 designed for one miRNA."""
    mirna: str
    sequence: str            # mature miRNA, DNA alphabet
    overhang_len: int        # read from the RT primer: len(RT) − 44
    fwd_specific_len: int
    forward_primer: str
    rt_primer: str


class AssayScorer:
    """Scores one assay against any number of miRNAs. Holds the assay's own Tm-gap
    cache, so build one per assay (row) and reuse it across the row."""

    def __init__(self, assay: Assay, cfg: dict, qpcr_params: dict | None = None):
        self.a = assay
        self.cfg = cfg
        self.levels = cfg["levels"]
        self.p3 = _get_p3_params(qpcr_params or {})
        self.tm_gap = _tm_gap_fn(assay.sequence, assay.fwd_specific_len, self.p3)
        self.rt_p3 = {"mv_conc": P3_RT_MV_CONC, "dv_conc": P3_RT_DV_CONC,
                      "dntp_conc": P3_RT_DNTP_CONC, "dna_conc": P3_RT_DNA_CONC}

    def lower_bound(self, other: str) -> float:
        """ΔCq without the duplex-Tm term — a proven lower bound of the exact ΔCq,
        since ΔCq_FWD = max(table, Tm term). Used as the screen."""
        return evaluate(self.a.sequence, other, self.a.overhang_len,
                        self.a.fwd_specific_len, None, full=True)["delta_cq"]

    def score(self, target_mirna: str, other: str, with_dg: bool = True) -> dict:
        """Exact record for one (assay, target) pair; `other` in DNA alphabet."""
        a = self.a
        ev = evaluate(a.sequence, other, a.overhang_len, a.fwd_specific_len,
                      self.tm_gap, full=True)
        rt, fwd = ev["rt"], ev["fwd"]
        dcq = ev["delta_cq"]
        level = level_for(dcq, self.levels)
        p_rt = 2.0 ** -rt["delta_cq"]
        p_pcr = 2.0 ** -fwd["delta_cq"]
        rec = {
            "assay_mirna": a.mirna,
            "target_mirna": target_mirna,
            "R": 0.0 if level == "NONE" else p_rt * p_pcr,
            "level": level,
            "delta_cq": dcq,
            "p_RT": p_rt,
            "p_PCR": p_pcr,
            "rt_shift": rt["shift_3p"],
            "rt_mismatches": len(rt["mismatch_positions"]),
            "rt_3p_class": self._rt_3p_class(other, rt),
            "pcr_shift": fwd["shift_5p"],
            "pcr_mismatches": len(fwd["mismatch_from_3p"]),
            "pcr_3p_class": self._pcr_3p_class(other, fwd),
            "category": ev["category"],
            "dG_rt": None,
            "dG_pcr": None,
            "approx_hybrid": True,
        }
        if with_dg:
            rec["dG_rt"] = self._dg_rt(other, rt["shift_3p"])
            rec["dG_pcr"] = self._dg_pcr(other, fwd["shift_5p"])
        return rec

    # ── per-step descriptors ──────────────────────────────────────

    def _rt_start(self, other: str, k: int) -> int:
        """Index in `other` facing the RT primer's 3' terminus (overhang window start)."""
        return len(other) - k - self.a.overhang_len

    def _rt_3p_class(self, other: str, rt: dict) -> str:
        """Pair at the RT primer's 3' terminus: MATCH / WOBBLE (rG·dT) / MISMATCH /
        NO_TEMPLATE (the off-target is too short to face it)."""
        j = self._rt_start(other, rt["shift_3p"])
        if j < 0:
            return "NO_TEMPLATE"
        t = self.a.sequence[-self.a.overhang_len]
        o = other[j]
        if o == t:
            return "MATCH"
        return "WOBBLE" if (t == "A" and o == "G") else "MISMATCH"

    def _pcr_3p_class(self, other: str, fwd: dict) -> str:
        """Forward-primer 3'-terminal pair, grouped as in Stadhouders 2010 (via the
        backend's ASSAY_FWD_TERMINAL_GROUP): MATCH / minor / intermediate / severe /
        NO_TEMPLATE."""
        L = self.a.fwd_specific_len
        j_end = L - 1 + fwd["shift_5p"]
        if not 0 <= j_end < len(other):
            return "NO_TEMPLATE"
        p = self.a.sequence[L - 1]
        if other[j_end] == p:
            return "MATCH"
        return ASSAY_FWD_TERMINAL_GROUP.get((p, _COMP.get(other[j_end], "N")), "severe")

    # ── ΔG (reported, not used in R) ──────────────────────────────

    def _dg_rt(self, other: str, k: int) -> float | None:
        """RT overhang : miRNA j in the chosen register (DNA:DNA approximation)."""
        n = self.a.overhang_len
        start = self._rt_start(other, k)
        window = other[max(start, 0): max(start + n + 1, 0)]
        if not window:
            return None
        seg = revcomp(self.a.sequence[-n:])
        r = primer3.calc_heterodimer(seg, window, temp_c=self.cfg["dg_rt"]["temp_c"],
                                     **self.rt_p3)
        return round(r.dg / 1000.0, 2)

    def _dg_pcr(self, other: str, r_shift: int) -> float | None:
        """Forward specific region on j's cDNA, anchored register + 1 base (the A2 rule)."""
        L = self.a.fwd_specific_len
        window = other[max(r_shift, 0): L + r_shift + 1]
        if not window:
            return None
        region = self.a.sequence[:L]
        r = primer3.calc_heterodimer(region, revcomp(window),
                                     temp_c=self.cfg["dg_pcr"]["temp_c"], **self.p3)
        return round(r.dg / 1000.0, 2)


@lru_cache(maxsize=1)
def load_mature(index_path: str, species: str) -> dict[str, str]:
    """{name: DNA sequence} for one species from the backend's miRBase index."""
    path = index_path if os.path.isabs(index_path) else os.path.join(_ROOT, index_path)
    with open(path, encoding="utf-8") as f:
        idx = json.load(f)
    return {n: dna(s) for n, s in idx["mature"][species].items()}


def index_metadata(index_path: str) -> dict:
    path = index_path if os.path.isabs(index_path) else os.path.join(_ROOT, index_path)
    with open(path, encoding="utf-8") as f:
        meta = json.load(f)["_metadata"]
    return {k: meta.get(k) for k in ("mirbase_release", "mature_fa_sha256", "build_date")}
