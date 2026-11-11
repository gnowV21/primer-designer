# ================================================================
# algorithm/vienna_dna.py — ViennaRNA with the DNA energy set
#
# One place that builds the DNA parameter object (Mathews 2004) and hands it to
# every fold_compound via params_subst(), so the library's global parameters
# (RNA Turner 2004, used by template_structure.py) are never left changed.
# The global switch happens once, at import, before any request is served.
#
# Users:
#   stemloop_rt.py               RT stem-loop MFE (mfe_stemloop)
#   structure_check/__init__.py  full-structure dimer ΔG (hard-filter rule 1)
#
# Dimer ΔG follows Kang 2017 (miPrimer, RNA 24:304, Methods): "The ΔG value is
# calculated by RNAcofold algorithm using the DNA parameters (Gruber et al.
# 2008)". Kang does not state temperature or salt; ViennaRNA's defaults are used
# (37 °C, standard 1.021 M Na⁺ — no salt correction), which is what RNAcofold
# reports when run without options.
# ================================================================

DNA_TEMP_C = 37.0

try:
    import RNA as _RNA
    _RNA.params_load_DNA_Mathews2004()
    DNA_MD = _RNA.md()
    DNA_MD.temperature = DNA_TEMP_C
    DNA_PARAMS = _RNA.param(DNA_MD)
    _RNA.params_load_RNA_Turner2004()          # restore the library default
    AVAILABLE = True
    VERSION = getattr(_RNA, "__version__", "?")
except Exception:                              # bindings absent (e.g. conda on Windows)
    _RNA = None
    DNA_MD = DNA_PARAMS = None
    AVAILABLE = False
    VERSION = None

COFOLD_METHOD = (
    f"RNAcofold (ViennaRNA {VERSION}), DNA parameters Mathews 2004, "
    f"{DNA_TEMP_C:g} °C, 1.021 M Na⁺"
)


def fold_compound(seq: str):
    """A fold_compound on the DNA energy set. Caller checks AVAILABLE first."""
    fc = _RNA.fold_compound(seq, DNA_MD)
    fc.params_subst(DNA_PARAMS)
    return fc


def _has_intermolecular_pair(structure: str, cut: int) -> bool:
    stack = []
    for i, c in enumerate(structure):
        if c == "(":
            stack.append(i)
        elif c == ")" and stack and stack.pop() < cut <= i:
            return True
    return False


def cofold_dg(seq1: str, seq2: str) -> tuple[float, str] | None:
    """
    Dimer ΔG (kcal/mol) of seq1 · seq2 as RNAcofold reports it, plus the
    dot-bracket structure (strands concatenated, no '&').

    If the minimum-free-energy complex has no base pair BETWEEN the two strands
    (each strand only folds on itself), there is no dimer and 0.0 is returned.
    This never happened on the 4506 hsa forward-primer pairs checked
    2026-11-11, but RNAcofold would otherwise report the sum of two hairpins.

    Returns None when ViennaRNA is unavailable.
    """
    if not AVAILABLE:
        return None
    a, b = seq1.upper(), seq2.upper()
    structure, mfe = fold_compound(f"{a}&{b}").mfe_dimer()
    if not _has_intermolecular_pair(structure, len(a)):
        return 0.0, structure
    return round(float(mfe), 2), structure
