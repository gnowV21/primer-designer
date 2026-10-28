# ================================================================
# blast_offtarget.py — BLAST off-target check (Module 10, Phase 3)
#
# Runs blastn against local miRBase (all species), then re-aligns
# with Needleman-Wunsch global alignment (Ye 2012).
# Classifies each hit using Ye 2012 thresholds + Kwok 1990
# 3'-terminal mismatch categories.
#
# Ensembl human cDNA is NOT included: DNase treatment prior to RT
# removes all genomic DNA and unspliced RNA. The only template
# remaining is mature miRNA — off-target risk is limited to miRNA
# family cross-reactivity, which is covered by miRBase multi-species.
#
# Sources:
#   [Ye12]   Ye et al. 2012 BMC Bioinformatics 13:134 (Primer-BLAST)
#   [Kwok90] Kwok et al. 1990 Nucleic Acids Research 18(4):999-1005
# ================================================================

import concurrent.futures
import os
import re
import subprocess
from typing import Optional

import algorithm.primer3_safe as primer3  # thread-safe wrapper (see primer3_safe.py)

from algorithm.constants import (
    BLAST_WORD_SIZE, BLAST_EVALUE_CUTOFF, BLAST_MAX_TARGET_SEQS,
    BLAST_REWARD, BLAST_PENALTY, BLAST_TASK,
    PRIMER_BLAST_IGNORE_ABOVE_MISMATCHES,
    PRIMER_BLAST_3PRIME_WINDOW, PRIMER_BLAST_3PRIME_MIN_MISMATCHES,
    PRIMER_BLAST_MIN_TOTAL_MISMATCHES,
    BLAST_3PRIME_DANGLE_SAFE, PRIMER_BLAST_MIN_3PRIME_ANCHOR,
    BLAST_TM_SAFE_MARGIN, BLAST_TM_CRITICAL_MARGIN, BLAST_CLASSIFIER_VERSION,
    SELF_MAX_END_SHIFT, SELF_MIN_OVERLAP,
    BLAST_MAX_HITS_RETURNED, MIRBASE_HUMAN_PREFIX, UNIVERSAL_REVERSE,
    KWOK_BLOCKING_PAIRS, KWOK_REDUCING_PAIRS,
)
from algorithm.sequence_utils import reverse_complement, rna_to_dna
from algorithm.thermodynamics import _get_p3_params
from .family_crossreactivity import get_family_id

_DB_DIR      = os.path.join(os.path.dirname(__file__), "..", "..", "data", "blast_db")
_MIRBASE_DB  = os.path.join(_DB_DIR, "mirbase_multi")
_METADATA    = os.path.join(_DB_DIR, "metadata.json")

_RISK_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}

_P3_KEYS = ("mv_conc", "dv_conc", "dntp_conc", "dna_conc")


def _blast_env_and_name(db_path: str) -> tuple[dict, str]:
    """Locate the DB via the BLASTDB variable and pass only its name to -db.

    BLAST+ splits -db on spaces (it accepts a space-separated list of databases),
    so a path such as 'D:\\Users\\TIEN VUONG\\...' breaks it. The 8.3 short-name
    workaround fails on volumes where short names are disabled (the default for
    non-system drives since Windows 10). BLASTDB is NCBI's own lookup mechanism and
    takes the directory verbatim, spaces included.
    """
    db_dir = os.path.normpath(os.path.dirname(os.path.abspath(db_path)))
    return dict(os.environ, BLASTDB=db_dir), os.path.basename(db_path)


# ── 3'-terminal mismatch classification ──────────────────────────

_WATSON_CRICK = {"A": "T", "T": "A", "G": "C", "C": "G"}


def classify_3prime_mismatch(primer_base: str, template_base: str) -> str:
    """
    [Kwok90] Table III — 3'-terminal mismatch type by PCR yield.
    Returns 'MATCH' | 'BLOCKING' | 'REDUCING' | 'TOLERANT'.

    template_base is the base on the TEMPLATE strand opposite the primer's 3'
    terminus — Kwok's primer:template notation (A:G = primer A facing template G).
    It is NOT the off-target's sense base: the forward primer has the miRNA's sense
    sequence and anneals to its cDNA, so template = complement of the sense base
    (nw_align does that conversion).
    """
    p, t = primer_base.upper(), template_base.upper()
    if _WATSON_CRICK.get(p) == t:
        return "MATCH"
    if (p, t) in KWOK_BLOCKING_PAIRS:
        return "BLOCKING"   # ~1% PCR yield
    if (p, t) in KWOK_REDUCING_PAIRS:
        return "REDUCING"   # ~5% PCR yield
    return "TOLERANT"       # ~100% PCR yield (T:X, X:T, G:G, most others)


# ── Needleman-Wunsch global alignment ────────────────────────────

def nw_align(seq1: str, seq2: str) -> dict:
    """
    Needleman-Wunsch global alignment via Biopython pairwise2.
    Returns {mismatches, mismatch_positions, aligned_seq1, aligned_seq2,
             primer_3prime_base, template_3prime_base, coverage_pct}.
    Falls back to simple column comparison if biopython unavailable.
    """
    try:
        from Bio import pairwise2
        alignments = pairwise2.align.globalms(
            seq1, seq2,
            2,    # match score
            -1,   # mismatch penalty
            -2,   # gap open
            -0.5, # gap extend
        )
        if not alignments:
            return _column_compare(seq1, seq2)
        a = alignments[0]
        aln1, aln2 = a.seqA, a.seqB
    except ImportError:
        aln1, aln2 = _pad_align(seq1, seq2)

    mismatches = []
    for i, (c1, c2) in enumerate(zip(aln1, aln2)):
        if c1 == "-" or c2 == "-":
            mismatches.append(i)
        elif c1.upper() != c2.upper():
            mismatches.append(i)

    # 3'-terminal bases (last non-gap character). aln2 is the off-target in the
    # primer's own (sense) orientation; the strand the primer actually anneals to is
    # its complement, which is what Kwok's primer:template categories refer to.
    primer_3p  = next((c for c in reversed(aln1) if c != "-"), "N")
    subject_3p = next((c for c in reversed(aln2) if c != "-"), "N").upper()

    return {
        "mismatches":           len(mismatches),
        "mismatch_positions":   mismatches,
        "aligned_primer":       aln1,
        "aligned_template":     aln2,
        "primer_3prime_base":   primer_3p.upper(),
        "template_3prime_base": _WATSON_CRICK.get(subject_3p, "N"),
        "coverage_pct":         round(len(seq1) / max(len(aln1.replace("-", "")), 1) * 100, 1),
        "aln_cols":             len(aln1),
    }


def _pad_align(s1: str, s2: str) -> tuple[str, str]:
    """Simple pad-to-equal-length alignment (no gaps, last resort)."""
    n = max(len(s1), len(s2))
    return s1.ljust(n, "-"), s2.ljust(n, "-")


def _column_compare(s1: str, s2: str) -> dict:
    n = max(len(s1), len(s2))
    a1 = s1.ljust(n, "-")
    a2 = s2.ljust(n, "-")
    mm = [i for i, (c1, c2) in enumerate(zip(a1, a2)) if c1 != c2]
    return {
        "mismatches": len(mm),
        "mismatch_positions": mm,
        "aligned_primer": a1,
        "aligned_template": a2,
        "primer_3prime_base": s1[-1].upper() if s1 else "N",
        "template_3prime_base": _WATSON_CRICK.get(s2[-1].upper(), "N") if s2 else "N",
        "coverage_pct": 100.0,
        "aln_cols": n,
    }


# ── Risk classification ───────────────────────────────────────────

def classify_hit_risk(
    primer: str,
    alignment: dict,
    safe_margin: float = BLAST_TM_SAFE_MARGIN,
    critical_margin: float = BLAST_TM_CRITICAL_MARGIN,
) -> tuple[str, str]:
    """
    Return (risk_level, reason) for one BLAST hit after NW realignment.
    risk_level: 'SAFE' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

    Gates, in order:

    1. 3'-anchoring gate: off-target priming requires the primer's 3' terminus to
       anneal so the polymerase can extend. BLAST reports only the local alignment,
       so `three_prime_dangling` (primer 3' nt left OUTSIDE the alignment) tells us
       whether the 3' end is annealed: ≥2 dangling → SAFE. The synthetic 5' tail of
       a forward primer legitimately does NOT align to the miRNA, so a 5' overhang
       is expected and is not penalised. This gate comes first because a whole-
       duplex Tm cannot see whether the 3' end is paired.

    2. Duplex-Tm gate — when alignment carries `tm_offtarget` and `tm_ontarget`
       (duplex Tm of the primer on the off-target and on its own target, same
       salt conditions). The reference is Tm_on, not Ta: the specific region binds
       at ~45 °C by design and the tail lifts the Tm only after cycle 1, a route an
       off-target shares. By Primer3's convention its *_TH limits (absolute Tm)
       sit 10 °C below PRIMER_MIN_TM; offsetting from Tm_on is this tool's choice.
         Tm_off < Tm_on − safe_margin       → SAFE
         Tm_off ≥ Tm_on − critical_margin   → CRITICAL; HIGH if the 3'-terminal
                                              base is unpaired or BLOCKING [Kwok90]
         otherwise (grey zone)              → rules below, capped at MEDIUM

    3. Ye12/Kwok90 rules (see _mismatch_rules). Without Tm data they apply
       uncapped, together with the legacy 10-nt minimum anchor.
    """
    dangling3 = alignment.get("three_prime_dangling", 0)

    # 3'-anchoring gate — the strongest determinant of off-target priming.
    if dangling3 >= BLAST_3PRIME_DANGLE_SAFE:
        return "SAFE", (
            f"primer 3′ end ({dangling3} nt) does not anneal to this target — "
            f"the polymerase cannot extend, so no off-target product [Ye12]"
        )

    tm_off = alignment.get("tm_offtarget")
    tm_on  = alignment.get("tm_ontarget")
    has_tm = tm_off is not None and tm_on is not None
    if has_tm:
        gap = tm_on - tm_off
        rel = f"{gap:.1f} °C below" if gap >= 0 else f"{-gap:.1f} °C above"
        tm_text = f"duplex Tm {tm_off:.1f} °C vs {tm_on:.1f} °C on target ({rel})"
        tm_safe = gap > safe_margin
        safe_reason = (
            f"{tm_text} — more than {safe_margin:g} °C weaker than the intended "
            f"target, so it barely anneals when the target does [Primer3 *_TH]"
        )

    # Adjacent mismatches at the last two positions: extension is dramatically
    # reduced, except that a mismatched 3'-terminal T still allows significant
    # amplification even next to another mismatch [Kwok90 abstract].
    p3_base = alignment["primer_3prime_base"]
    if dangling3 == 0 and _terminal_double_mismatch(alignment):
        if p3_base != "T":
            return "SAFE", (
                "last two primer 3′ bases both mismatched — extension dramatically "
                "reduced [Kwok90]"
            )
        if has_tm and tm_safe:
            return "SAFE", safe_reason
        return "MEDIUM", (
            "last two primer 3′ bases mismatched, but the terminal base is T — Kwok "
            "1990 still saw significant amplification [Kwok90]"
        )

    if not has_tm:
        return _mismatch_rules(primer, alignment, legacy_anchor=True)
    if tm_safe:
        return "SAFE", safe_reason
    if gap <= critical_margin:
        if dangling3 == 1:
            return "HIGH", (
                f"{tm_text} — binds almost as well as the target, but the primer's "
                f"3′-terminal base overhangs the off-target's end (unpaired), which "
                f"reduces extension [Kwok90]"
            )
        pair = f"{p3_base}:{alignment['template_3prime_base']}"
        terminal = classify_3prime_mismatch(p3_base, alignment["template_3prime_base"])
        if terminal in ("BLOCKING", "REDUCING"):
            yield_text = "~1%" if terminal == "BLOCKING" else "~5%"
            return "HIGH", (
                f"{tm_text} — binds almost as well as the target; the 3′-terminal "
                f"{pair} mismatch is {terminal} ({yield_text} yield) but the duplex "
                f"is stable [Kwok90]"
            )
        if terminal == "TOLERANT" and pair == "G:G":
            return "HIGH", (
                f"{tm_text} — binds almost as well as the target; the 3′-terminal "
                f"G:G mismatch amplifies, but its yield depends on sequence context "
                f"and dNTP concentration [Kwok90]"
            )
        if terminal == "TOLERANT":
            return "CRITICAL", (
                f"{tm_text} — within {critical_margin:g} °C of the intended target; "
                f"the 3′-terminal {pair} mismatch is efficiently extended [Kwok90]: "
                f"likely co-amplified"
            )
        return "CRITICAL", (
            f"{tm_text} — within {critical_margin:g} °C of the intended target and "
            f"3′ end annealed: likely co-amplified"
        )

    risk, reason = _mismatch_rules(primer, alignment, legacy_anchor=False)
    if risk in ("CRITICAL", "HIGH"):
        return "MEDIUM", (
            f"{reason}; capped at MEDIUM — {tm_text}, "
            f"{critical_margin:g}–{safe_margin:g} °C weaker than the target"
        )
    return risk, reason


def _terminal_double_mismatch(alignment: dict) -> bool:
    """True when the last two alignment columns (primer 3' end) are both mismatches."""
    n_cols = alignment.get("aln_cols")
    if not n_cols or n_cols < 2:
        return False
    mm = set(alignment.get("mismatch_positions") or ())
    return (n_cols - 1) in mm and (n_cols - 2) in mm


def _mismatch_rules(primer: str, alignment: dict, legacy_anchor: bool) -> tuple[str, str]:
    """
    Mismatch-count rules for a hit whose 3' end is (nearly) annealed.

    =1 dangling 3' nt → 3'-terminal base unpaired → MEDIUM (capped)
    1. [Ye12] ≥6 total mismatches → SAFE (ignore threshold)
    2. [Kwok90] BLOCKING 3'-terminal (A:G, G:A, C:C) → SAFE (~1% PCR yield)
    3. 3' terminal MATCH + ≤2 total mm → CRITICAL
    4. 3' terminal MATCH + ≤4 total mm → HIGH
    5. 3' terminal MATCH + 5 mm → MEDIUM
    6. [Kwok90] REDUCING (A:A) + ≥2 total mm → MEDIUM; else HIGH
    7. [Kwok90] TOLERANT + ≥2 mm in 3' window → MEDIUM; else HIGH

    legacy_anchor: also apply the 10-nt minimum anchor (only when no duplex Tm is
    available — the Tm gate supersedes it).
    """
    total_mm = alignment["mismatches"]
    dangling3 = alignment.get("three_prime_dangling", 0)

    # Rule 1: Ye12 ignore threshold
    if total_mm >= PRIMER_BLAST_IGNORE_ABOVE_MISMATCHES:
        return "SAFE", f"≥{PRIMER_BLAST_IGNORE_ABOVE_MISMATCHES} total mismatches — off-target PCR very unlikely [Ye12]"

    # A single dangling 3' base means the true 3'-terminal base is unpaired (a 3'
    # overhang, or a mismatch BLAST trimmed off the end): extension is reduced.
    if dangling3 == 1:
        return "MEDIUM", (
            "primer 3′-terminal base is unpaired (3′ overhang or mismatch) — "
            "extension substantially reduced [Kwok90]"
        )

    # 3' end is annealed (dangling3 == 0): the aligned fragment ends exactly at the
    # primer 3' terminus, so its last columns ARE the 3' window. Count 3'-window
    # mismatches relative to the alignment columns, not the full primer length (the
    # 5' tail may legitimately be unaligned).
    mm_positions = alignment["mismatch_positions"]
    n_cols = alignment.get("aln_cols") or len(primer)
    mm_in_3prime = sum(1 for pos in mm_positions if pos >= n_cols - PRIMER_BLAST_3PRIME_WINDOW)

    # Even a perfect 3' anchor is inert if too short to anneal at the annealing temp.
    if legacy_anchor and n_cols < PRIMER_BLAST_MIN_3PRIME_ANCHOR:
        return "SAFE", (
            f"3′-anchored match is only {n_cols} nt — its duplex Tm is far below the "
            f"qPCR annealing temperature, so it cannot seed extension [Ye12]"
        )

    terminal_cat = classify_3prime_mismatch(
        alignment["primer_3prime_base"],
        alignment["template_3prime_base"],
    )

    # Rule 2: BLOCKING
    if terminal_cat == "BLOCKING":
        return "SAFE", f"3'-terminal mismatch ({alignment['primer_3prime_base']}:{alignment['template_3prime_base']}) is BLOCKING (~1% PCR yield) [Kwok90]"

    if terminal_cat == "MATCH":
        if total_mm <= 2:   return "CRITICAL", f"3' terminal matches, only {total_mm} total mismatch(es) — high off-target risk"
        if total_mm <= 4:   return "HIGH",     f"3' terminal matches, {total_mm} mismatches — moderate off-target risk"
        return "MEDIUM",    f"3' terminal matches, {total_mm} mismatches — low-moderate risk"

    if terminal_cat == "REDUCING":
        if total_mm >= PRIMER_BLAST_MIN_TOTAL_MISMATCHES:
            return "MEDIUM", f"3'-terminal A:A mismatch (~5% yield), {total_mm} total mismatches [Kwok90]"
        return "HIGH", f"3'-terminal A:A mismatch (~5% yield), only {total_mm} total mismatch — risk elevated"

    # TOLERANT
    if mm_in_3prime >= PRIMER_BLAST_3PRIME_MIN_MISMATCHES:
        return "MEDIUM", f"Tolerant 3'-terminal but {mm_in_3prime} mismatches in last {PRIMER_BLAST_3PRIME_WINDOW}-nt window — reduced efficiency [Ye12]"
    return "HIGH", f"Tolerant 3'-terminal ({terminal_cat}), mismatches only in 5' region — 3' end may extend [Kwok90]"


# ── BLAST runner ──────────────────────────────────────────────────

def run_blastn(primer: str, db_path: str, timeout: int = 60) -> list[dict]:
    """
    Run blastn for a single primer vs one database.
    Returns list of raw hit dicts (outfmt 6 fields).
    Raises subprocess.CalledProcessError or subprocess.TimeoutExpired on failure.
    """
    env, db_name = _blast_env_and_name(db_path)
    # The query goes in on stdin (blastn's default -query is "-"): no temp file,
    # so no file path that could contain spaces.
    result = subprocess.run(
        [
            "blastn",
            "-db",             db_name,
            "-task",           BLAST_TASK,
            "-word_size",      str(BLAST_WORD_SIZE),
            "-evalue",         str(BLAST_EVALUE_CUTOFF),
            "-max_target_seqs", str(BLAST_MAX_TARGET_SEQS),
            "-reward",         str(BLAST_REWARD),
            "-penalty",        str(BLAST_PENALTY),
            "-outfmt",         "6 sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore sseq qseq",
        ],
        input=f">query\n{primer}\n",
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
        env=env,
    )
    return _parse_blastn_outfmt6(result.stdout)


def fetch_sequences(ids: list[str], db_path: str, timeout: int = 60) -> dict[str, str]:
    """Full mature sequences (DNA alphabet) for miRBase ids, via blastdbcmd.

    BLAST's outfmt 6 only returns the aligned fragment; the duplex-Tm gate needs the
    whole off-target miRNA. Unknown ids are simply absent from the result —
    blastdbcmd exits non-zero when any id is missing but still prints the rest.
    """
    wanted = sorted({i for i in ids if i})
    if not wanted:
        return {}
    env, db_name = _blast_env_and_name(db_path)
    result = subprocess.run(
        ["blastdbcmd", "-db", db_name, "-entry_batch", "-", "-outfmt", "%a\t%s"],
        input="\n".join(wanted) + "\n",
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    seqs = {}
    for line in result.stdout.splitlines():
        acc, _, seq = line.partition("\t")
        if acc and seq:
            seqs[acc.strip()] = rna_to_dna(seq.strip()).upper()
    # Match case-insensitively: blastdbcmd echoes ids as stored in the DB.
    by_lower = {k.lower(): v for k, v in seqs.items()}
    return {i: by_lower[i.lower()] for i in wanted if i.lower() in by_lower}


def duplex_tm(primer: str, target_mature: str, p3: dict) -> float:
    """Tm (°C) of the primer annealed to the cDNA of a mature miRNA.

    The forward primer has the miRNA's sense sequence, so it anneals to the
    first-strand cDNA = reverse complement of the miRNA. Same NN engine and salt
    conditions (primer3 calc_heterodimer: SantaLucia 1998 + von Ahsen 2001 Mg²⁺)
    as the design itself, so Tm_off and Tm_on are directly comparable.
    """
    template = reverse_complement(rna_to_dna(target_mature).upper())
    r = primer3.calc_heterodimer(primer.upper(), template, **{k: p3[k] for k in _P3_KEYS})
    return round(float(r.tm), 1)


def _parse_blastn_outfmt6(output: str) -> list[dict]:
    fields = ["subject_id", "identity_pct", "length", "mismatches", "gap_opens",
              "q_start", "q_end", "s_start", "s_end", "evalue", "bitscore",
              "subject_seq", "query_seq"]
    hits = []
    for line in output.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < len(fields):
            continue
        hit = {}
        for key, val in zip(fields, parts):
            if key in ("identity_pct", "evalue", "bitscore"):
                hit[key] = float(val)
            elif key in ("length", "mismatches", "gap_opens", "q_start", "q_end", "s_start", "s_end"):
                hit[key] = int(val)
            else:
                hit[key] = val
        hits.append(hit)
    return hits


# ── Full off-target check ─────────────────────────────────────────

def resolve_p3_conditions(conditions: Optional[dict]) -> dict:
    """primer3 salt/oligo conditions for the Tm gate.

    `conditions` is the design's metadata.design_settings.effective_p3 (already in
    primer3 units). Missing keys fall back to the design defaults, so a BLAST run
    without conditions uses exactly what a default design would.
    """
    p3 = _get_p3_params({})
    for k in _P3_KEYS:
        v = (conditions or {}).get(k)
        if v is not None:
            p3[k] = float(v)
    return p3


def check_offtarget(
    forward_primer: str,
    reverse_primer: str,
    mirna_id: Optional[str] = None,
    timeout: int = 60,
    target_sequence: Optional[str] = None,
    conditions: Optional[dict] = None,
    safe_margin: float = BLAST_TM_SAFE_MARGIN,
    critical_margin: float = BLAST_TM_CRITICAL_MARGIN,
    species: Optional[str] = None,
) -> dict:
    """
    Run BLAST for forward + reverse primers against the miRBase database.
    NW realign each hit. Classify risk. Return structured result.

    mirna_id: target name; hits with the same name (and, when sequences are
        known, a compatible sequence) are skipped as self-hits.
    target_sequence: mature sequence of the intended target — for the forward
        primer's on-target duplex Tm and for sequence-based self/identity checks.
        Looked up in the DB by mirna_id if omitted; if neither resolves, the Tm
        gate is skipped (legacy rules apply) and self-hits go by name only.
    conditions: primer3 conditions (mv_conc, dv_conc, dntp_conc, dna_conc) — pass
        the design's effective_p3 so Tm_on/Tm_off match the design's own Tm.
    species: miRBase species code ('hsa', 'ssc', …); defaults to mirna_id's prefix.
    """
    db_available = [_MIRBASE_DB] if _db_exists(_MIRBASE_DB) else []
    if not db_available:
        raise FileNotFoundError(
            f"BLAST database not found at {_MIRBASE_DB!r}. "
            "Run 'python scripts/build_blast_db.py' to build it first."
        )

    if species and not re.fullmatch(r"[A-Za-z]{3}", species):
        raise ValueError(f"species must be a 3-letter miRBase code, got {species!r}")
    species_prefix = f"{species.lower()}-" if species else _extract_species_prefix(mirna_id)
    # Pre-compute once; passed into every _is_self_hit call to avoid per-hit recomputation
    m_norm = _normalize_mirna_name(mirna_id.lower()) if mirna_id else None
    # Seed-family of the target — used to fold same-family hits into one bucket (Fix B)
    target_family = get_family_id(mirna_id) if mirna_id else None

    # On-target reference for the forward primer's duplex-Tm gate.
    p3 = resolve_p3_conditions(conditions)
    target_source = "request" if target_sequence else None
    if not target_sequence and mirna_id:
        target_sequence = fetch_sequences([mirna_id], _MIRBASE_DB, timeout).get(mirna_id)
        target_source = "mirbase_db" if target_sequence else None
    if target_sequence:
        target_sequence = rna_to_dna(target_sequence).upper()
    tm_on = duplex_tm(forward_primer, target_sequence, p3) if target_sequence else None
    margins = (safe_margin, critical_margin)

    # The fixed universal reverse primer anneals to the stem-loop body the RT primer
    # introduces, not to any miRNA, so a miRBase search says nothing about it — and
    # it would be the same for every design. Only a custom reverse primer is checked.
    skip_reverse = bool(reverse_primer) and reverse_primer.upper() == UNIVERSAL_REVERSE
    check_reverse = bool(reverse_primer) and not skip_reverse

    # Run forward and reverse BLAST concurrently — they are fully independent.
    # The Tm gate applies to the forward primer only: a reverse primer has no
    # miRNA on-target to compare against.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        fwd_future = pool.submit(_check_primer, forward_primer, db_available, mirna_id, m_norm, species_prefix, timeout, target_family, tm_on, p3, margins, target_sequence)
        rev_future = pool.submit(_check_primer, reverse_primer, db_available, mirna_id, m_norm, species_prefix, timeout, target_family) if check_reverse else None
        fwd_hits, fwd_safe, fwd_cs, fwd_fam, fwd_ident = fwd_future.result()
        rev_hits, rev_safe, rev_cs, rev_fam, _ = rev_future.result() if rev_future else ([], 0, 0, 0, [])

    summary = _summarise(fwd_hits + rev_hits, fwd_safe + rev_safe, fwd_cs + rev_cs,
                         fwd_fam + rev_fam, len(fwd_ident))
    summary["hits_truncated"] = (
        len(fwd_hits) == BLAST_MAX_HITS_RETURNED or len(rev_hits) == BLAST_MAX_HITS_RETURNED
    )

    return {
        "forward_primer_hits": fwd_hits,
        "reverse_primer_hits": rev_hits,
        # Other names carrying the target's mature sequence (identical, or ends shifted
        # ≤2 nt): indistinguishable by the forward primer, so not risk-classified.
        "identical_sequence_hits": fwd_ident,
        "reverse_primer_skipped": (
            "Universal reverse primer anneals to the stem-loop body, not to a miRNA — "
            "a miRBase search does not apply." if skip_reverse else None
        ),
        "summary": summary,
        "classification": {
            "classifier_version": BLAST_CLASSIFIER_VERSION,
            "tm_gate_applied": tm_on is not None,
            "tm_ontarget": tm_on,
            "target_sequence_source": target_source,
            "species": species_prefix.rstrip("-"),
            "safe_margin_c": safe_margin,
            "critical_margin_c": critical_margin,
            "conditions": p3,
        },
    }


def _check_primer(
    primer: str,
    db_paths: list[str],
    mirna_id: Optional[str],
    m_norm: Optional[str],
    species_prefix: str,
    timeout: int,
    target_family: Optional[str] = None,
    tm_on: Optional[float] = None,
    p3: Optional[dict] = None,
    margins: tuple[float, float] = (BLAST_TM_SAFE_MARGIN, BLAST_TM_CRITICAL_MARGIN),
    target_sequence: Optional[str] = None,
) -> tuple[list[dict], int, int, int, list[str]]:
    """Return (non_safe_hits, safe_count, cross_species_excluded, same_family_count,
    identical_sequence_ids).

    Self-hits are skipped. With target_sequence (DNA) known, a name match counts
    only if the hit's sequence is compatible (sequences_compatible), and any
    same-species hit under another name whose mature sequence is identical or
    compatible (ends shifted ≤2 nt) — multi-locus copies such as ath-miR156a…f, or
    renamed entries such as ssc-miR-20 → ssc-miR-20a-5p — is listed in
    identical_sequence_ids instead of being risk-classified: the forward primer
    cannot tell them apart, so the assay measures their sum.

    SAFE hits (3' end not annealed, or ≥6 mm) are counted but not included in the
    hit list. Cross-species miRBase hits (not matching species_prefix) are excluded
    entirely — biologically irrelevant for same-species qPCR and would otherwise
    dominate the hit cap with conserved miRNA orthologs from other organisms.

    same_family_count (Fix B): hits that are the target miRNA's own seed-family
    members are the EXPECTED, already-surfaced cross-reactivity case (see the
    Family Cross-reactivity panel). They are folded into one aggregated count
    instead of listed as separate critical off-targets, so the real out-of-family
    signal is not drowned. target_family is the seed-family id of mirna_id (or None).

    tm_on: on-target duplex Tm; when set, each 3'-anchored hit gets its own
    duplex Tm (full off-target sequence from the DB) and the Tm gate applies.
    """
    non_safe_hits: list[dict] = []
    safe_count = 0
    cross_species_excluded = 0
    same_family_count = 0
    identical: set[str] = set()
    primer_len = len(primer)
    for db in db_paths:
        is_mirbase = os.path.basename(db).startswith("mirbase")
        try:
            raw = run_blastn(primer, db, timeout=timeout)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            raise   # caller (route) handles circuit breaker

        def same_species(sid: str) -> bool:
            return not is_mirbase or sid.lower().startswith(species_prefix)

        # Full sequences of same-species hits: for self/identity checks (needs every
        # such hit) and the Tm gate (only 3'-anchored ones reach it).
        subject_seqs = {}
        if target_sequence or tm_on is not None:
            subject_seqs = fetch_sequences(
                [h["subject_id"] for h in raw if same_species(h["subject_id"])], db, timeout,
            )
        for h in raw:
            sid = h["subject_id"]
            subject_full = subject_seqs.get(sid)
            # Self-hit by name (incl. precursor copies, e.g. hsa-miR-16-1-5p), confirmed
            # by sequence when both are known: a renamed entry with a different
            # sequence (miRBase 22.1 ssc-miR-670) is a real off-target.
            if mirna_id and _is_self_hit(sid, mirna_id, m_norm):
                if not (target_sequence and subject_full) or sequences_compatible(
                        subject_full, target_sequence):
                    continue
            # Same mature molecule under another name — an identical copy from another
            # locus, or the same sequence annotated with ends shifted ≤2 nt (renamed
            # entries such as ssc-miR-20 → ssc-miR-20a-5p): indistinguishable by the
            # forward primer, so listed rather than risk-classified.
            if target_sequence and subject_full and sequences_compatible(
                    subject_full, target_sequence):
                identical.add(sid)
                continue
            # miRBase DB: skip other-species orthologs — same conserved sequence,
            # different organism → irrelevant for same-species assay
            if not same_species(sid):
                cross_species_excluded += 1
                continue

            # How much of the primer's 3'/5' end lies OUTSIDE the BLAST local
            # alignment. q_start/q_end are 1-based query (primer) coordinates.
            q_start = h.get("q_start")
            q_end   = h.get("q_end")
            dangling3 = max(primer_len - q_end, 0) if isinstance(q_end, int) else 0
            dangling5 = max(q_start - 1, 0) if isinstance(q_start, int) else 0

            # NW global realign of the matched fragment — more accurate than BLAST local
            subject_seq = h.get("subject_seq", "")
            query_seq   = h.get("query_seq", "")

            # A local alignment never ends on a mismatch, so a mismatched 3'-terminal
            # base is trimmed off and shows up as "dangling". On a plus-strand hit
            # (primer = off-target sense, i.e. it anneals to the off-target's cDNA)
            # the full subject gives the bases really opposite those primer positions:
            # put them back so the Kwok rules see the true terminal pair [Ye12 Fig.5].
            # Only bases past the end of the off-target stay dangling.
            plus = (isinstance(h.get("s_start"), int) and isinstance(h.get("s_end"), int)
                    and h["s_end"] >= h["s_start"])
            tm_window = subject_full
            if subject_full and plus:
                ext = subject_full[h["s_end"]: h["s_end"] + dangling3]
                # Duplex Tm only where the primer sits in this register (+1 base
                # downstream for thal's dangling-end term — on the target that gives
                # exactly the full-sequence Tm_on): a stronger duplex elsewhere on the
                # off-target cannot extend from this 3' end.
                lo = max(h["s_start"] - 1 - dangling5, 0)
                tm_window = subject_full[lo: h["s_end"] + dangling3 + 1]
                if ext and subject_seq and query_seq:
                    subject_seq += ext
                    query_seq += primer[q_end: q_end + len(ext)]
                    dangling3 -= len(ext)
            if subject_seq and query_seq:
                aln = nw_align(query_seq.replace("-", ""), subject_seq.replace("-", ""))
            else:
                aln = {
                    "mismatches": h["mismatches"],
                    "mismatch_positions": [],
                    "primer_3prime_base": primer[-1].upper(),
                    "template_3prime_base": "N",
                    "coverage_pct": round(h["length"] / primer_len * 100, 1),
                    "aln_cols": h["length"],
                }
            # Anchoring info drives classify_hit_risk's 3'-end gate.
            aln["three_prime_dangling"] = dangling3
            aln["five_prime_dangling"]  = dangling5
            if tm_on is not None and subject_full:
                aln["tm_ontarget"]  = tm_on
                aln["tm_offtarget"] = duplex_tm(primer, tm_window, p3)

            risk, reason = classify_hit_risk(primer, aln, *margins)
            # SAFE hits are counted in summary but omitted from hit list [Ye12]
            if risk == "SAFE":
                safe_count += 1
                continue
            # Fix B: fold same-seed-family members into one aggregated count.
            if target_family is not None:
                subj_family = get_family_id(h["subject_id"])
                if subj_family is not None and subj_family == target_family:
                    same_family_count += 1
                    continue
            non_safe_hits.append({
                "subject_id":   h["subject_id"],
                "database":     os.path.basename(db),
                "alignment": {
                    "identity_pct":        h["identity_pct"],
                    "coverage_pct":        aln.get("coverage_pct", 100.0),
                    "mismatches":          aln["mismatches"],
                    "mismatch_positions":  aln["mismatch_positions"],
                    "primer_3prime_base":  aln["primer_3prime_base"],
                    "template_3prime_base": aln["template_3prime_base"],
                    "three_prime_dangling": dangling3,
                    "terminal_category":   classify_3prime_mismatch(
                        aln["primer_3prime_base"], aln["template_3prime_base"]
                    ),
                    "tm_offtarget":        aln.get("tm_offtarget"),
                    "tm_ontarget":         aln.get("tm_ontarget"),
                },
                "evalue": h["evalue"],
                "risk":   risk,
                "risk_reason": reason,
            })
    # Sort by risk severity then evalue, cap at BLAST_MAX_HITS_RETURNED
    non_safe_hits.sort(key=lambda h: (_RISK_ORDER.get(h["risk"], 9), h["evalue"]))
    return (non_safe_hits[:BLAST_MAX_HITS_RETURNED], safe_count, cross_species_excluded,
            same_family_count, sorted(identical))


def _summarise(
    non_safe_hits: list[dict],
    safe_count: int = 0,
    cross_species_excluded: int = 0,
    same_family_count: int = 0,
    identical_sequence_count: int = 0,
) -> dict:
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0}
    for h in non_safe_hits:
        risk = h.get("risk", "MEDIUM")
        counts[risk] = counts.get(risk, 0) + 1
    # overall_risk reflects OUT-of-family off-targets only — same-family cross-
    # reactivity is expected and surfaced separately (see same_family_count), and
    # identical-sequence copies cannot be discriminated by any primer.
    if counts["CRITICAL"] > 0:    overall = "CRITICAL"
    elif counts["HIGH"] > 0:      overall = "HIGH"
    elif counts["MEDIUM"] > 0:    overall = "MEDIUM"
    else:                          overall = "SAFE"
    return {
        "total_hits":              (len(non_safe_hits) + safe_count + same_family_count
                                    + identical_sequence_count),
        "critical_count":          counts["CRITICAL"],
        "high_risk_count":         counts["HIGH"],
        "medium_risk_count":       counts["MEDIUM"],
        "safe_count":              safe_count,
        "cross_species_excluded":  cross_species_excluded,
        "same_family_count":       same_family_count,
        "identical_sequence_count": identical_sequence_count,
        "overall_risk":            overall,
    }


def _normalize_mirna_name(name: str) -> str:
    """
    Strip precursor-copy number so precursor variants of the same mature miRNA
    are treated as self-hits.

    miRBase assigns identical mature sequences to multiple precursor genes and
    may list them as separate FASTA entries:
      hsa-miR-16-1-5p  (from hsa-mir-16-1)
      hsa-miR-16-2-5p  (from hsa-mir-16-2)
    Both are the same mature miRNA as hsa-miR-16-5p.

    Strategy: split on '-', then strip the second-to-last component if it is
    exactly '1' or '2' AND there are at least 5 components total. The ≥5
    guard prevents stripping the miRNA name number itself for short names such
    as hsa-miR-1-5p (4 components → unchanged).

    Examples:
      hsa-miR-16-1-5p  → hsa-mir-16-5p   (5 parts, drops '1')
      hsa-miR-16-2-5p  → hsa-mir-16-5p   (5 parts, drops '2')
      hsa-miR-16-5p    → hsa-mir-16-5p   (4 parts → unchanged)
      hsa-miR-1-5p     → hsa-mir-1-5p    (4 parts → unchanged)
      hsa-let-7a-1-5p  → hsa-let-7a-5p  (5 parts, drops '1')
      hsa-miR-92a-2-5p → hsa-mir-92a-5p (5 parts, drops '2')
    """
    parts = name.strip().lower().split('-')
    if (len(parts) >= 5
            and re.fullmatch(r'[35]p', parts[-1])
            and re.fullmatch(r'\d+', parts[-2])):
        parts.pop(-2)
    return '-'.join(parts)


def _is_self_hit(subject_id: str, mirna_id: str, m_norm: Optional[str] = None) -> bool:
    """
    Return True if the hit's NAME denotes the target miRNA. Handles precursor
    variants via _normalize_mirna_name.

    Names match when equal, or when one extends the other at a '-' boundary
    ('hsa-mir-16' ↔ 'hsa-mir-16-5p'; 'ssc-mir-21' ↔ 'ssc-mir-21-5p'). A plain
    substring test is NOT used: it made 'ssc-mir-21' match 'ssc-mir-210', hiding
    a real off-target. An arm-less id also matches the other arm ('-3p'), so
    callers that know the sequences confirm with sequences_compatible().

    m_norm: pre-computed _normalize_mirna_name(mirna_id.lower()) — pass from
    caller to avoid recomputing it for every hit in the loop.
    """
    s_norm = _normalize_mirna_name(subject_id)
    if m_norm is None:
        m_norm = _normalize_mirna_name(mirna_id)
    short, long_ = sorted((s_norm, m_norm), key=len)
    return long_ == short or long_.startswith(short + "-")


def sequences_compatible(a: str, b: str,
                         max_shift: int = SELF_MAX_END_SHIFT,
                         min_overlap: int = SELF_MIN_OVERLAP) -> bool:
    """Same mature miRNA under two annotations: identical over their overlap, with
    each end differing by at most max_shift nt (e.g. miRBase 22.1 mmu-miR-138-5p
    AGCTGG… vs the CAGCTGG… a 2014 paper designed against). A renamed entry whose
    sequence changed entirely (ssc-miR-670) is not compatible.
    """
    a, b = a.upper(), b.upper()
    for k in range(-max_shift, max_shift + 1):      # b[j] pairs with a[j + k]
        a0, b0 = max(k, 0), max(-k, 0)
        n = min(len(a) - a0, len(b) - b0)
        if n < min_overlap:
            continue
        if (len(a) - a0 - n <= max_shift and len(b) - b0 - n <= max_shift
                and a[a0:a0 + n] == b[b0:b0 + n]):
            return True
    return False


def _extract_species_prefix(mirna_id: Optional[str]) -> str:
    """
    Extract 3-letter miRBase species prefix from a miRNA ID.
    'hsa-miR-21-5p' → 'hsa-', 'mmu-let-7a' → 'mmu-'.
    Falls back to MIRBASE_HUMAN_PREFIX when no prefix is detected.
    """
    if mirna_id:
        m = re.match(r'^([a-z]{3})-', mirna_id.lower())
        if m:
            return m.group(1) + "-"
    return MIRBASE_HUMAN_PREFIX


def _db_exists(db_path: str) -> bool:
    """Check if BLAST db files exist (any of .nhr/.nin/.nsq extensions)."""
    return any(
        os.path.exists(db_path + ext)
        for ext in (".nhr", ".nin", ".nsq", ".nal")
    )
