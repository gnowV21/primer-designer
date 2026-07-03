# ================================================================
# algorithm/template_structure.py — Template secondary structure check
#
# Fan 2019 (DOI 10.1080/07391102.2018.1498804):
# Hairpin structures within the amplicon — especially in the primer
# binding regions — inhibit PCR. A stem of ≥20 bp at the binding
# site can cause complete loss of product. Recommended: analyse ≥60 bp
# of context around each primer binding region.
#
# Approach:
#   Build the single-stranded cDNA template (bottom strand of the
#   amplicon, 5'→3'). The forward primer anneals to this strand.
#   Fold a TEMPLATE_FOLD_WINDOW-nt window centred on the primer's
#   specific-region binding site using ViennaRNA RNA.fold().
#   Report MFE, structure, and whether the binding site is paired.
#
# Fallback: if ViennaRNA is unavailable, returns a skip result so
# the rest of the pipeline is unaffected.
# ================================================================

from .constants import (
    STEMLOOP_BODY,
    TEMPLATE_FOLD_WINDOW, TEMPLATE_STRUCTURE_MFE_WARN, TEMPLATE_BINDING_PAIRED_MAX,
)
from .sequence_utils import rna_to_dna, reverse_complement

try:
    import RNA as _RNA
    _VIENNARNA = True
except ImportError:
    _VIENNARNA = False


def check_template_structure(
    mature_sequence: str,
    candidate: dict,
    params: dict,
) -> dict:
    """
    Check secondary structure of the cDNA template around the forward
    primer binding site.

    The cDNA template (bottom strand of the amplicon, 5'→3') is the
    single-stranded molecule the forward primer anneals to during PCR.
    If the binding region forms a stable hairpin, primer annealing is
    inhibited [Fan19].

    Args:
        mature_sequence: RNA miRNA sequence (e.g. 'UAGCUUAUCAGACUGAUGUUGA')
        candidate: forward primer candidate dict (must have specific_length,
                   tail_length, and sequence populated)
        params: user parameter dict (unused for now; present for future salt correction)

    Returns:
        {
            "mfe": float,                      # kcal/mol, full-window fold
            "structure": str,                  # dot-bracket of folded window
            "binding_site_paired_bases": int,  # paired bases within binding region
            "has_strong_local_hairpin": bool,  # True → warning triggered
            "binding_region_in_window": [start, end],  # 0-based, half-open
            "window_sequence": str,
            "method": str,
            "warning": str | None,
        }
    """
    if not _VIENNARNA:
        return _skip_result("ViennaRNA not available — template structure check skipped")

    specific_len = candidate.get("specific_length", 14)
    tail_len = candidate.get("tail_length", 5)

    dna = rna_to_dna(mature_sequence).upper()
    remaining_mirna = dna[specific_len:]

    # Amplicon top strand (5'→3'):
    # [tail][specific(=dna[0:specific_len])][remaining miRNA DNA][RC(STEMLOOP_BODY[7:44])]
    amplicon_top = (
        candidate.get("sequence", dna[:specific_len + tail_len])
        + remaining_mirna
        + reverse_complement(STEMLOOP_BODY[7:44])
    )

    # cDNA template = bottom strand of amplicon (5'→3'):
    # RC of amplicon top strand
    cDNA = reverse_complement(amplicon_top)

    # Binding region in cDNA (5'→3'):
    # STEMLOOP_BODY[7:44] is at positions 0..36 (37 nt) of the cDNA top
    # then complement(remaining_mirna) then complement(specific)
    # In cDNA (5'→3'): [RC(STEMLOOP_BODY[7:44])][complement(remaining)][complement(specific)][RC(tail)]
    stem_part_len = len(STEMLOOP_BODY[7:44])      # 37
    remaining_len = len(remaining_mirna)           # miRNA_len - specific_len
    binding_start = stem_part_len + remaining_len  # position in cDNA (5'→3')
    binding_end   = binding_start + specific_len

    # Window: TEMPLATE_FOLD_WINDOW nt centred on binding region
    center    = (binding_start + binding_end) // 2
    half_win  = TEMPLATE_FOLD_WINDOW // 2
    win_start = max(0, center - half_win)
    win_end   = min(len(cDNA), win_start + TEMPLATE_FOLD_WINDOW)
    # adjust if near end
    if win_end - win_start < TEMPLATE_FOLD_WINDOW and win_start > 0:
        win_start = max(0, win_end - TEMPLATE_FOLD_WINDOW)

    window_seq = cDNA[win_start:win_end]

    # Binding region relative to window
    rel_start = max(0, binding_start - win_start)
    rel_end   = min(len(window_seq), binding_end - win_start)

    # Fold with ViennaRNA (convert DNA window to RNA)
    rna_window = window_seq.replace("T", "U").upper()
    try:
        structure, mfe = _RNA.fold(rna_window)
        mfe = round(float(mfe), 2)
    except Exception as exc:
        return _skip_result(f"ViennaRNA fold failed: {exc}")

    # Count paired bases in binding region
    binding_dot_bracket = structure[rel_start:rel_end]
    paired = sum(1 for c in binding_dot_bracket if c != ".")

    has_strong = mfe < TEMPLATE_STRUCTURE_MFE_WARN and paired > TEMPLATE_BINDING_PAIRED_MAX
    warning = None
    if has_strong:
        warning = (
            f"Template secondary structure detected in forward primer binding region "
            f"(window MFE = {mfe:.2f} kcal/mol; {paired} of {specific_len} binding-region "
            f"bases are base-paired in predicted structure). "
            f"Stable hairpin at the binding site may reduce primer annealing efficiency. "
            f"Consider a different specific_length or verify with melting-curve analysis. "
            f"Source: Fan 2019 (DOI 10.1080/07391102.2018.1498804)."
        )

    return {
        "mfe": mfe,
        "structure": structure,
        "binding_site_paired_bases": paired,
        "has_strong_local_hairpin": has_strong,
        "binding_region_in_window": [rel_start, rel_end],
        "window_sequence": window_seq,
        "window_length": len(window_seq),
        "method": "ViennaRNA RNA.fold (DNA converted to RNA; relative stability valid)",
        "warning": warning,
        "source": "Fan 2019, DOI 10.1080/07391102.2018.1498804",
    }


def _skip_result(reason: str) -> dict:
    return {
        "mfe": None,
        "structure": None,
        "binding_site_paired_bases": None,
        "has_strong_local_hairpin": False,
        "binding_region_in_window": None,
        "window_sequence": None,
        "window_length": None,
        "method": "skipped",
        "warning": None,
        "skip_reason": reason,
        "source": "Fan 2019, DOI 10.1080/07391102.2018.1498804",
    }
