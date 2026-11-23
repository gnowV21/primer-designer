# ================================================================
# utils/report_text.py — labels and number/symbol formatting shared by the
# PDF and CSV exports (routes/export.py, routes/report_pdf.py).
#
# Presentation only: nothing here feeds the design, the scoring or the ranking.
# Conventions (UI/PDF review 2026-11-23):
#   temperature  "60.0 °C"   space before °C, Tm with 1 decimal
#   percent      "47.6%"     no space, 1 decimal
#   ΔG           "−6.10"     2 decimals, true minus U+2212 (prose only; numeric CSV
#                            columns keep the ASCII hyphen so spreadsheets parse them)
#   prime        5′ 3′       U+2032, never ' or ´
#   ranges       "58–62 °C"  en dash
# ================================================================

from __future__ import annotations

import re

MINUS = "\u2212"
PRIME = "\u2032"

# Standard primer rules a tiered set can break (`v4_rule_violations`, the V4 hard
# filters). One map for PDF, CSV and (mirrored) frontend/src/utils/v4Rules.js.
RULE_LABELS = {
    "gc_out_of_range":            "GC content outside the GC window",
    "gc_clamp_fail":              "3′ GC clamp missing",
    "gc_end_window_fail":         "3′ end too GC-rich (last 5 nt all G/C)",
    "hard_dimer_full_dg":         "Strong primer dimer (ΔG < −9 kcal/mol)",
    "hard_dimer_3prime_critical": "3′-end dimer Tm ≥ 47 °C",
    "hard_hairpin_tm":            "Hairpin Tm ≥ 47 °C",
}


def rule_label(code: str) -> str:
    return RULE_LABELS.get(code, str(code).replace("_", " "))


def rule_labels(codes) -> str:
    """Readable, comma-separated labels of rule codes; 'None' when empty."""
    codes = list(codes or [])
    return ", ".join(rule_label(c) for c in codes) if codes else "None"


# ── Numbers ───────────────────────────────────────────────────────

def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def signed(text: str) -> str:
    """ASCII hyphen-minus before a digit → true minus sign."""
    return re.sub(r"(?<![\w.])-(?=\d)", MINUS, text)


def fmt_tm(v, unit: bool = True) -> str:
    x = _num(v)
    if x is None:
        return "—"
    s = signed(f"{x:.1f}")
    return f"{s}\u00a0°C" if unit else s


def fmt_temp(v) -> str:
    """A set temperature (Ta): integer when whole, else 1 decimal, with °C."""
    x = _num(v)
    if x is None:
        return "—"
    s = f"{x:.0f}" if x == int(x) else f"{x:.1f}"
    return f"{signed(s)}\u00a0°C"


def fmt_pct(v, decimals: int = 1) -> str:
    x = _num(v)
    if x is None:
        return "—"
    return f"{signed(f'{x:.{decimals}f}')}%"


def fmt_dg(v) -> str:
    """ΔG with 2 decimals and a true minus sign (no unit; the label carries it)."""
    x = _num(v)
    if x is None:
        return "—"
    return signed(f"{x:.2f}")


def fmt_range(pair, unit: str = "") -> str:
    """[lo, hi] → '58–62 °C' / '40–60%'."""
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        return "—"
    lo, hi = pair
    if lo is None and hi is None:
        return "—"
    body = f"{lo}" if lo == hi else f"{lo}–{hi}"
    if not unit:
        return body
    return f"{body}%" if unit == "%" else f"{body}\u00a0{unit}"


# ── Text ──────────────────────────────────────────────────────────

_TEXT_FIXES = [
    (re.compile(r"(?<=[35])['´’](?=[\s\-–→,.;:)]|$)"), PRIME),   # 5' 3' → 5′ 3′
    (re.compile(r"\bMg2\+"), "Mg²⁺"),
    (re.compile(r"\bNa\+"), "Na⁺"),
    (re.compile(r"\bK\+"), "K⁺"),
    (re.compile(r"\bR2\b"), "R²"),
    (re.compile(r"byte-identical"), "identical"),
    (re.compile(r"\bspecific_length\b"), "forward-primer specific length"),
    (re.compile(r"(\d)\s+%"), r"\1%"),                            # "81 %" → "81%"
    (re.compile(r"(\d)°C"), "\\1\u00a0°C"),                       # "60°C" → "60 °C"
    (re.compile(r"(\d) °C"), "\\1\u00a0°C"),
]


def clean(text) -> str:
    """Apply the symbol conventions to a free-text message (warnings, notes)."""
    s = str(text or "")
    for rx, rep in _TEXT_FIXES:
        s = rx.sub(rep, s)
    return signed(s)


def sentence(text) -> str:
    """First letter upper-case ('tissue' → 'Tissue'); acronyms left alone."""
    s = str(text or "")
    return s[:1].upper() + s[1:] if s else s


# Values the design settings carry in lower case → display words.
_SETTING_WORDS = {
    "sybr": "SYBR Green", "taqman": "TaqMan", "relative": "Relative", "absolute": "Absolute",
    "tissue": "Tissue", "cell": "Cell line", "serum": "Serum", "plasma": "Plasma",
    "ffpe": "FFPE", "urine": "Urine", "other": "Other", "abi": "Applied Biosystems",
    "biorad": "Bio-Rad CFX", "roche": "Roche LightCycler", "qiagen": "Qiagen Rotor-Gene",
    "human": "Human", "mouse": "Mouse", "rat": "Rat",
}


def setting_word(v) -> str:
    if v is None or v == "":
        return "—"
    return _SETTING_WORDS.get(str(v).lower(), sentence(str(v)))


# ── Status vocabulary: Pass / Warning / Fail ─────────────────────

_STATUS = {
    "SAFE": "Pass", "PASS": "Pass", "OK": "Pass", "DISCRIMINATED": "Pass", "NONE": "Pass",
    "LOW": "Pass",
    "MEDIUM": "Warning", "PARTIAL": "Warning", "WARNING": "Warning",
    "HIGH": "Fail", "CRITICAL": "Fail", "CO-AMPLIFIED": "Fail", "IDENTICAL": "Fail",
    "FAIL": "Fail",
}


def status(level) -> str:
    """Map an API level/label to Pass / Warning / Fail ('' when unknown)."""
    return _STATUS.get(str(level or "").upper(), "")


def level_word(level) -> str:
    """API level in sentence case: 'CO-AMPLIFIED' → 'Co-amplified', 'SAFE' → 'Safe'."""
    s = str(level or "").replace("_", " ").lower()
    return s[:1].upper() + s[1:]


def plural(n: int, noun: str, plural_noun: str | None = None) -> str:
    return f"{n} {noun if n == 1 else (plural_noun or noun + 's')}"


# ── References (one numbered list for the PDF) ────────────────────
# key → citation. Keys are what the report sections cite; the list is printed in the
# order of first citation.
REFERENCES = {
    # Short, verified forms only (identifiers as recorded in AUDIT_REPORT.md, constants.py
    # and data/protocol_kb.json); no title is given where the repository has none.
    "Chen2005": "Chen C et al. Real-time quantification of microRNAs by stem-loop RT-PCR. "
                "Nucleic Acids Res 2005;33:e179. doi:10.1093/nar/gni178",
    "Kramer2011": "Kramer MF. Stem-loop RT-qPCR for miRNAs. Curr Protoc Mol Biol 2011;Unit 15.10. "
                  "doi:10.1002/0471142727.mb1510s95",
    "VarkonyiGasic2007": "Varkonyi-Gasic E et al. Plant Methods 2007;3:12. doi:10.1186/1746-4811-3-12",
    "Czimmerer2013": "Czimmerer Z et al. PLoS One 2013;8:e55168",
    "Schamberger2014": "Schamberger A, Orbán TI. PLoS One 2014;9:e106315",
    "Stadhouders2010": "Stadhouders R et al. J Mol Diagn 2010;12:109",
    "Magee2017": "Magee R et al. Non-Coding RNA 2017;3:18",
    "Fan2019": "Fan 2019. J Biomol Struct Dyn. doi:10.1080/07391102.2018.1498804",
    "Fujimoto2018": "Fujimoto 2018. Forensic Sci Int Genet. doi:10.1016/j.fsigen.2018.08.010",
    "Liang2018": "Liang 2018 (reference-miRNA stability; cited by the Protocol Advisor knowledge base)",
    "isomiRdb": "Aparicio-Puerta E et al. isomiRdb: microRNA expression at isoform resolution. "
                "Nucleic Acids Res 2023;51(D1):D179-D185. PMID 36243964. doi:10.1093/nar/gkac884",
    "Bustin2025": "Bustin SA et al. MIQE 2.0. Clin Chem 2025;71:634-651. doi:10.1093/clinchem/hvaf043",
    "SantaLucia1998": "SantaLucia J. Proc Natl Acad Sci USA 1998;95:1460-5. doi:10.1073/pnas.95.4.1460",
    "vonAhsen2001": "von Ahsen N et al. Oligonucleotide melting temperatures under PCR conditions. "
                    "Clin Chem 2001;47:1956-61",
    "Kang2017": "Kang 2017. RNA. doi:10.1261/rna.061150.117",
    "Lagatie2017": "Lagatie 2017. doi:10.1007/s00436-017-5382-5",
    "Wang2017": "Wang 2017. Mol Med Rep. doi:10.3892/mmr.2017.8297",
}
