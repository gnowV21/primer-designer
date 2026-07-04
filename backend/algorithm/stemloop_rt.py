# ================================================================
# stemloop_rt.py — Module 1: Stem-loop RT primer design
# Design ONE unique stem-loop RT primer per miRNA.
# Structure (5'→3'): [STEMLOOP_BODY 44nt] + [RC of 3' overhang]
# ================================================================

from .constants import (
    STEMLOOP_BODY, OVERHANG_LENGTH_DEFAULT, OVERHANG_LENGTH_MIN, OVERHANG_LENGTH_MAX,
    MFE_STEMLOOP_MIN, MFE_STEMLOOP_MAX,
    MFE_STEMLOOP_MIN_RNA, MFE_STEMLOOP_MAX_RNA,
    GC_STEMLOOP_MIN, GC_STEMLOOP_MAX,
    REFOLDING_PROTOCOL,
    USE_HYBRID_TM,
    P3_RT_MV_CONC,
    P3_DEFAULT_MV_CONC, P3_DEFAULT_DV_CONC, P3_DEFAULT_DNTP_CONC,
    P3_DEFAULT_DNA_CONC, P3_DEFAULT_TEMP_C,
)
from .hybrid_tm import predict_hybrid_tm
from .sequence_utils import rna_to_dna, reverse_complement, calculate_gc
from .thermodynamics import calculate_tm_nn, calculate_end_stability

# ViennaRNA — optional, fallback to primer3 MFE estimate when unavailable
try:
    import RNA as _RNA
    _VIENNARNA = True
except ImportError:
    _VIENNARNA = False

import primer3


def design_stemloop_rt(mature_sequence: str, params: dict) -> dict:
    """
    Design the stem-loop RT primer for a given mature miRNA.

    Structure (5'→3'):
      [STEMLOOP_BODY 44nt] + [RC of 3' overhang N nt]

    Sources: Chen et al. 2005 [Chen05], Kramer 2011 [K11], Report 2 [R2]
    """
    binding_len = int(params.get("bindingRegion3prime", OVERHANG_LENGTH_DEFAULT))
    binding_len = max(OVERHANG_LENGTH_MIN, min(OVERHANG_LENGTH_MAX, binding_len))

    # Step 1: Extract 3' overhang from miRNA
    overhang_rna = mature_sequence[-binding_len:]
    overhang_dna = rna_to_dna(overhang_rna)
    overhang_rc  = reverse_complement(overhang_dna)

    # Step 2: Build full primer
    primer_seq = STEMLOOP_BODY + overhang_rc

    # Step 3: Thermodynamics
    gc = calculate_gc(primer_seq)
    tm_full = calculate_tm_nn(primer_seq, params)

    # MFE of hairpin — ViennaRNA preferred; primer3-py fallback
    mfe, structure, mfe_method = _compute_mfe(primer_seq, params)

    end_stab = calculate_end_stability(primer_seq[-5:], params)

    # Step 4: Validate
    warnings = []
    pass_flags = {}

    # Use RNA-calibrated thresholds when ViennaRNA or RNAfold was used;
    # fall back to the primer3 DNA-proxy thresholds otherwise.
    _rna_method = mfe_method in ("ViennaRNA", "RNAfold")
    mfe_min = float(params.get("mfeMin", MFE_STEMLOOP_MIN_RNA if _rna_method else MFE_STEMLOOP_MIN))
    mfe_max = float(params.get("mfeMax", MFE_STEMLOOP_MAX_RNA if _rna_method else MFE_STEMLOOP_MAX))

    if not (mfe_min <= mfe <= mfe_max):
        severity = "critical" if (mfe < mfe_min - 3 or mfe > mfe_max + 3) else "warning"
        warnings.append({
            "field": "mfe",
            "severity": severity,
            "message": (
                f"Stem-loop MFE = {mfe} kcal/mol is outside the optimal range "
                f"({mfe_min} to {mfe_max} kcal/mol). "
                + ("Structure too stable — may impede DNA polymerase during PCR."
                   if mfe < mfe_min
                   else "Structure too weak — base stacking may not enhance RT efficiency.")
            ),
        })
    pass_flags["mfe_in_range"] = mfe_min <= mfe <= mfe_max

    if not (GC_STEMLOOP_MIN <= gc <= GC_STEMLOOP_MAX):
        warnings.append({
            "field": "gc_content",
            "severity": "warning",
            "message": f"GC content {gc}% is outside the recommended range ({GC_STEMLOOP_MIN}–{GC_STEMLOOP_MAX}%).",
        })
    pass_flags["gc_in_range"] = GC_STEMLOOP_MIN <= gc <= GC_STEMLOOP_MAX

    if binding_len != OVERHANG_LENGTH_DEFAULT:
        warnings.append({
            "field": "binding_region",
            "severity": "info",
            "message": (
                f"3' binding region is {binding_len} nt (recommended: {OVERHANG_LENGTH_DEFAULT} nt). "
                "Changing from 6 nt may reduce steric hindrance against pri-/pre-miRNA precursors "
                "(Chen et al. 2005)."
            ),
        })

    include_refold = params.get("enableRefoldingProtocol", True)

    # [RESEARCH_QUESTIONS_UX A4] 3' isomiR advisory: RT overhang binds the 3' end of
    # mature miRNA. Non-templated nucleotide additions (3' isomiRs) at the 3' terminus
    # can impair RT primer annealing, reducing cDNA yield for isoforms with terminal
    # additions/truncations. No database coverage for 3' isomiRs yet — general advisory.
    warnings.append({
        "field": "three_prime_isomir",
        "severity": "info",
        "message": (
            f"RT overhang binds the 3' end of the miRNA ({binding_len} nt). "
            "Non-templated 3' additions (3' isomiRs) can reduce RT efficiency for "
            "terminal-addition isoforms. Verify with melting curve analysis if "
            "expression levels appear unexpectedly low."
        ),
    })

    # [RESEARCH_QUESTIONS_UX A2] Compute DNA:RNA hybrid Tm for the RT overhang.
    # overhang_rc = DNA 5'→3' strand that anneals to miRNA 3' end (RNA).
    # USE_HYBRID_TM gate: True → Sugimoto 1995 NN; False → label-only fallback.
    if USE_HYBRID_TM:
        _hybrid = predict_hybrid_tm(
            dna_5to3=overhang_rc,
            dna_conc_nM=4000.0,       # 4 μM: Sugimoto 1995 measurement conditions
            mv_conc_mM=float(P3_RT_MV_CONC),  # RT buffer: 75 mM KCl [K11]
        )
        _tm_hybrid_c   = _hybrid["tm_c"]
        _tm_chemistry  = "DNA:RNA"
        _tm_accuracy   = _hybrid["accuracy"]
        _tm_note       = (
            f"RT overhang hybrid Tm (Sugimoto 1995 DNA:RNA NN): "
            f"{f'{_tm_hybrid_c}°C' if _tm_hybrid_c is not None else 'unavailable'} "
            f"at 4 μM, 75 mM KCl. "
            "Full-primer Tm above uses primer3 DNA:DNA NN (SantaLucia 1998) — indicative. "
            + "; ".join(_hybrid["caveats"])
        )
    else:
        _hybrid        = None
        _tm_hybrid_c   = None
        _tm_chemistry  = "DNA:RNA"
        _tm_accuracy   = "approximate"
        _tm_note       = (
            "approximate (DNA:DNA NN model; true DNA:RNA hybrid Tm may differ 3–8°C). "
            "Enable USE_HYBRID_TM in constants.py for Sugimoto 1995 model."
        )

    return {
        "sequence": primer_seq,
        "length": len(primer_seq),
        "overhang_rna": overhang_rna,
        "overhang_dna": overhang_dna,
        "overhang_rc": overhang_rc,
        "binding_length": binding_len,
        "gc_percent": gc,
        "tm_full": round(tm_full, 1),
        # tm_full uses primer3 DNA:DNA NN (SantaLucia 1998) — informational for the full primer.
        "tm_full_chemistry": "DNA:DNA",
        "tm_full_accuracy":  "informational (primer3, DNA:DNA NN; actual RT step involves DNA:RNA hybrid)",
        # tm_hybrid: Tm of the RT overhang × miRNA duplex (DNA:RNA, Sugimoto 1995 NN)
        "tm_hybrid": _hybrid,
        "tm_hybrid_c": _tm_hybrid_c,
        "tm_chemistry": _tm_chemistry,
        "tm_accuracy":  _tm_accuracy,
        "tm_note": _tm_note,
        "mfe": mfe,
        "mfe_method": mfe_method,
        "hairpin_structure": structure,
        "end_stability_3prime": end_stab,
        "warnings": warnings,
        "pass_flags": pass_flags,
        "rt_primer_conc_note": "Use 1 nM final concentration in RT reaction (Kramer 2011), not 50 nM from Chen 2005.",
        "refolding_protocol": REFOLDING_PROTOCOL if include_refold else None,
        "sources": ["Chen et al. 2005", "Kramer 2011 Unit 15.10", "Varkonyi-Gasic et al. 2007", "Report 2 HG Lab"],
    }


def _compute_mfe(primer_seq: str, params: dict) -> tuple:
    """
    Compute MFE of the stem-loop RT primer hairpin.

    Priority:
      1. ViennaRNA Python bindings (RNA.fold) — most accurate, requires C library
      2. RNAfold subprocess — accurate, works when binary is installed but Python
         bindings are absent (e.g. conda RNAfold on Windows without ViennaRNA-py)
      3. primer3.calc_hairpin ΔG — DNA-based proxy, ~15-20% off but always available
    """
    import subprocess as _subprocess

    rna_str = primer_seq.replace("T", "U").upper()

    # ── 1. ViennaRNA Python bindings ─────────────────────────────────────────
    if _VIENNARNA:
        try:
            structure, mfe = _RNA.fold(rna_str)
            return round(float(mfe), 2), structure, "ViennaRNA"
        except Exception:
            pass

    # ── 2. RNAfold subprocess ─────────────────────────────────────────────────
    # Handles: conda RNAfold on Windows, system RNAfold on Linux/macOS when
    # the Python bindings are not importable.
    try:
        proc = _subprocess.run(
            ["RNAfold", "--noPS"],
            input=rna_str,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            lines = proc.stdout.strip().split("\n")
            if len(lines) >= 2:
                struct_line = lines[1]
                paren_pos   = struct_line.rfind("(")
                if paren_pos != -1:
                    structure = struct_line[:paren_pos].strip()
                    mfe       = float(struct_line[paren_pos + 1:].rstrip(")").strip())
                    return round(mfe, 2), structure, "RNAfold"
    except (FileNotFoundError, _subprocess.TimeoutExpired, ValueError, Exception):
        pass

    # ── 3. primer3-py calc_hairpin as MFE proxy ───────────────────────────────
    # DNA-based ΔG; correlates with RNA MFE but is ~15-20% less negative.
    # Use the DNA sequence (T instead of U) — primer3 expects DNA.
    try:
        result    = primer3.calc_hairpin(
            seq=primer_seq,
            mv_conc=float(params.get("saltConcentration",       P3_DEFAULT_MV_CONC)),
            dv_conc=float(params.get("magnesiumConcentration",  P3_DEFAULT_DV_CONC)),
            dntp_conc=float(params.get("dntpTotal",             P3_DEFAULT_DNTP_CONC)),
            dna_conc=float(params.get("primerConcentration",    P3_DEFAULT_DNA_CONC)),
            temp_c=P3_DEFAULT_TEMP_C,
        )
        mfe_proxy = round(float(result.dg) / 1000, 2)
        return mfe_proxy, "N/A (primer3 proxy)", "primer3-py (ViennaRNA unavailable)"
    except Exception:
        return -11.5, "N/A", "default (all MFE libraries unavailable)"
