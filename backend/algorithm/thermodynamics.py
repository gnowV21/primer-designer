# ================================================================
# thermodynamics.py — Tm and ΔG calculations via primer3-py
# Method: SantaLucia 1998 nearest-neighbor thermodynamics [SL98]
# Salt correction: SantaLucia method (primer3-py default: salt_corrections_method='santalucia')
# NOTE: Owczarzy Mg2+ correction (2008, DOI 10.1021/bi702363u) is NOT used here.
#   Owczarzy 2004/2008 datasets are used as INDEPENDENT validation only
#   (calibration/tm_benchmark.json) — no circularity.
# NOTE: DNA:RNA hybrid Tm (RT primer + miRNA) uses DNA:DNA NN params here; actual
#   hybrid Tm may differ by 3-8 °C (Sugimoto 1995 DNA:RNA params not implemented).
# Consistent with Primer3Plus PRIMER_TM_FORMULA=1, PRIMER_SALT_CORRECTIONS=1
# ================================================================

import math
import primer3
from functools import lru_cache
from .constants import (
    P3_DEFAULT_MV_CONC, P3_DEFAULT_DV_CONC,
    P3_DEFAULT_DNTP_CONC, P3_DEFAULT_DNA_CONC,
    TRIS_PKA_25C, TRIS_CONC_DEFAULT_MM,
    P3_HETERODIMER_MAX_BP,
)
from .sequence_utils import reverse_complement


def effective_monovalent_mM(params: dict) -> float:
    """Effective monovalent-cation concentration (mM) for the Tm salt correction.

    Na+ and K+ are both monovalent and stabilize the duplex equivalently, so the
    correction uses their sum plus the protonated fraction of Tris (Tris+):

        [mono+] = [Na+] + [K+] + [Tris]·f_prot,  f_prot = 1/(1 + 10^(pH − pKa))

    Tris pKa is taken at 25 °C (measurement condition of buffer pH). The Tris term
    is small (~3–4 mM Tris+ for 10 mM Tris at pH 8.3); [Tris] defaults to the
    standard 1× PCR buffer (10 mM) and can be overridden via `trisConcentration`.
    """
    na = float(params.get("saltConcentration", P3_DEFAULT_MV_CONC))
    # Absent K+/Tris means "not specified" → contribute 0 (do NOT invent ions).
    # The design form always sends kPlusConc + bufferPH, so real designs use them;
    # API/validator callers that omit them keep the Na+-only baseline unchanged.
    k  = float(params.get("kPlusConc", 0.0) or 0.0)
    tris_total = float(params.get("trisConcentration", TRIS_CONC_DEFAULT_MM))
    ph = params.get("bufferPH")
    tris_plus = 0.0
    if tris_total > 0 and ph is not None:
        try:
            tris_plus = tris_total / (1.0 + 10.0 ** (float(ph) - TRIS_PKA_25C))
        except (ValueError, TypeError, OverflowError):
            tris_plus = 0.0
    return max(na + k + tris_plus, 0.0)


def _get_p3_params(params: dict) -> dict:
    """Extract primer3-py calculation parameters from user formData.

    mv_conc is the EFFECTIVE monovalent (Na+ + K+ + Tris+), not Na+ alone — so
    KCl and the Tris buffer contribute to the salt correction. Divalent (Mg2+)
    and dNTP are passed separately; primer3 converts Mg2+ via von Ahsen 2001.
    """
    return {
        "mv_conc":   effective_monovalent_mM(params),
        "dv_conc":   float(params.get("magnesiumConcentration",  P3_DEFAULT_DV_CONC)),
        "dntp_conc": float(params.get("dntpTotal",               P3_DEFAULT_DNTP_CONC)),
        "dna_conc":  float(params.get("primerConcentration",     P3_DEFAULT_DNA_CONC)),
    }


@lru_cache(maxsize=4096)
def _calc_tm_cached(sequence: str, mv_conc: float, dv_conc: float, dntp_conc: float, dna_conc: float) -> float:
    """Cached inner Tm call — primer3.calc_tm is deterministic for same (sequence, conditions)."""
    tm = primer3.calc_tm(
        seq=sequence,
        mv_conc=mv_conc,
        dv_conc=dv_conc,
        dntp_conc=dntp_conc,
        dna_conc=dna_conc,
    )
    return round(float(tm), 2)


# FUTURE: Sugimoto 1995 DNA:RNA nearest-neighbor table — pure Python, no new dependency.
# For RT primer overhang × miRNA duplex Tm: use algorithm/hybrid_tm.predict_hybrid_tm().
# Separated from _calc_tm_cached intentionally — different NN table (DNA:RNA vs DNA:DNA).
# Do NOT merge into _calc_tm_cached; the two engines must remain independent.


def calculate_tm_nn(sequence: str, params: dict) -> float:
    """
    Tm via nearest-neighbor (SantaLucia 1998) + Mg2+ salt correction.
    Mirrors Primer3Plus PRIMER_TM_FORMULA=1, PRIMER_SALT_CORRECTIONS=1. [P3P][SL98]
    """
    p3 = _get_p3_params(params)
    return _calc_tm_cached(sequence, p3["mv_conc"], p3["dv_conc"], p3["dntp_conc"], p3["dna_conc"])


def calculate_tm_binding_only(specific_region: str, params: dict) -> float:
    """
    Tm of the binding region only (specific 12-17 nt portion).
    Primer3Plus 2-step logic: Tm calculated only for template-binding 3' portion. [P3P]
    """
    return calculate_tm_nn(specific_region, params)


def _na_equivalent_mM(params: dict) -> float:
    """Effective [Na+]_eq (mM): monovalent (Na+K+Tris+) + von Ahsen 2001 Mg→Na term.
    Shares the monovalent model used by the NN engine, so salt handling stays unified."""
    mv = effective_monovalent_mM(params)
    dv = float(params.get("magnesiumConcentration", P3_DEFAULT_DV_CONC))
    dntp = float(params.get("dntpTotal", P3_DEFAULT_DNTP_CONC))
    if dv > dntp:
        mv += 120.0 * math.sqrt(dv - dntp)   # von Ahsen 2001 Mg2+ → Na+ equivalent
    return max(mv, 1.0)


def predicted_amplicon_tm(sequence: str, params: dict) -> float | None:
    """Product (amplicon) melting Tm in °C — long-duplex, salt-corrected formula:

        Tm = 81.5 + 0.41·%GC − 600/N + 16.6·log10[Na+]_eq   [Marmur62/Schildkraut65/Wallace79]

    This is the appropriate model for a long dsDNA product (concentration-independent),
    NOT the oligo nearest-neighbor engine used for primer Tm. Salt uses the same
    effective [Na+]_eq (Na+K+Tris+ + von Ahsen Mg) as the rest of the tool. [SPEC_phase5 §D]
    """
    seq = sequence.upper()
    n = len(seq)
    if n < 2:
        return None
    gc = 100.0 * sum(1 for b in seq if b in "GC") / n
    na = _na_equivalent_mM(params) / 1000.0   # mol/L
    tm = 81.5 + 0.41 * gc - 600.0 / n + 16.6 * math.log10(na)
    return round(tm, 1)


def amplicon_dh_cal(sequence: str, params: dict) -> float | None:
    """Formation ΔH (cal/mol, negative) of the amplicon as a perfect duplex, via the
    NN engine (primer3 calc_heterodimer with its reverse complement). Returns None when
    the sequence exceeds primer3's 60 bp thermodynamic-alignment limit — the caller then
    falls back to a per-bp approximation. Used only for melting-curve peak WIDTH. [SPEC §C.1.3]
    """
    seq = sequence.upper()
    if len(seq) > P3_HETERODIMER_MAX_BP:
        return None
    p3 = _get_p3_params(params)
    try:
        r = primer3.calc_heterodimer(
            seq1=seq, seq2=reverse_complement(seq),
            mv_conc=p3["mv_conc"], dv_conc=p3["dv_conc"],
            dntp_conc=p3["dntp_conc"], dna_conc=p3["dna_conc"],
        )
        return float(r.dh)
    except Exception:
        return None


def calc_dimer_tm(seq1: str, seq2: str | None, params: dict) -> float | None:
    """Tm (°C) of the most stable self- or hetero-dimer via primer3. Used to warn when a
    primer-dimer melt peak is close to the product peak in SYBR. [Lagatie17]"""
    p3 = _get_p3_params(params)
    try:
        if not seq2 or seq2 == seq1:
            r = primer3.calc_homodimer(seq=seq1, mv_conc=p3["mv_conc"], dv_conc=p3["dv_conc"],
                                       dntp_conc=p3["dntp_conc"], dna_conc=p3["dna_conc"])
        else:
            r = primer3.calc_heterodimer(seq1=seq1, seq2=seq2, mv_conc=p3["mv_conc"],
                                         dv_conc=p3["dv_conc"], dntp_conc=p3["dntp_conc"],
                                         dna_conc=p3["dna_conc"])
        return round(float(r.tm), 1)
    except Exception:
        return None


def calculate_end_stability(last_5_bases: str, params: dict) -> float:
    """
    Stability of the last 5 bases at 3' end (|ΔG| at 37°C).
    Mapping: Primer3Plus PRIMER_MAX_END_STABILITY = 9.0 kcal/mol. [P3P]
    Returns absolute value (positive kcal/mol).
    """
    p3 = _get_p3_params(params)
    try:
        result = primer3.calc_hairpin(
            seq=last_5_bases,
            mv_conc=p3["mv_conc"],
            dv_conc=p3["dv_conc"],
            dntp_conc=p3["dntp_conc"],
            dna_conc=p3["dna_conc"],
            temp_c=37.0,
        )
        return round(abs(float(result.dg) / 1000), 2)
    except Exception:
        return 0.0
