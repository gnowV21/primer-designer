# ================================================================
# blast_offtarget.py — BLAST off-target check (Module 10, Phase 3)
#
# Runs blastn against local miRBase + Ensembl databases, then
# re-aligns with Needleman-Wunsch global alignment (Ye 2012).
# Classifies each hit using Ye 2012 thresholds + Kwok 1990
# 3'-terminal mismatch categories.
#
# Sources:
#   [Ye12]   Ye et al. 2012 BMC Bioinformatics 13:134 (Primer-BLAST)
#   [Kwok90] Kwok et al. 1990 Nucleic Acids Research 18(4):999-1005
# ================================================================

import ctypes
import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Optional

from algorithm.constants import (
    BLAST_WORD_SIZE, BLAST_EVALUE_CUTOFF, BLAST_MAX_TARGET_SEQS,
    BLAST_REWARD, BLAST_PENALTY, BLAST_TASK,
    PRIMER_BLAST_IGNORE_ABOVE_MISMATCHES,
    PRIMER_BLAST_3PRIME_WINDOW, PRIMER_BLAST_3PRIME_MIN_MISMATCHES,
    PRIMER_BLAST_MIN_TOTAL_MISMATCHES,
    BLAST_MAX_HITS_RETURNED, MIRBASE_HUMAN_PREFIX,
    KWOK_BLOCKING_PAIRS, KWOK_REDUCING_PAIRS,
)

_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "blast_db")
_MIRBASE_DB  = os.path.join(_DB_DIR, "mirbase_multi")
_ENSEMBL_DB  = os.path.join(_DB_DIR, "ensembl_human_cdna")
_METADATA    = os.path.join(_DB_DIR, "metadata.json")


def _win_short_path(path: str) -> str:
    """Convert path with spaces to 8.3 short form on Windows (blastn rejects spaced paths)."""
    if not sys.platform.startswith("win") or " " not in path:
        return path
    try:
        if os.path.exists(path):
            buf = ctypes.create_unicode_buffer(32767)
            ctypes.windll.kernel32.GetShortPathNameW(path, buf, 32767)
            return buf.value or path
        head, tail_parts = path, []
        while head and not os.path.exists(head):
            head, part = os.path.split(head)
            tail_parts.insert(0, part)
        buf = ctypes.create_unicode_buffer(32767)
        ctypes.windll.kernel32.GetShortPathNameW(head, buf, 32767)
        return os.path.join(buf.value or head, *tail_parts)
    except Exception:
        return path


# ── 3'-terminal mismatch classification ──────────────────────────

def classify_3prime_mismatch(primer_base: str, template_base: str) -> str:
    """
    [Kwok90] Table III — 3'-terminal mismatch type by PCR yield.
    Returns 'MATCH' | 'BLOCKING' | 'REDUCING' | 'TOLERANT'.
    """
    p, t = primer_base.upper(), template_base.upper()
    if p == t:
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

    # 3'-terminal bases (last non-gap character)
    primer_3p   = next((c for c in reversed(aln1) if c != "-"), "N")
    template_3p = next((c for c in reversed(aln2) if c != "-"), "N")

    return {
        "mismatches":           len(mismatches),
        "mismatch_positions":   mismatches,
        "aligned_primer":       aln1,
        "aligned_template":     aln2,
        "primer_3prime_base":   primer_3p.upper(),
        "template_3prime_base": template_3p.upper(),
        "coverage_pct":         round(len(seq1) / max(len(aln1.replace("-", "")), 1) * 100, 1),
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
        "template_3prime_base": s2[-1].upper() if s2 else "N",
        "coverage_pct": 100.0,
    }


# ── Risk classification ───────────────────────────────────────────

def classify_hit_risk(primer: str, alignment: dict) -> tuple[str, str]:
    """
    Return (risk_level, reason) for one BLAST hit after NW realignment.
    risk_level: 'SAFE' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

    Rules:
    1. [Ye12] ≥6 total mismatches → SAFE (ignore threshold)
    2. [Kwok90] BLOCKING 3'-terminal (A:G, G:A, C:C) → SAFE (~1% PCR yield)
    3. 3' terminal MATCH + ≤2 total mm → CRITICAL
    4. 3' terminal MATCH + ≤4 total mm → HIGH
    5. 3' terminal MATCH + 5 mm → MEDIUM
    6. [Kwok90] REDUCING (A:A) + ≥2 total mm → MEDIUM; else HIGH
    7. [Kwok90] TOLERANT + ≥2 mm in 3' window → MEDIUM; else HIGH
    """
    total_mm = alignment["mismatches"]

    # Rule 1: Ye12 ignore threshold
    if total_mm >= PRIMER_BLAST_IGNORE_ABOVE_MISMATCHES:
        return "SAFE", f"≥{PRIMER_BLAST_IGNORE_ABOVE_MISMATCHES} total mismatches — off-target PCR very unlikely [Ye12]"

    primer_len = len(primer)
    mm_positions = alignment["mismatch_positions"]
    mm_in_3prime = sum(1 for pos in mm_positions if pos >= primer_len - PRIMER_BLAST_3PRIME_WINDOW)

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
    with tempfile.NamedTemporaryFile(mode="w", suffix=".fa", delete=False) as fq:
        fq.write(f">query\n{primer}\n")
        fq_path = fq.name

    try:
        result = subprocess.run(
            [
                "blastn",
                "-query",          _win_short_path(fq_path),
                "-db",             _win_short_path(db_path),
                "-task",           BLAST_TASK,
                "-word_size",      str(BLAST_WORD_SIZE),
                "-evalue",         str(BLAST_EVALUE_CUTOFF),
                "-max_target_seqs", str(BLAST_MAX_TARGET_SEQS),
                "-reward",         str(BLAST_REWARD),
                "-penalty",        str(BLAST_PENALTY),
                "-outfmt",         "6 sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore sseq qseq",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        hits = _parse_blastn_outfmt6(result.stdout)
    finally:
        os.unlink(fq_path)

    return hits


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

def check_offtarget(
    forward_primer: str,
    reverse_primer: str,
    mirna_id: Optional[str] = None,
    timeout: int = 60,
) -> dict:
    """
    Run BLAST for forward + reverse primers against both databases.
    NW realign each hit. Classify risk. Return structured result.

    mirna_id: if set, skip self-hits where subject contains this ID.
    """
    dbs = [_MIRBASE_DB, _ENSEMBL_DB]
    db_available = [d for d in dbs if _db_exists(d)]

    species_prefix = _extract_species_prefix(mirna_id)
    fwd_hits, fwd_safe, fwd_cs = _check_primer(forward_primer, db_available, mirna_id, species_prefix, timeout)
    rev_hits, rev_safe, rev_cs = _check_primer(reverse_primer, db_available, mirna_id, species_prefix, timeout) if reverse_primer else ([], 0, 0)

    summary = _summarise(fwd_hits + rev_hits, fwd_safe + rev_safe, fwd_cs + rev_cs)
    summary["hits_truncated"] = (
        len(fwd_hits) == BLAST_MAX_HITS_RETURNED or len(rev_hits) == BLAST_MAX_HITS_RETURNED
    )

    return {
        "forward_primer_hits": fwd_hits,
        "reverse_primer_hits": rev_hits,
        "summary": summary,
    }


def _check_primer(
    primer: str,
    db_paths: list[str],
    mirna_id: Optional[str],
    species_prefix: str,
    timeout: int,
) -> tuple[list[dict], int, int]:
    """Return (non_safe_hits, safe_count, cross_species_excluded).

    SAFE hits (≥6 mm) are counted but not included in the hit list.
    Cross-species miRBase hits (not matching species_prefix) are excluded entirely —
    they are biologically irrelevant for same-species qPCR and would otherwise
    dominate the hit cap with conserved miRNA orthologs from other organisms.
    species_prefix is derived from mirna_id (e.g., 'hsa-' for hsa-miR-21-5p).
    """
    non_safe_hits: list[dict] = []
    safe_count = 0
    cross_species_excluded = 0
    for db in db_paths:
        is_mirbase = os.path.basename(db).startswith("mirbase")
        try:
            raw = run_blastn(primer, db, timeout=timeout)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            raise   # caller (route) handles circuit breaker
        for h in raw:
            # Skip self-hit
            if mirna_id and mirna_id.lower() in h["subject_id"].lower():
                continue
            # miRBase DB: skip other-species orthologs — same conserved sequence,
            # different organism → irrelevant for same-species assay
            if is_mirbase and not h["subject_id"].lower().startswith(species_prefix):
                cross_species_excluded += 1
                continue
            # NW global realign — more accurate than BLAST local
            subject_seq = h.get("subject_seq", "")
            query_seq   = h.get("query_seq", "")
            if subject_seq and query_seq:
                aln = nw_align(query_seq.replace("-", ""), subject_seq.replace("-", ""))
            else:
                aln = {
                    "mismatches": h["mismatches"],
                    "mismatch_positions": [],
                    "primer_3prime_base": primer[-1].upper(),
                    "template_3prime_base": "N",
                    "coverage_pct": round(h["length"] / len(primer) * 100, 1),
                }
            risk, reason = classify_hit_risk(primer, aln)
            # SAFE hits (≥6 mm) are counted in summary but omitted from hit list [Ye12]
            if risk == "SAFE":
                safe_count += 1
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
                    "terminal_category":   classify_3prime_mismatch(
                        aln["primer_3prime_base"], aln["template_3prime_base"]
                    ),
                },
                "evalue": h["evalue"],
                "risk":   risk,
                "risk_reason": reason,
            })
    # Sort by risk severity then evalue, cap at BLAST_MAX_HITS_RETURNED
    _risk_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    non_safe_hits.sort(key=lambda h: (_risk_order.get(h["risk"], 9), h["evalue"]))
    return non_safe_hits[:BLAST_MAX_HITS_RETURNED], safe_count, cross_species_excluded


def _summarise(non_safe_hits: list[dict], safe_count: int = 0, cross_species_excluded: int = 0) -> dict:
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0}
    for h in non_safe_hits:
        risk = h.get("risk", "MEDIUM")
        counts[risk] = counts.get(risk, 0) + 1
    if counts["CRITICAL"] > 0:    overall = "CRITICAL"
    elif counts["HIGH"] > 0:      overall = "HIGH"
    elif counts["MEDIUM"] > 0:    overall = "MEDIUM"
    else:                          overall = "SAFE"
    return {
        "total_hits":              len(non_safe_hits) + safe_count,
        "critical_count":          counts["CRITICAL"],
        "high_risk_count":         counts["HIGH"],
        "medium_risk_count":       counts["MEDIUM"],
        "safe_count":              safe_count,
        "cross_species_excluded":  cross_species_excluded,
        "overall_risk":            overall,
    }


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
