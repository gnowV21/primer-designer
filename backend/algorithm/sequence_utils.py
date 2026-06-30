# ================================================================
# sequence_utils.py — Sequence manipulation utilities
# ================================================================

RNA_TO_DNA_TABLE = str.maketrans("AaUuGgCc", "AaTtGgCc")
DNA_COMPLEMENT = str.maketrans("ATGCatgc", "TACGtacg")


def rna_to_dna(rna_seq: str) -> str:
    """Convert RNA sequence to DNA (U→T). Preserves case."""
    return rna_seq.translate(RNA_TO_DNA_TABLE)


def reverse_complement(dna_seq: str) -> str:
    """Return reverse complement of a DNA sequence."""
    return dna_seq.translate(DNA_COMPLEMENT)[::-1]


def validate_rna_sequence(seq: str) -> tuple:
    """
    Validate RNA sequence. Returns (is_valid, error_message).
    """
    seq = seq.upper().strip()
    if not seq:
        return False, "Sequence is empty."
    if any(b == "T" for b in seq):
        return False, "Character 'T' detected. This must be an RNA sequence — use 'U' instead of 'T'."
    invalid = set(seq) - set("AUGC")
    if invalid:
        return False, f"Invalid characters detected: {', '.join(sorted(invalid))}. Only A, U, G, C are accepted."
    if len(seq) < 15:
        return False, f"Sequence too short ({len(seq)} nt). Mature miRNAs are typically 17–24 nt."
    if len(seq) > 30:
        return False, f"Sequence too long ({len(seq)} nt). Mature miRNAs are typically 17–24 nt."
    return True, ""


def calculate_gc(sequence: str) -> float:
    """Calculate GC content percentage."""
    seq = sequence.upper()
    if not seq:
        return 0.0
    gc = sum(1 for b in seq if b in "GC")
    return round((gc / len(seq)) * 100, 1)


def calculate_gc_skew(sequence: str) -> float:
    """
    GC-skew = (G - C) / (G + C).
    Range -1.0 to +1.0. Positive = more G (G-quadruplex risk). [PAST24]
    """
    seq = sequence.upper()
    g = seq.count("G")
    c = seq.count("C")
    if g + c == 0:
        return 0.0
    return round((g - c) / (g + c), 3)


def check_homopolymer(sequence: str, max_run: int = 5) -> bool:
    """Return True if sequence has homopolymer run > max_run. [P3P Max Poly-X=5]"""
    seq = sequence.upper()
    for base in "ATGC":
        if base * (max_run + 1) in seq:
            return True
    return False


def check_gc_clamp(sequence: str, window: int = 5, min_gc: int = 1, max_consecutive: int = 3) -> tuple:
    """
    Check 3' GC clamp rules. Returns (passes, reason_if_fail).
    - At least min_gc G/C in last window bases
    - No more than max_consecutive consecutive G/C at 3' end
    """
    end = sequence[-window:].upper()
    gc_count = sum(1 for b in end if b in "GC")
    if gc_count < min_gc:
        return False, f"Only {gc_count} G/C in last {window} bases — GC clamp too weak."
    consecutive = 0
    for base in reversed(sequence.upper()):
        if base in "GC":
            consecutive += 1
        else:
            break
    if consecutive > max_consecutive:
        return False, f"{consecutive} consecutive G/C at 3' end — exceeds max {max_consecutive}."
    return True, ""
