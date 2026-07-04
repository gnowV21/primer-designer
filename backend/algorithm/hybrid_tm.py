# ================================================================
# hybrid_tm.py — DNA:RNA hybrid Tm via Sugimoto 1995 nearest-neighbor
# Reference: Sugimoto N et al. (1995) Biochemistry 34(37):11211-11216
# Informational only — NOT used in scoring or hard-filter logic.
# Feature flag: USE_HYBRID_TM (constants.py)
# ================================================================

import math

R_CAL = 1.987  # cal/(mol·K), universal gas constant

# ----------------------------------------------------------------
# Nearest-neighbor parameters for DNA:RNA hybrid duplexes [Sugimoto95]
# Convention: key = DNA dinucleotide 5'→3'; paired RNA strand is 3'→5'
#   DNA: 5'-XY-3'   RNA: 3'-X'Y'-5'
#   (X' = RNA complement of X: A↔U, T↔A, G↔C, C↔G)
# Source: Sugimoto et al. 1995, Biochemistry 34(37):11211-11216, Table 2
# ΔH in kcal/mol, ΔS in cal/(mol·K)
# ----------------------------------------------------------------
_NN: dict[str, tuple[float, float]] = {
    "AA": (-7.8,  -21.9),  # AA/UU  [Sugimoto95]
    "AT": (-7.8,  -23.2),  # AT/UA  [Sugimoto95]
    "TA": (-6.3,  -17.1),  # TA/AU  [Sugimoto95]
    "CA": (-9.1,  -23.5),  # CA/GU  [Sugimoto95]
    "GT": (-8.4,  -22.4),  # GT/CA  [Sugimoto95]
    "CT": (-7.8,  -21.6),  # CT/GA  [Sugimoto95]
    "GA": (-5.5,  -13.5),  # GA/CU  [Sugimoto95]
    "CG": (-16.3, -47.1),  # CG/GC  [Sugimoto95]
    "GC": (-11.1, -28.4),  # GC/CG  [Sugimoto95]
    "GG": (-7.0,  -19.3),  # GG/CC  [Sugimoto95]
    "AC": (-5.9,  -16.3),  # AC/UG  [Sugimoto95]
    "TG": (-8.3,  -21.9),  # TG/AC  [Sugimoto95]
    "AG": (-9.4,  -25.5),  # AG/UC  [Sugimoto95]
    "CC": (-9.3,  -23.2),  # CC/GG  [Sugimoto95]
    "TC": (-5.8,  -15.5),  # TC/AG  [Sugimoto95]
    "TT": (-6.6,  -18.4),  # TT/AA  [Sugimoto95]
}

# Initiation parameters [Sugimoto95] Table 2
# Applied once for the 5'-terminal DNA base.
# AT initiation (5' = A or T): [Sugimoto95]
_INIT_AT = (2.3, 4.1)   # (ΔH kcal/mol, ΔS cal/mol·K)
# GC initiation (5' = G or C): [Sugimoto95]
_INIT_GC = (0.1, -2.8)  # (ΔH kcal/mol, ΔS cal/mol·K)

# Short-duplex caveat (4–8 bp): NN extrapolation error grows at <8 bp.
# Salt correction is designed for longer oligos; RNA:DNA specific correction not validated.
_CAVEAT_SHORT_DUPLEX = "short-duplex NN extrapolation (4–8 bp): uncertainty ±3–5°C [Sugimoto95 range]"
_CAVEAT_SALT         = "salt correction for DNA:RNA is approximate (SantaLucia 1998 monovalent formula) [SL98]"


def predict_hybrid_tm(
    dna_5to3: str,
    dna_conc_nM: float = 4000.0,
    mv_conc_mM: float = 50.0,
) -> dict:
    """
    Predict Tm of a DNA:RNA hybrid duplex using Sugimoto 1995 nearest-neighbor parameters.

    Convention:
      dna_5to3 — DNA strand written 5'→3' (the RT primer overhang: overhang_rc)
      RNA complement is implicit (antiparallel: A↔U, T↔A, G↔C, C↔G in RNA)

    Parameters:
      dna_5to3    — DNA sequence, bases A/T/G/C, 5'→3' (4–8 nt typical for RT primer overhang)
      dna_conc_nM — total strand concentration (nM); default 4000 = 4 μM (Sugimoto 1995 measurement conditions)
      mv_conc_mM  — monovalent cation concentration (mM Na+ equivalent); default 50 mM

    Returns dict:
      tm_c     — Tm in °C (float, or None if sequence contains unsupported bases)
      dH       — total ΔH in kcal/mol [Sugimoto95]
      dS       — total ΔS in cal/(mol·K) after salt correction [SL98]
      method   — citation string
      caveats  — list of caveat strings
      accuracy — accuracy descriptor

    Tm formula [Sugimoto95][SL98]:
      Tm = ΔH° / (ΔS°_corrected + R·ln(Ct/4)) − 273.15
      where Ct = dna_conc_nM × 1e-9 mol/L; x=4 (non-self-complementary duplex)

    Salt correction [SL98] eq. 10:
      ΔS°_corrected = ΔS°_base + 0.368 × (N−1) × ln([Na+] / 1.0)
      where N = duplex length (bp), [Na+] in mol/L
    """
    seq = dna_5to3.upper().strip()
    n   = len(seq)

    if n < 2:
        return _failure("Sequence too short for NN calculation (need ≥ 2 nt)")

    # Validate bases
    invalid = set(seq) - {"A", "T", "G", "C"}
    if invalid:
        return _failure(f"Unsupported bases in sequence: {invalid}")

    # Sum nearest-neighbor ΔH and ΔS
    dH_sum = 0.0
    dS_sum = 0.0
    for i in range(n - 1):
        dinuc = seq[i:i+2]
        if dinuc not in _NN:
            return _failure(f"Unknown dinucleotide: {dinuc}")
        h, s = _NN[dinuc]
        dH_sum += h
        dS_sum += s

    # Initiation correction for 5'-terminal DNA base [Sugimoto95]
    init_h, init_s = _INIT_GC if seq[0] in ("G", "C") else _INIT_AT
    dH_total = dH_sum + init_h   # kcal/mol
    dS_total = dS_sum + init_s   # cal/(mol·K)

    # Salt correction [SL98]: applies to ΔS
    # 0.368 × (N−1) × ln([Na+]/1.0), [Na+] in mol/L
    mv_mol_L = mv_conc_mM / 1000.0
    dS_salt  = 0.368 * (n - 1) * math.log(mv_mol_L)
    dS_eff   = dS_total + dS_salt   # cal/(mol·K)

    # Tm calculation
    dH_cal = dH_total * 1000.0   # convert kcal → cal
    Ct     = dna_conc_nM * 1e-9  # mol/L
    denom  = dS_eff + R_CAL * math.log(Ct / 4.0)

    if abs(denom) < 1e-12:
        return _failure("Denominator near zero — Tm undefined at these conditions")

    tm_c = dH_cal / denom - 273.15

    caveats = [_CAVEAT_SHORT_DUPLEX, _CAVEAT_SALT]
    if n < 6:
        caveats.insert(0, f"Duplex length {n} bp is very short; NN errors are largest <6 bp")

    return {
        "tm_c":     round(tm_c, 1),
        "dH":       round(dH_total, 2),
        "dS":       round(dS_eff, 2),
        "method":   "Sugimoto 1995 DNA:RNA nearest-neighbor (Biochemistry 34:11211)",
        "chemistry": "DNA:RNA",
        "accuracy": "modeled (Sugimoto 1995), short-duplex — indicative",
        "caveats":  caveats,
    }


def _failure(reason: str) -> dict:
    return {
        "tm_c":     None,
        "dH":       None,
        "dS":       None,
        "method":   "Sugimoto 1995 DNA:RNA NN (failed)",
        "chemistry": "DNA:RNA",
        "accuracy": "not computed",
        "caveats":  [reason],
    }
