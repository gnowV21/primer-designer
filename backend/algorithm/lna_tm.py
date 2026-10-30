# ================================================================
# lna_tm.py — Doublet-based unified NN Tm calculator for LNA-substituted
#             DNA primers (DNA·LNA:DNA context only).
#
# References:
#   [SL98]      SantaLucia 1998 — PNAS 95:1460-1465 (DNA:DNA NN params)
#   [McTigue04] McTigue et al. 2004 — Biochemistry 43(18):5388-5405 (single-LNA doublets)
#   [Owczarzy11] Owczarzy et al. 2011 — Biochemistry 50(43):9352-9367 (LNA:LNA doublets)
#   [vA01]      von Ahsen et al. 2001 — Clin Chem 47:1956-1961 (Mg²⁺→Na⁺ conversion)
#
# Scope: DNA primers with LNA substitutions annealing to a DNA template.
#        DNA:RNA context (e.g. RT primer overhang binding to miRNA) is OUT OF SCOPE
#        for this module — use hybrid_tm.py for that context.
#
# LNA Tm is INFORMATIONAL ONLY — NOT used in scoring or hard-filter logic.
# Feature flag: USE_LNA_SUGGESTIONS (constants.py)
#
# Core principle (v1.1):
#   - n bases → (n-1) doublets
#   - One LNA at position i affects doublets (i-1, i) and (i, i+1)
#   - Doublet source:  both DNA → SL98
#                      exactly 1 LNA → McTigue04
#                      both LNA → Owczarzy11
#   - delta_tm = tm_lna - tm_dna  (same engine → pure LNA effect)
# ================================================================

import math
import itertools

R_CAL = 1.987  # cal/(mol·K) — universal gas constant

# ----------------------------------------------------------------
# SECTION 1: SantaLucia 1998 DNA:DNA nearest-neighbor parameters
# Source: SantaLucia 1998, PNAS 95:1460-1465, Table 2
# Convention: key = DNA dinucleotide 5'→3' (both UPPERCASE)
# ΔH in kcal/mol, ΔS in cal/(mol·K)
# ----------------------------------------------------------------
_SL98: dict[str, tuple[float, float]] = {
    # --- Unique pairs (+ complementary by symmetry) ---
    "AA": (-7.9,  -22.2),   # AA/TT  [SL98]
    "TT": (-7.9,  -22.2),   # TT/AA  = AA by symmetry [SL98]
    "AT": (-7.2,  -20.4),   # AT/TA  [SL98]
    "TA": (-7.2,  -21.3),   # TA/AT  [SL98]
    "CA": (-8.5,  -22.7),   # CA/GT  [SL98]
    "TG": (-8.5,  -22.7),   # TG/AC  = CA by symmetry [SL98]
    "GT": (-8.4,  -22.4),   # GT/CA  [SL98]
    "AC": (-8.4,  -22.4),   # AC/TG  = GT by symmetry [SL98]
    "CT": (-7.8,  -21.0),   # CT/GA  [SL98]
    "AG": (-7.8,  -21.0),   # AG/TC  = CT by symmetry [SL98]
    "GA": (-8.2,  -22.2),   # GA/CT  [SL98]
    "TC": (-8.2,  -22.2),   # TC/AG  = GA by symmetry [SL98]
    "CG": (-10.6, -27.2),   # CG/GC  [SL98]
    "GC": (-9.8,  -24.4),   # GC/CG  [SL98]
    "GG": (-8.0,  -19.9),   # GG/CC  [SL98]
    "CC": (-8.0,  -19.9),   # CC/GG  = GG by symmetry [SL98]
}

# Initiation parameters [SL98] Table 2
# Applied for the 5'-terminal base of the primer strand.
_SL98_INIT_GC = (0.1,  -2.8)   # (ΔH kcal/mol, ΔS cal/mol·K) — terminal G or C [SL98]
_SL98_INIT_AT = (2.3,   4.1)   # (ΔH kcal/mol, ΔS cal/mol·K) — terminal A or T [SL98]

# ----------------------------------------------------------------
# SECTION 2: Single-LNA doublet parameters (FULL NN, in 1 M Na+)
# Source: Owczarzy et al. 2011, Biochemistry 50(43):9352-9367, Table 2,
#         "Isolated LNA Modifications" block — the full ΔH°/ΔS° values that
#         Owczarzy computed from McTigue et al. 2004's 32NN differential set
#         (McTigue 2004, Biochemistry 43(18):5388-5405). Using the published
#         full parameters directly avoids any SL98-baseline mismatch.
# Convention: lowercase = DNA base; UPPERCASE = LNA base; key is 5'→3'.
#   'xY' = DNA x then LNA Y  ↔ Owczarzy "X+Y/..." (2nd base LNA)
#   'Xy' = LNA X then DNA y  ↔ Owczarzy "+XY/..." (1st base LNA)
# ΔH in kcal/mol, ΔS in cal/(mol·K).
# ----------------------------------------------------------------
_MCTIGUE04: dict[str, tuple[float, float]] = {
    # --- xY doublets: DNA-then-LNA (Owczarzy Table 2, "A+A/TT" … "T+T/AA") ---
    'aA': (-6.908,  -18.135),   # A+A/TT
    'aC': (-5.510,  -11.824),   # A+C/TG
    'aG': (-9.000,  -22.826),   # A+G/TC
    'aT': (-5.384,  -13.537),   # A+T/TA
    'cA': (-7.142,  -18.333),   # C+A/GT
    'cC': (-5.937,  -12.335),   # C+C/GG
    'cG': (-10.876, -27.918),   # C+G/GC
    'cT': (-9.471,  -25.070),   # C+T/GA
    'gA': (-7.756,  -19.302),   # G+A/CT
    'gC': (-10.725, -25.511),   # G+C/CG
    'gG': (-8.943,  -20.833),   # G+G/CC
    'gT': (-9.035,  -22.742),   # G+T/CA
    'tA': (-5.609,  -16.019),   # T+A/AT
    'tC': (-7.591,  -19.031),   # T+C/AG
    'tG': (-6.335,  -15.537),   # T+G/AC
    'tT': (-5.574,  -14.149),   # T+T/AA
    # --- Xy doublets: LNA-then-DNA (Owczarzy Table 2, "+AA/TT" … "+TT/AA") ---
    'Aa': (-7.193,  -19.723),   # +AA/TT
    'Ac': (-7.269,  -18.336),   # +AC/TG
    'Ag': (-7.536,  -18.387),   # +AG/TC
    'At': (-4.918,  -12.943),   # +AT/TA
    'Ca': (-7.451,  -18.380),   # +CA/GT
    'Cc': (-5.904,  -11.904),   # +CC/GG
    'Cg': (-9.815,  -23.491),   # +CG/GC
    'Ct': (-7.092,  -16.825),   # +CT/GA
    'Ga': (-5.038,  -11.656),   # +GA/CT
    'Gc': (-10.160, -24.651),   # +GC/CG
    'Gg': (-10.844, -26.580),   # +GG/CC
    'Gt': (-8.612,  -22.327),   # +GT/CA
    'Ta': (-7.246,  -19.738),   # +TA/AT
    'Tc': (-6.307,  -15.515),   # +TC/AG
    'Tg': (-10.040, -25.744),   # +TG/AC
    'Tt': (-6.372,  -16.902),   # +TT/AA
}

# ----------------------------------------------------------------
# SECTION 3: Consecutive LNA:LNA doublet parameters (FULL NN, in 1 M Na+)
# Source: Owczarzy et al. 2011, Biochemistry 50(43):9352-9367, Table 2,
#         "Consecutive LNA Modifications" block.
# Convention: both bases UPPERCASE (both LNA); key is 5'→3'.
#   'XY' ↔ Owczarzy "+X+Y/..."   ΔH kcal/mol, ΔS cal/(mol·K).
# ----------------------------------------------------------------
_OWCZARZY11: dict[str, tuple[float, float]] = {
    'AA': (-9.991,  -27.175),   # +A+A/TT
    'AC': (-11.389, -28.963),   # +A+C/TG
    'AG': (-12.793, -31.607),   # +A+G/TC
    'AT': (-14.703, -40.750),   # +A+T/TA
    'CA': (-14.177, -35.498),   # +C+A/GT
    'CC': (-15.399, -36.375),   # +C+C/GG
    'CG': (-14.558, -35.239),   # +C+G/GC
    'CT': (-15.737, -41.218),   # +C+T/GA
    'GA': (-13.959, -35.097),   # +G+A/CT
    'GC': (-16.109, -40.738),   # +G+C/CG
    'GG': (-13.022, -29.673),   # +G+G/CC
    'GT': (-17.361, -45.858),   # +G+T/CA
    'TA': (-10.318, -26.108),   # +T+A/AT
    'TC': (-9.166,  -21.535),   # +T+C/AG
    'TG': (-10.046, -22.591),   # +T+G/AC
    'TT': (-10.419, -27.683),   # +T+T/AA
}

# ----------------------------------------------------------------
# Caveat strings
# ----------------------------------------------------------------
_CAVEAT_LNA_GENERAL = (
    "LNA Tm predicted by doublet NN model (SantaLucia 1998 + McTigue 2004 + "
    "Owczarzy 2011, LNA·DNA:DNA). Salt correction approximate for LNA away "
    "from ~100 mM Na⁺. Informational — verify with synthesis provider. "
    "RT overhang is out of scope (DNA:RNA context)."
)
_CAVEAT_BENCHMARKED_SINGLE_LNA = (
    "LNA NN parameters: Owczarzy 2011 Table 2 (single-LNA set derived from "
    "McTigue 2004 32NN). Benchmarked against McTigue 2004 Table 1 measured Tm "
    "(ΔTm RMSD 0.78 °C, absolute Tm RMSD 1.54 °C; 1 M Na⁺). Predictions away "
    "from ~1 M Na⁺ rely on the SantaLucia 1998 salt model — verify with your "
    "synthesis provider for final designs."
)
_CAVEAT_CONSECUTIVE_LNA_UNBENCHMARKED = (
    "This design contains CONSECUTIVE LNA positions. The adjacent-LNA (LNA:LNA) "
    "nearest-neighbour parameters come from Owczarzy 2011 and are NOT covered by "
    "our benchmark, which contains single-LNA oligos only. Treat the predicted Tm "
    "for these designs as an unvalidated estimate."
)


# ----------------------------------------------------------------
# SECTION 4: Core doublet classification and lookup
# ----------------------------------------------------------------

def _classify_doublet(seq: str, lna_set: set, j: int) -> str:
    """
    Classify doublet at position j based on LNA membership.

    Returns 'dna_dna', 'one_lna', or 'lna_lna'.
    j and j+1 must both be valid indices in seq.
    """
    j_lna  = j     in lna_set
    j1_lna = (j + 1) in lna_set
    if j_lna and j1_lna:
        return "lna_lna"
    elif j_lna or j1_lna:
        return "one_lna"
    else:
        return "dna_dna"


def _lookup_doublet(seq: str, lna_set: set, j: int) -> tuple[float, float, str]:
    """
    Look up (dH, dS, source_name) for doublet starting at position j.

    Key construction rules:
      dna_dna  → uppercase both (SL98)
      one_lna  → lowercase=DNA, UPPERCASE=LNA (McTigue04)
      lna_lna  → UPPERCASE both (Owczarzy11)

    Raises KeyError if the doublet key is not found in the selected table.
    """
    kind = _classify_doublet(seq, lna_set, j)
    b0 = seq[j]
    b1 = seq[j + 1]

    if kind == "dna_dna":
        key = b0.upper() + b1.upper()
        dh, ds = _SL98[key]
        return dh, ds, "santalucia98"

    elif kind == "one_lna":
        k0 = b0.upper() if j     in lna_set else b0.lower()
        k1 = b1.upper() if (j + 1) in lna_set else b1.lower()
        key = k0 + k1
        dh, ds = _MCTIGUE04[key]
        return dh, ds, "mctigue04"

    else:  # lna_lna
        key = b0.upper() + b1.upper()
        dh, ds = _OWCZARZY11[key]
        return dh, ds, "owczarzy11"


# ----------------------------------------------------------------
# SECTION 5: Salt concentration helpers
# ----------------------------------------------------------------

def _effective_mv_mol_L(params: dict) -> float:
    """
    Compute effective monovalent Na+ concentration in mol/L.

    If Mg²⁺ is present and exceeds chelated dNTP, apply simplified
    von Ahsen 2001 [vA01] conversion:
        mv_eff_mM = mv_mM + 3.3 * sqrt(max(0, dv_mM - dntp_mM))

    This approximation is calibrated for ~100 mM Na+. Below ~20 mM
    or above ~200 mM the error increases. [SL98][vA01]
    """
    mv_mM   = float(params.get("saltConcentration",      50.0))
    dv_mM   = float(params.get("magnesiumConcentration",  1.5))
    dntp_mM = float(params.get("dntpTotal",               0.8))

    free_mg_mM = max(0.0, dv_mM - dntp_mM)
    if free_mg_mM > 0.0:
        mv_eff_mM = mv_mM + 3.3 * math.sqrt(free_mg_mM)
    else:
        mv_eff_mM = mv_mM

    # Guard against zero or negative concentration (avoid log(<=0))
    return max(mv_eff_mM, 1.0) / 1000.0   # mol/L


# ----------------------------------------------------------------
# SECTION 6: Shared NN Tm engine
# ----------------------------------------------------------------

def _nn_tm(sequence: str, lna_positions: list, params: dict) -> dict:
    """
    Core nearest-neighbor Tm engine.

    Shared for baseline DNA (lna_positions=[]) and LNA-substituted cases.

    Parameters
    ----------
    sequence      : DNA 5'→3' (A/T/G/C only, uppercase assumed after validation)
    lna_positions : 0-based indices of LNA-substituted bases (may be empty)
    params        : user params dict (saltConcentration, magnesiumConcentration,
                    dntpTotal, primerConcentration)

    Algorithm
    ---------
    1. Sum (n-1) doublet ΔH/ΔS using _lookup_doublet (dispatches to SL98/McTigue04/Owczarzy11)
    2. Add 5'-terminal initiation (SL98 GC or AT; LNA terminal → use DNA base identity)
    3. Salt correction [SL98 eq. 10 + vA01]:
           ΔS_eff = ΔS_total + 0.368 × (n−1) × ln([Na+]_eff)
    4. Tm = ΔH_total × 1000 / (ΔS_eff + R × ln(C_T / 4)) − 273.15
       C_T = primerConcentration (nM) × 1e-9; x=4 (non-self-complementary) [SL98]

    Returns
    -------
    dict with: tm, dh_total, ds_total, ds_eff, param_sources (list), per_doublet (list)
    Raises ValueError on bad input; KeyError propagates from unknown doublet keys.
    """
    seq = sequence.upper()
    n   = len(seq)
    lna_set = set(lna_positions)

    # 1. Sum doublet contributions
    dh_sum = 0.0
    ds_sum = 0.0
    param_sources: list[str] = []
    per_doublet: list[dict]  = []

    for j in range(n - 1):
        dh, ds, src = _lookup_doublet(seq, lna_set, j)
        dh_sum += dh
        ds_sum += ds
        if src not in param_sources:
            param_sources.append(src)
        per_doublet.append({
            "j": j,
            "doublet": f"{seq[j]}{seq[j+1]}",
            "lna_j":   j     in lna_set,
            "lna_j1":  (j + 1) in lna_set,
            "dH":      dh,
            "dS":      ds,
            "source":  src,
        })

    # 2. Initiation: SantaLucia 1998 applies a terminal-initiation correction to
    #    BOTH duplex ends (one per terminal base pair), not just the 5' end.
    #    Terminal LNAs are assumed to use DNA initiation parameters [Owczarzy11].
    init_h = 0.0
    init_s = 0.0
    for terminal_base in (seq[0], seq[-1]):
        if terminal_base in ("G", "C"):
            init_h += _SL98_INIT_GC[0]
            init_s += _SL98_INIT_GC[1]
        else:
            init_h += _SL98_INIT_AT[0]
            init_s += _SL98_INIT_AT[1]
    if "santalucia98" not in param_sources:
        param_sources.insert(0, "santalucia98")  # initiation always uses SL98

    dh_total = dh_sum + init_h   # kcal/mol
    ds_total = ds_sum + init_s   # cal/(mol·K)

    # 3. Salt correction [SL98]
    mv_mol_L = _effective_mv_mol_L(params)
    ds_salt  = 0.368 * (n - 1) * math.log(mv_mol_L)
    ds_eff   = ds_total + ds_salt

    # 4. Tm calculation [SL98]
    ct_nM  = float(params.get("primerConcentration", 200.0))
    ct_mol = ct_nM * 1e-9           # mol/L
    dh_cal = dh_total * 1000.0      # kcal → cal

    denom = ds_eff + R_CAL * math.log(ct_mol / 4.0)
    if abs(denom) < 1e-12:
        raise ValueError("Denominator near zero — Tm undefined at these conditions")

    tm_c = dh_cal / denom - 273.15

    return {
        "tm":           round(tm_c, 1),
        "dh_total":     round(dh_total, 3),
        "ds_total":     round(ds_total, 3),
        "ds_eff":       round(ds_eff, 3),
        "param_sources": param_sources,
        "per_doublet":  per_doublet,
    }


# ----------------------------------------------------------------
# SECTION 7: Public API — calc_lna_tm
# ----------------------------------------------------------------

def calc_lna_tm(sequence: str, lna_positions: list, params: dict) -> dict:
    """
    Calculate Tm for a DNA primer with LNA substitutions at given positions.

    Compares baseline (all DNA) vs LNA-substituted using the same _nn_tm engine
    so that delta_tm reflects purely the LNA contribution.

    Parameters
    ----------
    sequence      : DNA 5'→3', bases A/T/G/C (case-insensitive)
    lna_positions : 0-based indices of LNA-substituted bases (empty → pure DNA)
    params        : dict with keys: saltConcentration (mM Na+),
                    magnesiumConcentration (mM Mg²+), dntpTotal (mM),
                    primerConcentration (nM)

    Returns
    -------
    {
      tm_dna        : float,   # baseline Tm (no LNA), same NN engine
      tm_lna        : float,   # Tm with LNA substitutions
      delta_tm      : float,   # tm_lna - tm_dna (pure LNA effect)
      lna_positions : list,
      method        : list,    # METADATA: param sets actually touched
      per_doublet   : list,    # per-doublet breakdown for the LNA calculation
      warnings      : list,
    }
    """
    seq = sequence.upper().strip()
    warnings: list[str] = []

    # Validate
    invalid = set(seq) - {"A", "T", "G", "C"}
    if invalid:
        return {
            "tm_dna": None, "tm_lna": None, "delta_tm": None,
            "lna_positions": lna_positions, "method": [], "per_doublet": [],
            "warnings": [f"Unsupported bases in sequence: {sorted(invalid)}"],
        }
    if len(seq) < 2:
        return {
            "tm_dna": None, "tm_lna": None, "delta_tm": None,
            "lna_positions": lna_positions, "method": [], "per_doublet": [],
            "warnings": ["Sequence too short for NN calculation (need ≥ 2 nt)"],
        }

    # 3'-terminal LNA warning (LNA_AVOID_3PRIME_TERMINAL)
    last_idx = len(seq) - 1
    if last_idx in set(lna_positions):
        warnings.append(
            f"LNA at 3’-terminal position ({last_idx}) may interfere with "
            "polymerase extension. Included per request but use with caution."
        )

    # Compute baseline (DNA only)
    try:
        dna_result = _nn_tm(seq, [], params)
    except (KeyError, ValueError) as exc:
        return {
            "tm_dna": None, "tm_lna": None, "delta_tm": None,
            "lna_positions": lna_positions, "method": [], "per_doublet": [],
            "warnings": [f"DNA Tm calculation failed: {exc}"],
        }

    # Compute LNA-substituted
    try:
        lna_result = _nn_tm(seq, lna_positions, params)
    except (KeyError, ValueError) as exc:
        return {
            "tm_dna": dna_result["tm"], "tm_lna": None, "delta_tm": None,
            "lna_positions": lna_positions, "method": dna_result["param_sources"],
            "per_doublet": [], "warnings": [f"LNA Tm calculation failed: {exc}"],
        }

    # Aggregate method metadata
    method = list(dict.fromkeys(
        dna_result["param_sources"] + lna_result["param_sources"]
    ))

    # Caveats — only claim benchmark coverage for the parameter set actually used.
    # mctigue04 = isolated single-LNA (benchmarked); owczarzy11 = consecutive LNA:LNA
    # (NOT covered by the single-LNA benchmark). [Week2 C10]
    has_single = "mctigue04" in method
    has_consecutive = "owczarzy11" in method
    benchmark_coverage = (
        "mixed" if (has_single and has_consecutive)
        else "consecutive_lna_unbenchmarked" if has_consecutive
        else "single_lna"
    )
    warnings.append(_CAVEAT_LNA_GENERAL)
    if has_single:
        warnings.append(_CAVEAT_BENCHMARKED_SINGLE_LNA)
    if has_consecutive:
        warnings.append(_CAVEAT_CONSECUTIVE_LNA_UNBENCHMARKED)

    tm_dna   = dna_result["tm"]
    tm_lna   = lna_result["tm"]
    delta_tm = round(tm_lna - tm_dna, 1)

    return {
        "tm_dna":        tm_dna,
        "tm_lna":        tm_lna,
        "delta_tm":      delta_tm,
        "lna_positions": lna_positions,
        "method":        method,
        "per_doublet":   lna_result["per_doublet"],
        "benchmark_coverage": benchmark_coverage,
        "warnings":      warnings,
    }


# ----------------------------------------------------------------
# SECTION 8: suggest_lna_positions
# ----------------------------------------------------------------

def _comb_count(n: int, k: int) -> int:
    """C(n, k) without importing scipy."""
    if k < 0 or k > n:
        return 0
    if k == 0 or k == n:
        return 1
    k = min(k, n - k)
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result


def suggest_lna_positions(
    sequence: str,
    target_tm: float,
    params: dict,
    max_lna: int = 4,
    mode: str = "tm",
    sibling_mismatch_positions: list = None,
) -> dict:
    """
    Find optimal LNA substitution positions for a DNA primer.

    Parameters
    ----------
    sequence                  : DNA 5'→3', A/T/G/C
    target_tm                 : desired Tm in °C (for mode="tm")
    params                    : ion conditions (same keys as calc_lna_tm)
    max_lna                   : max LNA positions to add (default 4)
    mode                      : "tm" → minimize LNA count to reach target_tm
                                "discrimination" → prefer sibling_mismatch_positions
    sibling_mismatch_positions: 0-based positions where sibling miRNA differs
                                (only used in mode="discrimination")

    Search strategy
    ---------------
    exhaustive  if C(len(eligible), max_lna) ≤ LNA_EXHAUSTIVE_LIMIT
    greedy      otherwise (add best position each round; recompute because of cooperativity)

    eligible_positions: all positions 0 to n-1.
    LNA_AVOID_3PRIME_TERMINAL=True → warning added but position IS eligible.

    Returns
    -------
    {
      suggested_positions : list,
      tm_achieved         : float | None,
      target_met          : bool,
      search              : "exhaustive" | "greedy",
      mode                : str,
      discrimination_gain : float | None,
      warnings            : list,
    }
    """
    # Import here to avoid circular import at module level
    from .constants import (
        LNA_EXHAUSTIVE_LIMIT,
        LNA_AVOID_3PRIME_TERMINAL,
    )

    seq = sequence.upper().strip()
    n   = len(seq)
    warnings: list[str] = []

    if sibling_mismatch_positions is None:
        sibling_mismatch_positions = []

    # Validate sequence
    invalid = set(seq) - {"A", "T", "G", "C"}
    if invalid:
        return _suggest_failure(f"Unsupported bases: {sorted(invalid)}", mode)
    if n < 2:
        return _suggest_failure("Sequence too short (need ≥ 2 nt)", mode)

    # Eligible positions: all 0..n-1
    eligible = list(range(n))

    # 3'-terminal warning
    last_idx = n - 1
    if LNA_AVOID_3PRIME_TERMINAL:
        warnings.append(
            f"Position {last_idx} (3’-terminal) is eligible but LNA there may "
            "hinder polymerase extension — prefer interior positions."
        )

    # Baseline Tm (DNA only)
    try:
        dna_res = _nn_tm(seq, [], params)
        tm_dna  = dna_res["tm"]
    except (KeyError, ValueError) as exc:
        return _suggest_failure(f"Baseline Tm failed: {exc}", mode)

    # Determine search strategy
    total_combos = sum(_comb_count(len(eligible), k) for k in range(1, max_lna + 1))
    use_exhaustive = (_comb_count(len(eligible), max_lna) <= LNA_EXHAUSTIVE_LIMIT)
    search_label = "exhaustive" if use_exhaustive else "greedy"

    best_positions: list[int] = []
    tm_achieved: float | None = None
    target_met = False

    # --- mode = "tm" ---
    if mode == "tm":
        if tm_dna >= target_tm:
            warnings.append(
                f"Baseline DNA Tm ({tm_dna}°C) already meets or exceeds "
                f"target ({target_tm}°C). No LNA substitutions needed."
            )
            return {
                "suggested_positions": [],
                "tm_achieved":        tm_dna,
                "target_met":         True,
                "search":             search_label,
                "mode":               mode,
                "discrimination_gain": None,
                "warnings":           warnings + [_CAVEAT_LNA_GENERAL],
            }

        if use_exhaustive:
            # Try k=1,2,...,max_lna; stop at first k where target met
            for k in range(1, max_lna + 1):
                found = False
                for combo in itertools.combinations(eligible, k):
                    try:
                        res = _nn_tm(seq, list(combo), params)
                        if res["tm"] >= target_tm:
                            best_positions = list(combo)
                            tm_achieved    = res["tm"]
                            target_met     = True
                            found          = True
                            break
                    except (KeyError, ValueError):
                        continue
                if found:
                    break
            # If not met, find best k=max_lna combo by Tm
            if not target_met:
                best_tm = -999.0
                for combo in itertools.combinations(eligible, max_lna):
                    try:
                        res = _nn_tm(seq, list(combo), params)
                        if res["tm"] > best_tm:
                            best_tm        = res["tm"]
                            best_positions = list(combo)
                            tm_achieved    = res["tm"]
                    except (KeyError, ValueError):
                        continue
                warnings.append(
                    f"Target Tm {target_tm}°C not reachable with ≤{max_lna} "
                    f"LNA substitutions. Best achieved: {tm_achieved}°C."
                )
        else:
            # Greedy: add position with highest Tm gain each round
            current_positions: list[int] = []
            remaining = list(eligible)
            for _ in range(max_lna):
                best_gain   = -999.0
                best_pos    = None
                best_tm_val = None
                for pos in remaining:
                    candidate = current_positions + [pos]
                    try:
                        res = _nn_tm(seq, candidate, params)
                        gain = res["tm"] - tm_dna
                        if gain > best_gain:
                            best_gain   = gain
                            best_pos    = pos
                            best_tm_val = res["tm"]
                    except (KeyError, ValueError):
                        continue
                if best_pos is None:
                    break
                current_positions.append(best_pos)
                remaining.remove(best_pos)
                tm_achieved = best_tm_val
                if best_tm_val is not None and best_tm_val >= target_tm:
                    target_met = True
                    break
            best_positions = current_positions
            if not target_met:
                warnings.append(
                    f"Target Tm {target_tm}°C not reachable with ≤{max_lna} "
                    f"LNA substitutions (greedy). Best achieved: {tm_achieved}°C."
                )

    # --- mode = "discrimination" ---
    elif mode == "discrimination":
        # Score each candidate set:
        #   score = frac_covered * 0.6 + (tm_gain / max_possible_gain) * 0.4
        # max_possible_gain estimated from max_lna greedy run
        disc_positions = set(sibling_mismatch_positions)

        def _score_candidate(combo: list) -> float:
            try:
                res = _nn_tm(seq, combo, params)
                tm_g = max(0.0, res["tm"] - tm_dna)
            except (KeyError, ValueError):
                return -1.0
            covered  = len(set(combo) & disc_positions)
            frac_cov = covered / max(len(disc_positions), 1)
            # Normalise Tm gain by a rough max (3°C per LNA * max_lna)
            tm_norm  = min(1.0, tm_g / max(3.0 * max_lna, 1.0))
            return frac_cov * 0.6 + tm_norm * 0.4

        if use_exhaustive:
            best_score = -1.0
            for k in range(1, max_lna + 1):
                for combo in itertools.combinations(eligible, k):
                    s = _score_candidate(list(combo))
                    if s > best_score:
                        best_score     = s
                        best_positions = list(combo)
        else:
            # Greedy by discrimination score
            current_positions_d: list[int] = []
            remaining_d = list(eligible)
            for _ in range(max_lna):
                best_score_g  = -1.0
                best_pos_g    = None
                for pos in remaining_d:
                    candidate = current_positions_d + [pos]
                    s = _score_candidate(candidate)
                    if s > best_score_g:
                        best_score_g = s
                        best_pos_g   = pos
                if best_pos_g is None:
                    break
                current_positions_d.append(best_pos_g)
                remaining_d.remove(best_pos_g)
                # Check if we've covered all mismatch positions
                if disc_positions and disc_positions.issubset(set(current_positions_d)):
                    break
            best_positions = current_positions_d

        # Compute final Tm for best set
        try:
            final_res   = _nn_tm(seq, best_positions, params)
            tm_achieved = final_res["tm"]
            target_met  = (tm_achieved >= target_tm)
        except (KeyError, ValueError):
            tm_achieved = None
            target_met  = False

    else:
        return _suggest_failure(f"Unknown mode: {mode!r}. Use 'tm' or 'discrimination'.", mode)

    # Compute discrimination_gain
    discrimination_gain = None
    if tm_achieved is not None:
        discrimination_gain = round(tm_achieved - tm_dna, 1)

    # 3'-terminal warning for chosen positions
    if last_idx in set(best_positions) and LNA_AVOID_3PRIME_TERMINAL:
        warnings.append(
            f"Suggested set includes 3’-terminal position {last_idx}. "
            "Verify extension efficiency with synthesis provider."
        )

    warnings.append(_CAVEAT_LNA_GENERAL)
    _has_consecutive = any(
        b - a == 1 for a, b in zip(sorted(best_positions), sorted(best_positions)[1:])
    )
    warnings.append(
        _CAVEAT_CONSECUTIVE_LNA_UNBENCHMARKED if _has_consecutive
        else _CAVEAT_BENCHMARKED_SINGLE_LNA
    )

    return {
        "suggested_positions": best_positions,
        "tm_achieved":         tm_achieved,
        "target_met":          target_met,
        "search":              search_label,
        "mode":                mode,
        "discrimination_gain": discrimination_gain,
        "warnings":            warnings,
    }


def _suggest_failure(reason: str, mode: str) -> dict:
    """Return a structured failure result from suggest_lna_positions."""
    return {
        "suggested_positions": [],
        "tm_achieved":         None,
        "target_met":          False,
        "search":              None,
        "mode":                mode,
        "discrimination_gain": None,
        "warnings":            [reason, _CAVEAT_LNA_GENERAL],
    }
