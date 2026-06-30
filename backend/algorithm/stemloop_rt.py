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
)
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
    mfe, structure, mfe_method = _compute_mfe(primer_seq)

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

    return {
        "sequence": primer_seq,
        "length": len(primer_seq),
        "overhang_rna": overhang_rna,
        "overhang_dna": overhang_dna,
        "overhang_rc": overhang_rc,
        "binding_length": binding_len,
        "gc_percent": gc,
        "tm_full": round(tm_full, 1),
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


def _compute_mfe(primer_seq: str) -> tuple:
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
            mv_conc=50.0, dv_conc=1.5, dntp_conc=0.8, dna_conc=200.0,
            temp_c=37.0,
        )
        mfe_proxy = round(float(result.dg) / 1000, 2)
        return mfe_proxy, "N/A (primer3 proxy)", "primer3-py (ViennaRNA unavailable)"
    except Exception:
        return -11.5, "N/A", "default (all MFE libraries unavailable)"
