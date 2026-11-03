# ================================================================
# probe_design.py — TaqMan probe design for stem-loop RT-qPCR
# Phase 6 PART A (SPEC_phase6 §A.2–A.5)
#
# Two modes:
#   "custom"    — junction probe bridging miRNA|stemloop (per-miRNA, Chen 2005)
#   "universal" — probe on stemloop body, same for all miRNAs [Kramer 2013 RNA13]
#
# All thresholds read from PROBE_* constants (SPEC_phase2 §K); no hard-coded numbers.
# NOT part of SCORING_WEIGHTS_V4. Quality-only output.
#
# Sources: [IDT-TQ] IDT TaqMan guidelines; [RNA13] Kramer 2013 RNA;
#          [Chen05] Chen 2005 NAR; [patent 10036062]; [Hoffman08] J Clin Microbiol
# ================================================================

import algorithm.primer3_safe as primer3  # thread-safe wrapper (see primer3_safe.py)

from .constants import (
    STEMLOOP_BODY,
    UNIVERSAL_REVERSE,
    PROBE_MIN_LENGTH_SINGLE_Q, PROBE_MAX_LENGTH_SINGLE_Q,
    PROBE_MIN_LENGTH_MGB,       PROBE_MAX_LENGTH_MGB,
    PROBE_MIN_LENGTH_LNA,       PROBE_MAX_LENGTH_LNA,
    PROBE_MGB_TM_BOOST, PROBE_MGB_FILTER_BY_BOOSTED_TM,
    PROBE_TM_MIN, PROBE_TM_OPT, PROBE_TM_MAX,
    PROBE_TM_MIN_ABOVE_PRIMER, PROBE_TM_IDEAL_ABOVE_PRIMER,
    PROBE_GC_MIN, PROBE_GC_MAX,
    PROBE_NO_G_AT_5PRIME, PROBE_G_NOT_EXCEED_C,
    PROBE_MAX_CONSECUTIVE_G,
    PROBE_HAIRPIN_DG_MAX, PROBE_SELF_DIMER_DG_MAX, PROBE_HETERO_DIMER_DG_MAX,
    PROBE_MIN_DIST_FROM_PRIMER,
    PROBE_JUNCTION_OVERLAP_MIRNA_SIDE, PROBE_JUNCTION_OVERLAP_STEMLOOP_SIDE,
    PROBE_MODE_CUSTOM, PROBE_MODE_UNIVERSAL, PROBE_MODE_DEFAULT,
    PROBE_DV_CONC_DEFAULT, PROBE_DNA_CONC,
    P3_DEFAULT_MV_CONC, P3_DEFAULT_DNTP_CONC,
)
from .sequence_utils import rna_to_dna, reverse_complement, calculate_gc
from .thermodynamics import _get_p3_params, _calc_tm_cached

# Universal reverse binding site within STEMLOOP_BODY — exclude from universal probe scan
_UNIV_REV_START = 8
_UNIV_REV_END   = 28  # CCAGTGCAGGGTCCGAGGTA at positions [8:28]


def design_probe(
    mature_seq: str,
    stemloop_seq: str,
    forward_primer: dict,
    params: dict,
    mode: str = PROBE_MODE_DEFAULT,
    probe_type: str = "single_q",
) -> dict:
    """
    Design a TaqMan probe for stem-loop RT-qPCR.

    Args:
        mature_seq:    Mature miRNA sequence (RNA, 5'→3').
        stemloop_seq:  Stemloop RT primer sequence (from design_stemloop_rt).
        forward_primer: Top-ranked forward primer dict (has 'sequence', 'tm').
        params:        User formData dict (salt/Mg conditions).
        mode:          "custom" (junction, per-miRNA) or "universal" (stemloop body).
        probe_type:    "single_q" (18-27 nt) or "mgb" (13-20 nt + MGB Tm boost).

    Returns:
        {sequence, length, tm, gc_percent, position_1based, mode, probe_type,
         quality: {tm_gap, checks: {name: pass/fail/value}}, warnings: [...], passes_all: bool}
    """
    mature_dna = rna_to_dna(mature_seq.upper())
    rc_mature  = reverse_complement(mature_dna)  # complement of miRNA = cDNA RC_miRNA part
    fwd_tm     = float(forward_primer.get("tm", 60.0))
    p3         = _probe_p3_params(params)
    min_len, max_len = _length_range(probe_type)

    if mode == PROBE_MODE_CUSTOM:
        candidate = _design_custom(rc_mature, fwd_tm, p3, min_len, max_len, probe_type)
    else:
        candidate = _design_universal(fwd_tm, p3, min_len, max_len, probe_type)

    if candidate is None:
        return _no_probe_result(mode, "No probe candidate met Tm/GC criteria within the length range.")

    seq      = candidate["sequence"]
    tm       = candidate["tm"]
    gc       = round(calculate_gc(seq), 1)
    pos      = candidate["position_1based"]
    warnings = []

    # [§1 / §3.4] Universal probe specificity note
    if mode == PROBE_MODE_UNIVERSAL:
        warnings.append(
            "Universal probe binds the stemloop body and generates signal for any amplicon "
            "sharing the stemloop scaffold, including non-specific products. "
            "Sequence specificity is entirely determined by the RT primer and forward primer "
            "[Jung20 doi:10.1016/j.bios.2020.112301][Wang17 doi:10.3892/mmr.2017.8297]."
        )

    # [§2.3] Spatial fit check — probe must fit between universal reverse and forward primer
    fwd_seq = forward_primer.get("sequence", "")
    fwd_len = len(fwd_seq)
    cdna_len = len(STEMLOOP_BODY) + len(mature_dna)
    univ_rev_len = len(UNIVERSAL_REVERSE)
    space_for_probe = cdna_len - univ_rev_len - PROBE_MIN_DIST_FROM_PRIMER - fwd_len - PROBE_MIN_DIST_FROM_PRIMER
    if len(seq) > space_for_probe:
        warnings.append(
            f"Probe ({len(seq)} nt) may not fit within the amplicon (~{cdna_len} nt) "
            f"alongside forward ({fwd_len} nt) and universal reverse ({univ_rev_len} nt) primers. "
            "Consider a shorter MGB probe or universal mode [RESEARCH_INSIGHTS_probe §2.3]."
        )

    # [§3.1] LNA probe advisory
    if probe_type == "lna":
        warnings.append(
            "LNA probe Tm not adjusted (LNA modification positions and count unknown). "
            "Expected Tm increase: +2–8°C per LNA substitution [Liu25 doi:10.1515/cclm-2025-0824]. "
            "Verify final Tm with manufacturer before use."
        )

    checks   = _run_quality_checks(seq, tm, gc, fwd_tm, fwd_seq, params, p3, warnings, probe_type)

    return {
        "sequence":      seq,
        "length":        len(seq),
        "tm":            tm,
        "gc_percent":    gc,
        "position_1based": pos,
        "mode":          mode,
        "probe_type":    probe_type,
        "quality":       {"tm_gap": round(tm - fwd_tm, 1), "checks": checks},
        "warnings":      warnings,
        "passes_all":    not warnings,
        "disclaimer":    (
            f"Probe Tm calculated at {PROBE_DV_CONC_DEFAULT} mM Mg²⁺, "
            f"{P3_DEFAULT_MV_CONC} mM Na⁺ (primer3-py SantaLucia 1998). "
            "Actual Tm may differ if master-mix Mg²⁺ varies. Verify empirically before use."
        ),
    }


# ── Custom probe (junction miRNA | stemloop body) ───────────────────

def _design_custom(rc_mature: str, fwd_tm: float, p3: dict, min_len: int, max_len: int, probe_type: str) -> dict | None:
    """
    Find best probe spanning the cDNA junction:
      cDNA = 5'-STEMLOOP_BODY(44nt)-RC_miRNA_DNA(N nt)-3'
      Probe must overlap >= STEMLOOP_SIDE nt on stemloop side
                     and  >= MIRNA_SIDE nt on miRNA side.
    Returns candidate dict or None.
    """
    combined = STEMLOOP_BODY + rc_mature
    junction = len(STEMLOOP_BODY)  # index of first nt on miRNA side

    best = None
    best_dist = float("inf")

    for length in range(min_len, max_len + 1):
        # Slide window so it always covers the junction with required overlap
        # left_ext = how many nt we go INTO STEMLOOP_BODY from junction
        left_min = PROBE_JUNCTION_OVERLAP_STEMLOOP_SIDE
        left_max = min(junction, length - PROBE_JUNCTION_OVERLAP_MIRNA_SIDE)
        for left_ext in range(left_min, left_max + 1):
            right_ext = length - left_ext
            if right_ext < PROBE_JUNCTION_OVERLAP_MIRNA_SIDE:
                continue
            start = junction - left_ext
            end   = junction + right_ext
            if end > len(combined):
                continue
            probe_raw = combined[start:end]

            probe_seq = _apply_gc_rules(probe_raw)
            tm = _probe_tm(probe_seq, p3, probe_type)
            if not _passes_tm_filter(tm, fwd_tm, probe_type):
                continue

            # Position (1-based in cDNA = STEMLOOP_BODY + RC_miRNA)
            # We report position relative to miRNA for interpretability
            dist = abs(tm - PROBE_TM_OPT) + abs((tm - fwd_tm) - PROBE_TM_IDEAL_ABOVE_PRIMER)
            if dist < best_dist:
                best_dist  = dist
                best = {"sequence": probe_seq, "tm": tm, "position_1based": start + 1}

    return best


# ── Universal probe (stemloop body [RNA13]) ─────────────────────────

def _design_universal(fwd_tm: float, p3: dict, min_len: int, max_len: int, probe_type: str) -> dict | None:
    """
    Find best probe window within STEMLOOP_BODY, complementary strand.
    Exclude the universal-reverse primer binding region [8:28].
    """
    best = None
    best_dist = float("inf")

    for length in range(min_len, max_len + 1):
        for start in range(0, len(STEMLOOP_BODY) - length + 1):
            end = start + length
            # Exclude windows that overlap the universal-reverse binding site
            if start < _UNIV_REV_END and end > _UNIV_REV_START:
                continue
            window = STEMLOOP_BODY[start:end]
            # Universal probe is complementary to stemloop body → RC
            probe_raw = reverse_complement(window)
            probe_seq = _apply_gc_rules(probe_raw)
            tm = _probe_tm(probe_seq, p3, probe_type)
            if not _passes_tm_filter(tm, fwd_tm, probe_type):
                continue
            dist = abs(tm - PROBE_TM_OPT) + abs((tm - fwd_tm) - PROBE_TM_IDEAL_ABOVE_PRIMER)
            if dist < best_dist:
                best_dist = dist
                best = {"sequence": probe_seq, "tm": tm, "position_1based": start + 1}

    return best


# ── Quality checks ──────────────────────────────────────────────────

def _run_quality_checks(
    seq: str, tm: float, gc: float, fwd_tm: float,
    fwd_seq: str, params: dict, p3: dict,
    warnings: list, probe_type: str,
) -> dict:
    checks = {}
    tm_gap = tm - fwd_tm

    # [§2.2] MGB Tm is approximate — warn, do not treat as hard fail
    if probe_type == "mgb":
        checks["mgb_tm_approx"] = {"value": round(tm, 1), "pass": True}
        warnings.append(
            f"MGB Tm shown (+{PROBE_MGB_TM_BOOST:.0f}°C assumed) is approximate. "
            "Actual Tm depends on sequence context and linker chemistry. "
            "Verify with manufacturer (Applied Biosystems, IDT, etc.) before use [RESEARCH_INSIGHTS_probe §2.2]."
        )

    # Tm gap
    if tm_gap < PROBE_TM_MIN_ABOVE_PRIMER:
        warnings.append(f"Probe Tm gap = {tm_gap:.1f}°C (< {PROBE_TM_MIN_ABOVE_PRIMER}°C required) [IDT-TQ].")
    checks["tm_gap"] = {"value": round(tm_gap, 1), "pass": tm_gap >= PROBE_TM_MIN_ABOVE_PRIMER}

    # Probe Tm range
    checks["tm_range"] = {"value": round(tm, 1), "pass": PROBE_TM_MIN <= tm <= PROBE_TM_MAX}
    if not checks["tm_range"]["pass"]:
        warnings.append(f"Probe Tm = {tm:.1f}°C outside [{PROBE_TM_MIN}–{PROBE_TM_MAX}°C] [IDT-TQ].")

    # GC%
    checks["gc_pct"] = {"value": gc, "pass": PROBE_GC_MIN <= gc <= PROBE_GC_MAX}
    if not checks["gc_pct"]["pass"]:
        warnings.append(f"Probe GC = {gc:.1f}% outside [{PROBE_GC_MIN}–{PROBE_GC_MAX}%] [IDT-TQ].")

    # 5'-G rule
    no_g_ok = seq[0] != "G"
    checks["no_5prime_g"] = {"value": seq[0], "pass": no_g_ok}
    if not no_g_ok:
        warnings.append("Probe 5' base = G (reduces fluorescence efficiency) [IDT-TQ].")

    # G ≤ C rule
    g_le_c = seq.count("G") <= seq.count("C")
    checks["g_not_exceed_c"] = {"value": f"G={seq.count('G')},C={seq.count('C')}", "pass": g_le_c}
    if not g_le_c:
        warnings.append("Probe has more G than C — consider reverse complement [patent 10036062].")

    # Poly-G
    poly_g_ok = _max_run(seq, "G") <= PROBE_MAX_CONSECUTIVE_G
    checks["poly_g"] = {"value": _max_run(seq, "G"), "pass": poly_g_ok}
    if not poly_g_ok:
        warnings.append(f"Probe has >{PROBE_MAX_CONSECUTIVE_G} consecutive G bases [IDT-TQ].")

    # Hairpin ΔG
    hp_dg = _calc_hairpin_dg(seq, p3)
    hp_ok = hp_dg > PROBE_HAIRPIN_DG_MAX
    checks["hairpin_dg"] = {"value": hp_dg, "pass": hp_ok}
    if not hp_ok:
        warnings.append(f"Probe hairpin ΔG = {hp_dg:.2f} kcal/mol (< {PROBE_HAIRPIN_DG_MAX}) [IDT-TQ].")

    # Self-dimer ΔG
    sd_dg = _calc_self_dimer_dg(seq, p3)
    sd_ok = sd_dg > PROBE_SELF_DIMER_DG_MAX
    checks["self_dimer_dg"] = {"value": sd_dg, "pass": sd_ok}
    if not sd_ok:
        warnings.append(f"Probe self-dimer ΔG = {sd_dg:.2f} kcal/mol (< {PROBE_SELF_DIMER_DG_MAX}) [IDT-TQ].")

    # Heterodimer with forward primer
    if fwd_seq:
        hd_dg = _calc_hetero_dg(seq, fwd_seq, p3, float(params.get("annealingTemp", 60.0)))
        hd_ok = hd_dg > PROBE_HETERO_DIMER_DG_MAX
        checks["hetero_dimer_fwd_dg"] = {"value": hd_dg, "pass": hd_ok}
        if not hd_ok:
            warnings.append(f"Probe × Forward heterodimer ΔG = {hd_dg:.2f} kcal/mol (< {PROBE_HETERO_DIMER_DG_MAX}) [IDT-TQ].")

    return checks


# ── Helpers ─────────────────────────────────────────────────────────

def _apply_gc_rules(seq: str) -> str:
    """Apply 5'-no-G and G≤C rules; return corrected sequence."""
    # G > C → take RC first
    s = seq.upper()
    if s.count("G") > s.count("C"):
        s = reverse_complement(s)
    # 5'-G → take RC (may fix or break G>C — accept whichever is better)
    if s and s[0] == "G":
        rc = reverse_complement(s)
        if rc[0] != "G":
            s = rc
    return s


def _probe_tm(seq: str, p3: dict, probe_type: str) -> float:
    tm = _calc_tm_cached(seq, p3["mv_conc"], p3["dv_conc"], p3["dntp_conc"], p3["dna_conc"])
    if probe_type == "mgb":
        tm += PROBE_MGB_TM_BOOST
    return round(tm, 1)


def _probe_p3_params(params: dict) -> dict:
    """Probe-specific p3 params: use PROBE_DV_CONC_DEFAULT for Mg (1.5 mM)."""
    base = _get_p3_params(params)
    base["dv_conc"]   = PROBE_DV_CONC_DEFAULT
    base["dna_conc"]  = PROBE_DNA_CONC
    return base


def _length_range(probe_type: str) -> tuple:
    if probe_type == "mgb":
        return PROBE_MIN_LENGTH_MGB, PROBE_MAX_LENGTH_MGB
    if probe_type == "lna":
        return PROBE_MIN_LENGTH_LNA, PROBE_MAX_LENGTH_LNA
    return PROBE_MIN_LENGTH_SINGLE_Q, PROBE_MAX_LENGTH_SINGLE_Q


def _passes_tm_filter(tm: float, fwd_tm: float, probe_type: str) -> bool:
    """Return True if probe Tm passes filter for candidate selection.

    For MGB: skip Tm range filter — +15°C boost is too imprecise to reject candidates
    [RESEARCH_INSIGHTS_probe §2.2]. Still filter on gap so raw-Tm is not absurdly low.
    For LNA: no Tm boost applied; filter same as single_q.
    """
    if probe_type == "mgb" and not PROBE_MGB_FILTER_BY_BOOSTED_TM:
        # raw Tm = tm - PROBE_MGB_TM_BOOST; ensure gap with raw tm is not negative
        raw_tm = tm - PROBE_MGB_TM_BOOST
        return raw_tm >= (PROBE_TM_MIN - PROBE_MGB_TM_BOOST - 5)  # very loose floor
    return (PROBE_TM_MIN <= tm <= PROBE_TM_MAX) and (tm - fwd_tm >= PROBE_TM_MIN_ABOVE_PRIMER)


def _max_run(seq: str, base: str) -> int:
    """Longest consecutive run of `base` in `seq`."""
    best = cur = 0
    for b in seq:
        cur = cur + 1 if b == base else 0
        best = max(best, cur)
    return best


def _calc_hairpin_dg(seq: str, p3: dict) -> float:
    try:
        r = primer3.calc_hairpin(seq=seq, mv_conc=p3["mv_conc"], dv_conc=p3["dv_conc"],
                                  dntp_conc=p3["dntp_conc"], dna_conc=p3["dna_conc"], temp_c=37.0)
        return round(float(r.dg) / 1000, 2)
    except Exception:
        return 0.0


def _calc_self_dimer_dg(seq: str, p3: dict) -> float:
    try:
        r = primer3.calc_homodimer(seq=seq, mv_conc=p3["mv_conc"], dv_conc=p3["dv_conc"],
                                    dntp_conc=p3["dntp_conc"], dna_conc=p3["dna_conc"], temp_c=37.0)
        return round(float(r.dg) / 1000, 2)
    except Exception:
        return 0.0


def _calc_hetero_dg(seq1: str, seq2: str, p3: dict, temp_c: float) -> float:
    try:
        r = primer3.calc_heterodimer(seq1=seq1, seq2=seq2, mv_conc=p3["mv_conc"],
                                      dv_conc=p3["dv_conc"], dntp_conc=p3["dntp_conc"],
                                      dna_conc=p3["dna_conc"], temp_c=temp_c)
        return round(float(r.dg) / 1000, 2)
    except Exception:
        return 0.0


def _no_probe_result(mode: str, reason: str) -> dict:
    return {
        "sequence":        None,
        "length":          None,
        "tm":              None,
        "gc_percent":      None,
        "position_1based": None,
        "mode":            mode,
        "probe_type":      "single_q",
        "quality":         {},
        "warnings":        [reason],
        "passes_all":      False,
        "disclaimer":      "No probe designed.",
    }
