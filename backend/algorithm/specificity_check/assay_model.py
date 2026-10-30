"""
assay_model.py — assay-level cross-reactivity of a stem-loop RT-qPCR assay as a ΔCq.

An off-target miRNA gives signal only if it passes BOTH steps:
  RT  — the stem-loop RT primer's 3' overhang captures it and is extended
        (RNA:DNA; the primer's 3' terminus pairs with the 5'-most nt of the
        miRNA's 3'-terminal window, the stem junction with the miRNA's last nt);
  FWD — the forward primer primes the off-target's cDNA. Only the first cycles
        pay for a mismatch: later products carry the primer sequence.
The delays add:   ΔCq_assay ≈ ΔCq_RT + ΔCq_FWD,   cross-reactivity ≈ 2^−ΔCq × 100 %.

Both axes are offset-aware: each end of the off-target may be shifted by up to
ASSAY_MAX_END_SHIFT nt relative to the target (isomiRs, mis-annotated ends), and
the register giving the SMALLEST delay is kept. A fixed-position comparison turns
every 1-nt shift into a large Hamming distance — a false "discriminated" for
exactly the variants most likely to co-amplify.

Values are lower bounds of published ranges (constants ASSAY_*), so the model
predicts the most cross-reactivity the data allow. They were measured with TaqMan
probes; for SYBR the prediction is an optimistic bound.
"""

from typing import Callable, Optional

from ..constants import (
    ASSAY_MAX_END_SHIFT,
    ASSAY_DCQ_RT_3P_LONGER, ASSAY_DCQ_RT_3P_SHORT1, ASSAY_DCQ_RT_3P_SHORT2,
    ASSAY_DCQ_RT_SHIFT_RANGE, ASSAY_SHIFT_EVIDENCE_NOTE,
    ASSAY_DCQ_RT_WOBBLE, ASSAY_DCQ_RT_MM_NEAR, ASSAY_DCQ_RT_MM_FAR, ASSAY_DCQ_RT_MULTI,
    ASSAY_RT_NEAR_POSITIONS,
    ASSAY_DCQ_FWD_TERMINAL, ASSAY_FWD_TERMINAL_GROUP, ASSAY_DCQ_FWD_POS2,
    ASSAY_DCQ_FWD_POS3_5, ASSAY_FWD_3P_WINDOW, ASSAY_DCQ_FWD_MULTI_3P,
    ASSAY_DCQ_FWD_NO_TEMPLATE, ASSAY_DCQ_PER_TM_DEGREE,
    ASSAY_DCQ_COAMPLIFIED_BELOW, ASSAY_DCQ_DISCRIMINATED_AT,
    SELF_MIN_OVERLAP,
)

_COMP = {"A": "T", "T": "A", "G": "C", "C": "G"}


def _shifts():
    """0 first, then ±1, ±2 — ties keep the unshifted register."""
    out = [0]
    for d in range(1, ASSAY_MAX_END_SHIFT + 1):
        out += [d, -d]
    return out


# ── variant category ─────────────────────────────────────────────

def variant_category(target: str, other: str) -> str:
    """How another miRBase ENTRY relates to the target, by sequence alone:
    'same_sequence' | 'shifted_5p' | 'shifted_3p' | 'other' (DNA alphabet).

    These are miRBase entries whose ends differ by ≤ ASSAY_MAX_END_SHIFT nt over an
    identical overlap of ≥ SELF_MIN_OVERLAP nt — in practice a synonym/renamed entry
    (hsa-miR-25 vs hsa-miR-25-3p) or a paralogue from another locus (mmu-miR-467a vs
    467b), NOT a biological isomiR: processing variants and tailed forms have no
    miRBase entries of their own, and are covered by the isomiRdb-based flags in
    isomir_flag.py. Whatever their origin, no primer design separates them from the
    target, so they are reported and not scored [Magee17]: a 5'-shifted sequence is
    bound by both primers, a 3'-shifted one is only partly resolved by the RT overhang.
    """
    if other == target:
        return "same_sequence"
    for r in _shifts():                       # other[i + r] faces target[i]
        lo, hi = max(0, -r), min(len(target), len(other) - r)
        if hi - lo < SELF_MIN_OVERLAP:
            continue
        if any(target[i] != other[i + r] for i in range(lo, hi)):
            continue
        d3 = (len(other) - r) - len(target)   # >0: other's 3' end longer
        if abs(d3) > ASSAY_MAX_END_SHIFT:
            continue
        if r == 0 and d3 == 0:
            return "same_sequence"
        return "shifted_3p" if r == 0 else "shifted_5p"
    return "other"


# ── RT axis ──────────────────────────────────────────────────────

def rt_axis(target: str, other: str, overhang_len: int) -> dict:
    """ΔCq of the RT step for `other`, best register over 3'-end shifts.

    k = how far the off-target's 3' end reaches past the target's (k>0 longer: the
    extra nt sit against the stem; k<0 shorter: the junction-side overhang bases
    are unpaired, the primer 3' end still pairs).
    """
    win = target[-overhang_len:]
    best = None
    for k in _shifts():
        start = len(other) - k - overhang_len      # other index facing win[0]
        mismatches, wobble = [], []
        for i, t in enumerate(win):
            j = start + i
            if j >= len(other):
                continue                           # junction side, accounted by k
            o = other[j] if j >= 0 else None       # j < 0: nothing opposite → mismatch
            if o != t:
                mismatches.append(i + 1)           # 1 = RT primer 3' terminus
                # rG·dT: target A (primer T) faced by an off-target G [Chen05].
                wobble.append(t == "A" and o == "G")
        # A shift value is a lower bound with a wide measured range (n = 1–2 miRNAs);
        # shift_range travels with it so every caller can show the uncertainty.
        if k > 0:
            shift_cq, shift_key = ASSAY_DCQ_RT_3P_LONGER, "longer"
            shift_basis = f"3′ end {k} nt longer"
        elif k == 0:
            shift_cq, shift_key, shift_basis = 0.0, None, ""
        elif k == -1:
            shift_cq, shift_key = ASSAY_DCQ_RT_3P_SHORT1, "short1"
            shift_basis = "3′ end 1 nt shorter"
        else:
            shift_cq, shift_key = ASSAY_DCQ_RT_3P_SHORT2, "short2"
            shift_basis = f"3′ end {-k} nt shorter"
        shift_range = ASSAY_DCQ_RT_SHIFT_RANGE.get(shift_key) if shift_key else None
        if shift_range:
            lo, hi, n = shift_range
            shift_basis += f" (measured {lo:g}–{hi:g} Ct, n = {n} miRNA)"
        if not mismatches:
            mm_cq, mm_basis = 0.0, "overhang pairs fully"
        elif len(mismatches) >= 2:
            mm_cq, mm_basis = ASSAY_DCQ_RT_MULTI, f"{len(mismatches)} overhang mismatches"
        else:
            p = mismatches[0]
            positional = ASSAY_DCQ_RT_MM_NEAR if p <= ASSAY_RT_NEAR_POSITIONS else ASSAY_DCQ_RT_MM_FAR
            mm_cq = min(positional, ASSAY_DCQ_RT_WOBBLE) if wobble[0] else positional
            mm_basis = (f"1 mismatch at position {p} from the RT primer 3′ end"
                        + (" (rG·dT wobble)" if wobble[0] else ""))
        cq = round(shift_cq + mm_cq, 2)
        if best is None or cq < best["delta_cq"]:
            best = {
                "delta_cq": cq,
                "shift_3p": k,
                "shift_delta_cq": shift_cq,
                # (low, high, n_mirnas) of the published measurements, or None when the
                # register is unshifted. delta_cq uses the low end.
                "shift_range": list(shift_range) if shift_range else None,
                "shift_evidence_note": ASSAY_SHIFT_EVIDENCE_NOTE if shift_range else None,
                "mismatch_positions": mismatches,
                "wobble": any(wobble),
                "basis": "; ".join(b for b in (shift_basis, mm_basis) if b),
            }
    return best


# ── FWD axis ─────────────────────────────────────────────────────

def _fwd_table(primer_region: str, other: str, r: int) -> Optional[dict]:
    """Table ΔCq for one 5' register r (other[i + r] faces primer_region[i])."""
    L = len(primer_region)
    j_end = L - 1 + r
    if j_end < 0 or j_end >= len(other):
        return {"delta_cq": ASSAY_DCQ_FWD_NO_TEMPLATE, "mismatch_from_3p": [],
                "basis": "primer 3′ end runs past the off-target's end"}
    mm = []                                        # positions from the primer 3' end (1 = terminal)
    for i in range(L):
        j = i + r
        if 0 <= j < len(other) and other[j] != primer_region[i]:
            mm.append(L - i)
    mm.sort()
    near = [q for q in mm if q <= ASSAY_FWD_3P_WINDOW]
    terminal_pair = None
    if mm and mm[0] == 1:
        # primer base : template base (template = complement of the off-target sense base)
        terminal_pair = (primer_region[-1], _COMP.get(other[j_end], "N"))
    if not near:
        cq, basis = 0.0, ("no mismatch" if not mm else
                          f"{len(mm)} mismatch(es) ≥{ASSAY_FWD_3P_WINDOW + 1} nt from the 3′ end")
    elif len(near) >= 2:
        # Kwok90's terminal-T exception covers a DOUBLE mismatch (T plus one more);
        # three or more near the 3' end are outside what was tested.
        if terminal_pair and terminal_pair[0] == "T" and len(near) == 2:
            group = ASSAY_FWD_TERMINAL_GROUP.get(terminal_pair, "severe")
            cq = ASSAY_DCQ_FWD_TERMINAL[group]
            basis = (f"{len(near)} mismatches in the last {ASSAY_FWD_3P_WINDOW} nt, terminal "
                     f"T ({'–'.join(terminal_pair)}) still extends [Kwok90]")
        else:
            cq = ASSAY_DCQ_FWD_MULTI_3P
            basis = f"{len(near)} mismatches in the last {ASSAY_FWD_3P_WINDOW} nt"
    elif near[0] == 1:
        group = ASSAY_FWD_TERMINAL_GROUP.get(terminal_pair, "severe")
        cq = ASSAY_DCQ_FWD_TERMINAL[group]
        basis = f"3′-terminal {'–'.join(terminal_pair)} mismatch ({group})"
    elif near[0] == 2:
        cq, basis = ASSAY_DCQ_FWD_POS2, "penultimate mismatch"
    else:
        cq, basis = ASSAY_DCQ_FWD_POS3_5, f"mismatch {near[0]} nt from the 3′ end"
    return {"delta_cq": cq, "mismatch_from_3p": mm, "basis": basis}


def fwd_axis(
    primer_region: str,
    other: str,
    tm_gap: Optional[Callable[[int], Optional[float]]] = None,
) -> dict:
    """ΔCq of the forward primer on `other`'s cDNA, best register over 5'-end shifts.

    primer_region = the forward primer's specific region (target 5' prefix).
    tm_gap(r) → Tm_on − Tm_off for register r (°C), or None to skip the stability
    term. ΔCq_FWD = max(table, ASSAY_DCQ_PER_TM_DEGREE × gap). Tm is computed lazily,
    only for registers that could still beat the best total.
    """
    tables = sorted(((_fwd_table(primer_region, other, r), r) for r in _shifts()),
                    key=lambda x: x[0]["delta_cq"])
    best = None
    for tab, r in tables:
        if best is not None and tab["delta_cq"] >= best["delta_cq"]:
            break
        gap = tm_gap(r) if tm_gap is not None else None
        # Capped at the largest measured delay ("no amplification"): the two-state
        # estimate is only meant for gaps of a few °C.
        tm_cq = (round(min(max(0.0, gap) * ASSAY_DCQ_PER_TM_DEGREE, ASSAY_DCQ_FWD_NO_TEMPLATE), 2)
                 if gap is not None else None)
        cq = round(max(tab["delta_cq"], tm_cq or 0.0), 2)
        if best is None or cq < best["delta_cq"]:
            best = {
                "delta_cq": cq,
                "table_delta_cq": tab["delta_cq"],
                "tm_delta_cq": tm_cq,
                "tm_gap_c": round(gap, 1) if gap is not None else None,
                "shift_5p": r,
                "mismatch_from_3p": tab["mismatch_from_3p"],
                "basis": tab["basis"] + (f"; duplex {gap:.1f} °C weaker than on target"
                                         if gap is not None and tm_cq and tm_cq > tab["delta_cq"]
                                         else ""),
            }
    return best


# ── assay ─────────────────────────────────────────────────────────

def assay_label(delta_cq: float) -> str:
    if delta_cq < ASSAY_DCQ_COAMPLIFIED_BELOW:
        return "CO-AMPLIFIED"
    if delta_cq < ASSAY_DCQ_DISCRIMINATED_AT:
        return "PARTIAL"
    return "DISCRIMINATED"


def cross_reactivity_pct(delta_cq: float) -> float:
    return round(100.0 * 2.0 ** (-delta_cq), 3)


def evaluate(
    target: str,
    other: str,
    overhang_len: int,
    fwd_len: int,
    tm_gap_for: Optional[Callable[[str, int], Optional[float]]] = None,
) -> dict:
    """Both axes for one off-target (DNA alphabet). tm_gap_for(other, r) supplies the
    FWD stability term. When the RT step alone already discriminates an unrelated
    miRNA, the forward axis is not evaluated (fwd = None): the total can only grow,
    and delta_cq is then a lower bound."""
    category = variant_category(target, other)
    rt = rt_axis(target, other, overhang_len)
    if category == "other" and rt["delta_cq"] >= ASSAY_DCQ_DISCRIMINATED_AT:
        return {
            "category": category, "rt": rt, "fwd": None,
            "delta_cq": rt["delta_cq"], "delta_cq_is_lower_bound": True,
            "cross_reactivity_pct": cross_reactivity_pct(rt["delta_cq"]),
            "assay_label": assay_label(rt["delta_cq"]),
        }
    fwd = fwd_axis(target[:fwd_len], other,
                   (lambda r: tm_gap_for(other, r)) if tm_gap_for is not None else None)
    total = round(rt["delta_cq"] + fwd["delta_cq"], 2)
    # Upper end of what the shift literature allows, so a label is never read as exact.
    hi = rt["shift_range"][1] if rt.get("shift_range") else None
    total_high = (round(total - rt.get("shift_delta_cq", 0.0) + hi, 2)
                  if hi is not None else None)
    return {
        "category": category,
        "delta_cq_high": total_high,
        "rt": rt,
        "fwd": fwd,
        "delta_cq": total,
        "delta_cq_is_lower_bound": False,
        "cross_reactivity_pct": cross_reactivity_pct(total),
        "assay_label": assay_label(total),
    }
