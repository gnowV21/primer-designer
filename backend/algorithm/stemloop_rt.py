# ================================================================
# stemloop_rt.py — Module 1: Stem-loop RT primer design
# Design ONE unique stem-loop RT primer per miRNA.
# Structure (5'→3'): [STEMLOOP_BODY 44nt] + [RC of 3' overhang]
# ================================================================

from .constants import (
    STEMLOOP_BODY, OVERHANG_LENGTH_DEFAULT, OVERHANG_LENGTH_MIN, OVERHANG_LENGTH_MAX,
    MFE_STEMLOOP_MIN, MFE_STEMLOOP_MAX, MFE_STEMLOOP_OPTIMAL,
    MFE_STEMLOOP_MIN_DNA, MFE_STEMLOOP_MAX_DNA, MFE_STEMLOOP_OPTIMAL_DNA,
    GC_STEMLOOP_MIN, GC_STEMLOOP_MAX,
    REFOLDING_PROTOCOL,
    USE_HYBRID_TM,
    SHORT_DUPLEX_NT_THRESHOLD, TM_SHORT_DUPLEX_UNCERTAINTY_C,
    P3_RT_MV_CONC,
    P3_DEFAULT_TEMP_C,
)
from .hybrid_tm import predict_hybrid_tm
from .specificity_check.isomir_flag import check_3prime_isomir_flag
from .sequence_utils import rna_to_dna, reverse_complement, calculate_gc
from .thermodynamics import calculate_tm_nn, calculate_end_stability, _get_p3_params

import algorithm.primer3_safe as primer3  # thread-safe wrapper (see primer3_safe.py)

# ViennaRNA — optional, fallback to primer3 MFE estimate when unavailable.
# The RT primer is DNA, so it is folded with the DNA energy set (Mathews 2004).
# The parameter object is built once and substituted per fold_compound, so the
# global RNA parameters used elsewhere (template_structure) are never changed.
_MFE_TEMP_C = 37.0
try:
    import RNA as _RNA
    _RNA.params_load_DNA_Mathews2004()
    _DNA_MD = _RNA.md()
    _DNA_MD.temperature = _MFE_TEMP_C
    _DNA_PARAMS = _RNA.param(_DNA_MD)
    _RNA.params_load_RNA_Turner2004()          # restore the library default
    _VIENNARNA = True
except Exception:
    _VIENNARNA = False

MFE_METHOD_VIENNA = "ViennaRNA (DNA, Mathews 2004, 37 °C)"
MFE_METHOD_RNAFOLD = "RNAfold (DNA, Mathews 2004, 37 °C)"
MFE_METHOD_PRIMER3 = "primer3-py hairpin ΔG (DNA proxy; ViennaRNA unavailable)"


def mfe_thresholds(mfe_method: str) -> tuple:
    """(min, max, optimum) kcal/mol for the engine that produced the MFE."""
    if mfe_method in (MFE_METHOD_VIENNA, MFE_METHOD_RNAFOLD):
        return MFE_STEMLOOP_MIN_DNA, MFE_STEMLOOP_MAX_DNA, MFE_STEMLOOP_OPTIMAL_DNA
    return MFE_STEMLOOP_MIN, MFE_STEMLOOP_MAX, MFE_STEMLOOP_OPTIMAL


def design_stemloop_rt(mature_sequence: str, params: dict, mirna_name: str = "") -> dict:
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

    # Thresholds depend on the folding engine that produced the value.
    _t_min, _t_max, _ = mfe_thresholds(mfe_method)
    mfe_min = float(params.get("mfeMin", _t_min))
    mfe_max = float(params.get("mfeMax", _t_max))

    if mfe is None:
        # No folding engine available: report it, never substitute a number (SCI-03).
        warnings.append({
            "field": "mfe",
            "severity": "warning",
            "message": "Stem-loop MFE could not be computed (no folding engine available); "
                       "this criterion is excluded from the score.",
        })
    elif not (mfe_min <= mfe <= mfe_max):
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
    pass_flags["mfe_in_range"] = mfe is not None and mfe_min <= mfe <= mfe_max

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

    # 3' isomiR advisory (Week2 C11): the RT overhang binds the 3' end, so 3' isomiRs
    # (templated shift, non-templated uridylation/adenylation) reduce RT capture of the
    # affected isoforms. Data-driven now — only miRNAs with a documented entry raise a
    # warning; others get a neutral info note (absence of evidence != evidence of absence).
    three_prime_isomir = check_3prime_isomir_flag(
        mirna_name, binding_len, sample_type=params.get("sampleType"))
    if three_prime_isomir["three_prime_isomir_risk"]:
        warnings.append({
            "field": "three_prime_isomir",
            "severity": "warning",
            "message": three_prime_isomir["warning"],
            "source": three_prime_isomir.get("source"),
        })
    # Separate from the capture warning above: the risk here is a shift in isoform
    # composition reading as a change in miRNA level [Nejad18], which can fire even
    # when the canonical form is still the majority.
    if three_prime_isomir.get("fold_change_bias_risk"):
        warnings.append({
            "field": "three_prime_isomir_fold_change",
            "severity": "warning",
            "message": three_prime_isomir["fold_change_bias_warning"],
            "source": "Nejad C et al. RNA 2018;24:332-341 [PMID:29263133]",
        })
    elif three_prime_isomir.get("summary"):
        warnings.append({
            "field": "three_prime_isomir",
            "severity": "info",
            "message": three_prime_isomir["summary"] + (
                f" The RT overhang ({binding_len} nt) pairs with the canonical 3' end, so "
                "these isoforms are under-counted."
            ),
            "source": three_prime_isomir.get("source"),
        })
    else:
        warnings.append({
            "field": "three_prime_isomir",
            "severity": "info",
            "message": (
                f"The RT overhang binds the 3' end of the miRNA ({binding_len} nt). "
                "3' isomiRs (non-templated additions/truncations) can reduce RT efficiency "
                "for affected isoforms."
            ),
            "coverage_note": three_prime_isomir.get("coverage_note"),
        })

    # [RESEARCH_QUESTIONS_UX A2] Compute DNA:RNA hybrid Tm for the RT overhang.
    # overhang_rc = DNA 5'→3' strand that anneals to miRNA 3' end (RNA).
    # USE_HYBRID_TM gate: True → Sugimoto 1995 NN; False → label-only fallback.
    # Week2 P4: the RT overhang is 6 nt — below SHORT_DUPLEX_NT_THRESHOLD (8), a point Tm
    # from an NN model is not defensible (initiation + terminal fraying dominate). Report
    # dG37 and an indicative Tm band instead of a point value.
    _reportable_as_tm = binding_len >= SHORT_DUPLEX_NT_THRESHOLD
    _tm_hybrid_band_c = None
    _dg37_kcal_mol = None
    if USE_HYBRID_TM:
        _hybrid = predict_hybrid_tm(
            dna_5to3=overhang_rc,
            dna_conc_nM=4000.0,       # 4 μM: Sugimoto 1995 measurement conditions
            mv_conc_mM=float(P3_RT_MV_CONC),  # RT buffer: 75 mM KCl [K11]
        )
        _tm_raw        = _hybrid["tm_c"]
        _tm_chemistry  = "DNA:RNA"
        _tm_accuracy   = _hybrid["accuracy"]
        # dG37 (kcal/mol) = dH − T·dS, T = 310.15 K, dS in cal/mol·K.
        if _hybrid.get("dH") is not None and _hybrid.get("dS") is not None:
            _dg37_kcal_mol = round(_hybrid["dH"] - 310.15 * _hybrid["dS"] / 1000.0, 2)
        if _reportable_as_tm:
            _tm_hybrid_c = _tm_raw
            _tm_note = (
                f"RT overhang hybrid Tm (Sugimoto 1995 DNA:RNA NN): {_tm_raw}°C at 4 μM, "
                "75 mM KCl. Full-primer Tm above uses primer3 DNA:DNA NN (SantaLucia 1998) — "
                "indicative. " + "; ".join(_hybrid["caveats"])
            )
        else:
            _tm_hybrid_c = None   # do not present a point Tm for a <8 bp duplex
            if _tm_raw is not None:
                _tm_hybrid_band_c = [round(_tm_raw - TM_SHORT_DUPLEX_UNCERTAINTY_C, 1),
                                     round(_tm_raw + TM_SHORT_DUPLEX_UNCERTAINTY_C, 1)]
            if _dg37_kcal_mol is not None:
                # Normal path: hybrid NN succeeded → report ΔG37 + indicative band.
                _tm_note = (
                    f"RT overhang is {binding_len} nt (< {SHORT_DUPLEX_NT_THRESHOLD} bp): a point Tm "
                    "is not reportable — nearest-neighbour initiation and terminal fraying dominate at "
                    f"this length. Reported instead: ΔG37 = {_dg37_kcal_mol} kcal/mol (Sugimoto 1995 "
                    f"DNA:RNA NN, 4 μM, 75 mM KCl) and an indicative Tm band "
                    f"{_tm_hybrid_band_c if _tm_hybrid_band_c else 'n/a'} (± "
                    f"{TM_SHORT_DUPLEX_UNCERTAINTY_C:.0f} °C, not a statistical CI). Use ΔG37 for "
                    "relative ranking, not the Tm as an absolute value. " + "; ".join(_hybrid["caveats"])
                )
            else:
                # Hybrid NN could not be computed (e.g. unsupported base) — never print "None".
                _tm_note = (
                    f"RT overhang is {binding_len} nt (< {SHORT_DUPLEX_NT_THRESHOLD} bp): a point Tm "
                    "is not reportable, and the DNA:RNA hybrid thermodynamics could not be computed "
                    "for this overhang. " + "; ".join(_hybrid["caveats"])
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
        "tm_hybrid_band_c": _tm_hybrid_band_c,
        "dg37_kcal_mol": _dg37_kcal_mol,
        "reportable_as_tm": _reportable_as_tm,
        "tm_chemistry": _tm_chemistry,
        "tm_accuracy":  _tm_accuracy,
        "tm_note": _tm_note,
        "three_prime_isomir": three_prime_isomir,
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
    MFE (kcal/mol) of the stem-loop RT primer hairpin, folded as DNA.

    Priority:
      1. ViennaRNA Python bindings, DNA energy set (Mathews 2004) at 37 °C
      2. RNAfold binary with `-P DNA` (bindings absent, e.g. conda on Windows)
      3. primer3.calc_hairpin ΔG — DNA proxy, own threshold window
      4. None — no engine; the criterion is excluded from the score (SCI-03)
    """
    import subprocess as _subprocess

    seq = primer_seq.upper()

    # ── 1. ViennaRNA Python bindings (DNA parameters) ────────────────────────
    if _VIENNARNA:
        try:
            fc = _RNA.fold_compound(seq, _DNA_MD)
            fc.params_subst(_DNA_PARAMS)
            structure, mfe = fc.mfe()
            return round(float(mfe), 2), structure, MFE_METHOD_VIENNA
        except Exception:
            pass

    # ── 2. RNAfold subprocess (DNA parameters) ───────────────────────────────
    try:
        proc = _subprocess.run(
            ["RNAfold", "--noPS", "-P", "DNA", "-T", str(_MFE_TEMP_C)],
            input=seq,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            lines = proc.stdout.strip().splitlines()
            if len(lines) >= 2:
                struct_line = lines[1]
                paren_pos   = struct_line.rfind("(")
                if paren_pos != -1:
                    structure = struct_line[:paren_pos].strip()
                    mfe       = float(struct_line[paren_pos + 1:].rstrip(")").strip())
                    return round(mfe, 2), structure, MFE_METHOD_RNAFOLD
    except Exception:
        pass

    # ── 3. primer3-py calc_hairpin as MFE proxy ───────────────────────────────
    # Same ionic conditions (effective monovalent incl. K+/Tris+) as every other
    # primer3 call — audit SCI-05.
    try:
        p3 = _get_p3_params(params)
        result = primer3.calc_hairpin(
            seq=seq,
            mv_conc=p3["mv_conc"], dv_conc=p3["dv_conc"],
            dntp_conc=p3["dntp_conc"], dna_conc=p3["dna_conc"],
            temp_c=P3_DEFAULT_TEMP_C,
        )
        return round(float(result.dg) / 1000, 2), "N/A (primer3 proxy)", MFE_METHOD_PRIMER3
    except Exception:
        return None, None, "unavailable"
