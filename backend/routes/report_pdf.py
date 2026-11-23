# ================================================================
# routes/report_pdf.py — the PDF primer report (POST /api/export, format "pdf").
#
# Presentation only: reads the /api/design result as it is; no value is recomputed
# and nothing here feeds the design, scoring or ranking.
#
# Layout (UI/PDF review 2026-11-23, docs/REVIEW_ui_polish_2026-11.md):
#   page 1   ready to order: title, miRNA, the 3 primers, specificity verdict,
#            warnings that ask for action
#   then     primer set comparison, assay design (MIQE 2.0 §1), off-target (BLAST),
#            protocol advisor, controls & contamination, validation checklist
#   appendix scientific notes, 3′ isoforms, methods, reproducibility, references
# Fonts: DejaVu Sans / Sans Mono, embedded (backend/assets/fonts) — the standard-14
# fonts have no Δ, ², ′, −, ≥ in WinAnsi.
# ================================================================

from __future__ import annotations

import html as _html
import io
import os
import re
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    CondPageBreak, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from algorithm.constants import NTC_DELTA_CQ_MIN
from utils.report_text import (
    REFERENCES, clean, fmt_dg, fmt_pct, fmt_range, fmt_temp, fmt_tm, level_word, plural,
    rule_labels, setting_word, status,
)

# ── Fonts ─────────────────────────────────────────────────────────

FONT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", "assets", "fonts"))
SANS, SANS_B, SANS_I, SANS_BI = "DejaVuSans", "DejaVuSans-Bold", "DejaVuSans-Oblique", "DejaVuSans-BoldOblique"
MONO, MONO_B = "DejaVuSansMono", "DejaVuSansMono-Bold"
_FONTS_READY = False


def register_fonts() -> None:
    """Register the embedded TrueType fonts once per process."""
    global _FONTS_READY
    if _FONTS_READY:
        return
    for name, fname in ((SANS, "DejaVuSans.ttf"), (SANS_B, "DejaVuSans-Bold.ttf"),
                        (SANS_I, "DejaVuSans-Oblique.ttf"), (SANS_BI, "DejaVuSans-BoldOblique.ttf"),
                        (MONO, "DejaVuSansMono.ttf"), (MONO_B, "DejaVuSansMono-Bold.ttf")):
        pdfmetrics.registerFont(TTFont(name, os.path.join(FONT_DIR, fname)))
    pdfmetrics.registerFontFamily(SANS, normal=SANS, bold=SANS_B, italic=SANS_I, boldItalic=SANS_BI)
    pdfmetrics.registerFontFamily(MONO, normal=MONO, bold=MONO_B, italic=MONO, boldItalic=MONO_B)
    _FONTS_READY = True


# ── Colours (HG Lab navy; status colours kept apart from the brand) ──

NAVY = colors.HexColor("#273E74")
NAVY_BG = colors.HexColor("#EEF1F8")
ROW_ALT = colors.HexColor("#F8FAFC")
GRID = colors.HexColor("#CBD5E1")
TEXT = colors.HexColor("#1E293B")
MUTED = colors.HexColor("#475569")
CRIT = "#B91C1C"
WARN = "#B45309"
PASS = "#15803D"

esc = _html.escape


# ── Styles ────────────────────────────────────────────────────────

def _styles() -> dict:
    base = dict(fontName=SANS, textColor=TEXT)
    return {
        "title": ParagraphStyle("title", fontName=SANS_B, fontSize=17, leading=21, textColor=NAVY,
                                spaceAfter=2),
        "sub": ParagraphStyle("sub", fontSize=8.5, leading=11, textColor=MUTED, fontName=SANS),
        "h2": ParagraphStyle("h2", fontName=SANS_B, fontSize=12.5, leading=16, textColor=NAVY,
                             spaceBefore=14, spaceAfter=6),
        "h3": ParagraphStyle("h3", fontName=SANS_B, fontSize=10, leading=13, textColor=TEXT,
                             spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("body", fontSize=9.3, leading=12.8, spaceAfter=3, **base),
        "body_math": ParagraphStyle("body_math", fontSize=9.3, leading=15.5, spaceAfter=3, **base),
        "small": ParagraphStyle("small", fontSize=8, leading=10.5, textColor=MUTED, fontName=SANS,
                                spaceBefore=4, spaceAfter=2),
        "cell": ParagraphStyle("cell", fontSize=8.3, leading=10.4, **base),
        "cell_r": ParagraphStyle("cell_r", fontSize=8.3, leading=10.4, alignment=TA_RIGHT, **base),
        "head": ParagraphStyle("head", fontName=SANS_B, fontSize=8.3, leading=10.4,
                               textColor=colors.white),
        "head_r": ParagraphStyle("head_r", fontName=SANS_B, fontSize=8.3, leading=10.4,
                                 textColor=colors.white, alignment=TA_RIGHT),
        # Sequences: mono, never wrapped (no CJK / no spaces → one line).
        "seq": ParagraphStyle("seq", fontName=MONO, fontSize=8.6, leading=10.6, textColor=TEXT,
                              splitLongWords=0),
        "seq_s": ParagraphStyle("seq_s", fontName=MONO, fontSize=7.6, leading=10.0, textColor=TEXT,
                                splitLongWords=0),
        "ref": ParagraphStyle("ref", fontSize=8, leading=10.4, leftIndent=14, firstLineIndent=-14,
                              spaceAfter=2, **base),
    }


# ── Small builders ────────────────────────────────────────────────

# Author-year mentions in free text (API messages, advisor text) → reference keys.
_AUTO_CITE = [
    (re.compile(r"Chen(?: et al\.)? 2005"), "Chen2005"),
    (re.compile(r"Kramer(?: et al\.)? 2011"), "Kramer2011"),
    (re.compile(r"Varkonyi-Gasic"), "VarkonyiGasic2007"),
    (re.compile(r"Czimmerer(?: et al\.)? 2013"), "Czimmerer2013"),
    (re.compile(r"Schamberger(?: et al\.)? 2014"), "Schamberger2014"),
    (re.compile(r"Stadhouders(?: et al\.)? 2010"), "Stadhouders2010"),
    (re.compile(r"Magee(?: et al\.)? 2017"), "Magee2017"),
    (re.compile(r"Fan 2019"), "Fan2019"),
    (re.compile(r"Fujimoto 2018"), "Fujimoto2018"),
    (re.compile(r"Liang 2018"), "Liang2018"),
    (re.compile(r"isomiRdb"), "isomiRdb"),
    (re.compile(r"MIQE 2\.0"), "Bustin2025"),
]


class _Citations:
    """Numbered references in order of first citation."""

    def __init__(self):
        self.order: list[str] = []
        self.extra: dict[str, str] = {}

    def text(self, key: str) -> str:
        return REFERENCES.get(key) or self.extra.get(key, key)

    def add(self, key: str, text: str) -> str:
        """A reference known only from the design result (advisor source)."""
        long_key = re.sub(r"(?<=[A-Za-z])(\d{2})$", r"20\1", key)
        if long_key in REFERENCES:
            return self(long_key)
        if key not in REFERENCES:
            self.extra.setdefault(key, text)
        return self(key)

    def __call__(self, *keys: str) -> str:
        nums = []
        for k in keys:
            if k not in REFERENCES and k not in self.extra:
                continue
            if k not in self.order:
                self.order.append(k)
            n = str(self.order.index(k) + 1)
            if n not in nums:
                nums.append(n)
        return f"[{', '.join(nums)}]" if nums else ""

    def auto(self, text: str) -> str:
        """Bracketed numbers for the sources an author-year mention names, or ''."""
        keys = [k for rx, k in _AUTO_CITE if rx.search(text or "")]
        return self(*keys)


def _seq(seq: str) -> str:
    return esc(str(seq or ""))


_SEQ_IN_TEXT = re.compile(r"5′-([ACGTUN]{8,})-3′")


def _text(s) -> str:
    """Escaped free text in the report's notation: an inline 5′-SEQ-3′ goes on its own line
    in mono (never broken); code-style math (ΔCq_assay, 2^−ΔCq) becomes sub/superscript."""
    t = esc(clean(s))
    t = _SEQ_IN_TEXT.sub(lambda m: f"<br/>5′-<font name='{MONO}' size='7.6'>{m.group(1)}</font>-3′", t)
    t = re.sub(r"ΔCq_(assay|RT|FWD)", r"ΔCq<sub>\1</sub>", t)
    t = re.sub(r"2\^(−?ΔCq)", r"2<super>\1</super>", t)
    return t


def _seq_seed(seq: str) -> str:
    """Mature sequence with the seed (nt 2–8) in bold."""
    s = esc(str(seq or ""))
    if len(s) < 8:
        return s
    return f"{s[:1]}<b>{s[1:8]}</b>{s[8:]}"


def _table(rows, fracs, st, *, width, right_cols=(), mono_cells=(), zebra=True,
           header=True, first_bold=False, mono_style="seq") -> Table:
    """Full-width table, every cell a Paragraph (text wraps, never overflows).
    rows: list of lists of str (markup allowed); fracs: column width fractions.
    right_cols: column indices right-aligned (numbers). mono_cells: {(r, c)} or a
    callable (r, c) -> bool for sequence cells (mono, unwrapped)."""
    is_mono = mono_cells if callable(mono_cells) else (lambda r, c: (r, c) in mono_cells)
    is_right = right_cols if callable(right_cols) else (lambda r, c: c in right_cols)
    data = []
    for r, row in enumerate(rows):
        out = []
        for c, v in enumerate(row):
            if isinstance(v, (Paragraph, Table)):
                out.append(v)
                continue
            txt = "" if v is None else str(v)
            if header and r == 0:
                sty = st["head_r"] if is_right(r, c) else st["head"]
            elif is_mono(r, c):
                sty = st[mono_style]
            else:
                sty = st["cell_r"] if is_right(r, c) else st["cell"]
                if first_bold and c == 0:
                    txt = f"<b>{txt}</b>"
            out.append(Paragraph(txt, sty))
        data.append(out)
    tbl = Table(data, colWidths=[width * f for f in fracs], repeatRows=1 if header else 0,
                hAlign="LEFT")
    cmds = [
        ("FONTNAME", (0, 0), (-1, -1), SANS),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    if len(data) > 7:
        cmds += [("NOSPLIT", (0, 0), (-1, 3)), ("NOSPLIT", (0, -3), (-1, -1))]
    if zebra and len(data) > 1:
        cmds.append(("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, ROW_ALT]))
    tbl.setStyle(TableStyle(cmds))
    return tbl


def _heading(text: str, st: dict, level: str = "h2") -> list:
    """A heading that never ends a page: break first unless ~4 cm (h3: 2.5 cm) remain."""
    return [CondPageBreak((4 if level == "h2" else 2.5) * cm), Paragraph(text, st[level])]


def _flag(severity: str) -> str:
    if severity == "critical":
        return f"<font color='{CRIT}'><b>Critical:</b></font>"
    return f"<font color='{WARN}'><b>Warning:</b></font>"


def _status_text(level) -> str:
    """'Pass' / 'Warning' / 'Fail' in its colour, followed by the level word."""
    s = status(level)
    word = level_word(level)
    colour = {"Pass": PASS, "Warning": WARN, "Fail": CRIT}.get(s)
    if not colour:
        return esc(word or "—")
    extra = f" ({esc(word)})" if word and word.lower() != s.lower() else ""
    return f"<font color='{colour}'><b>{s}</b></font>{extra}"


# ── Facts read from the design result ─────────────────────────────

def _species_word(meta) -> str:
    return setting_word(meta.get("species"))


def same_reference(target: str, reference: str) -> bool:
    """True when the normalization reference names the target miRNA itself
    ('hsa-miR-16-5p' vs 'miR-16')."""
    def norm(x):
        x = str(x or "").strip().lower()
        x = re.sub(r"^[a-z]{3,5}-(?=(mir|let)-)", "", x)
        return re.sub(r"-[35]p$", "", x)
    t, r = norm(target), norm(reference)
    return bool(t) and bool(r) and t == r


def reverse_tm(results: dict):
    """The universal reverse Tm at the design conditions (ranking, primer3) when the
    design reports it; the precomputed constant otherwise."""
    for s in results.get("top3") or []:
        tp = ((s.get("ranking") or {}).get("pcr") or {}).get("tm_pair") or {}
        if tp.get("tm_reverse") is not None:
            return tp["tm_reverse"]
    return (results.get("universal_reverse") or {}).get("tm")


def design_blast(results: dict) -> dict:
    """BLAST screen run during the design (algorithm 4.0.0): availability and the rank-1
    result. {} when the design does not report it (V4 result)."""
    rs = results.get("ranking_summary") or {}
    top = (results.get("top3") or [{}])[0]
    b = (((top.get("ranking") or {}).get("specificity") or {}).get("blast")) or {}
    if not rs and not b:
        return {}
    return {"available": bool(rs.get("blast_available")) and b.get("score") is not None,
            "reason": rs.get("blast_unavailable_reason"),
            "overall_risk": b.get("overall_risk"), "medium_hits": b.get("medium_hits"),
            "worst_hit": b.get("worst_hit"), "score": b.get("score")}


def family_view(results: dict) -> dict:
    """Seed group of the target as the report names it (the API's auto-generated family
    label, e.g. 'miR-1' for the miR-15/16 seed, is not shown)."""
    cr = (results.get("specificity_warnings") or {}).get("cross_reactivity") or {}
    seq = (results.get("metadata") or {}).get("mirna_sequence") or ""
    seed = seq[1:8].upper() if len(seq) >= 8 else ""
    sibs = cr.get("cross_reactivity") or []
    worst = "None"
    levels = [r.get("risk") for r in sibs]
    for lv in ("IDENTICAL", "HIGH", "LOW"):
        if lv in levels:
            worst = lv
            break
    return {"seed": seed, "close": len(sibs), "worst": worst,
            "name": f"Seed group {seed}" if seed else "Seed group"}


def specificity_verdict(results: dict) -> str:
    """One sentence on rank 1: closest other miRNA, its label, and the BLAST screen."""
    top = (results.get("top3") or [{}])[0]
    rk = top.get("ranking") or {}
    sp = rk.get("specificity") or {}
    parts = []
    ad, tmm = sp.get("assay_dcq") or {}, sp.get("tm_margin") or {}
    if ad.get("label"):
        who = ad.get("worst_target")
        lab = str(ad["label"]).upper()
        verb = {"DISCRIMINATED": "is discriminated", "PARTIAL": "is only partly discriminated",
                "CO-AMPLIFIED": "is predicted to co-amplify"}.get(lab, f"is {level_word(lab).lower()}")
        detail = [f"assay ΔCq {ad['min_delta_cq']:.1f}"] if isinstance(ad.get("min_delta_cq"), (int, float)) else []
        if isinstance(tmm.get("margin"), (int, float)):
            detail.append(f"Tm margin {fmt_tm(tmm['margin'])}")
        parts.append(f"the closest other miRNA{', ' + esc(who) + ',' if who else ''} {verb}"
                     + (f" ({'; '.join(detail)})" if detail else ""))
    else:
        oc = (results.get("specificity_warnings") or {}).get("overhang_collision") or {}
        if oc.get("worst_assay_label"):
            parts.append(f"worst assay label {level_word(oc['worst_assay_label'])}")
    b = design_blast(results)
    if b:
        if b["available"]:
            risk = str(b.get("overall_risk") or "").upper()
            txt = ("no off-target hit of concern" if risk == "SAFE"
                   else f"overall risk {level_word(risk).lower()}")
            parts.append(f"BLAST screen during the design: {txt}")
        else:
            parts.append("BLAST screen not available for this design")
    if not parts:
        return ""
    s = "; ".join(parts)
    return s[:1].upper() + s[1:] + "."


def action_warnings(results: dict) -> list[tuple[str, str]]:
    """(severity, message) of everything that asks for action: critical/warning global
    warnings, edge cases, and a reference gene equal to the target."""
    out = []
    meta = results.get("metadata") or {}
    ds = meta.get("design_settings") or {}
    if same_reference(meta.get("mirna_id"), ds.get("reference")):
        out.append(("warning", f"The normalization reference ({ds.get('reference')}) is the target "
                               f"miRNA itself. Choose a different reference gene."))
    for w in results.get("global_warnings") or []:
        if w.get("severity") in ("critical", "warning"):
            out.append((w["severity"], clean(w.get("message", ""))))
    for e in results.get("edge_cases") or []:
        if e.get("severity") in ("critical", "warning"):
            out.append((e["severity"], clean(e.get("message", ""))))
    order = {"critical": 0, "warning": 1}
    return sorted(out, key=lambda x: order.get(x[0], 2))


def _grade_line(s: dict) -> str:
    rk = s.get("ranking")
    if not rk:
        return f"Score {s.get('total_score', '?')} ({s.get('grade', '')})"
    sp, pcr, fx = rk["specificity"], rk["pcr"], rk["flexible"]
    return (f"Grade {s.get('grade', '?')} · Specificity {sp['total']}/{sp['max']} · "
            f"PCR {pcr['total']}/{pcr['max']} · Composition &amp; structure {fx['total']}/{fx['max']}")


# ── Footer with "Page x of y" ─────────────────────────────────────

def _canvas_maker(left_text: str):
    class _Numbered(rl_canvas.Canvas):
        def __init__(self, *a, **k):
            k["initialFontName"] = k.get("initialFontName") or SANS   # no unembedded Helvetica
            super().__init__(*a, **k)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            n = len(self._pages)
            for st in self._pages:
                self.__dict__.update(st)
                self._footer(n)
                rl_canvas.Canvas.showPage(self)
            rl_canvas.Canvas.save(self)

        def _footer(self, n):
            w, _h = A4
            self.setFont(SANS, 7.5)
            self.setFillColor(MUTED)
            self.setStrokeColor(GRID)
            self.setLineWidth(0.4)
            x0, x1 = 2 * cm + 6, w - 2 * cm - 6
            self.line(x0, 1.45 * cm, x1, 1.45 * cm)
            self.drawString(x0, 1.05 * cm, left_text)
            self.drawRightString(x1, 1.05 * cm, f"Page {self._pageNumber} of {n}")
    return _Numbered


# ── The report ────────────────────────────────────────────────────

def build_pdf_bytes(results: dict, blast_result=None, include_checklist: bool = True,
                    history_count: int = 0, today: str | None = None) -> bytes:
    register_fonts()
    st = _styles()
    cite = _Citations()
    today = today or date.today().isoformat()

    meta = results.get("metadata") or {}
    top3 = results.get("top3") or []
    sl = results.get("stemloop_rt") or {}
    rev = results.get("universal_reverse") or {}
    ds = meta.get("design_settings") or {}
    mirna = str(meta.get("mirna_id") or "unknown")
    tiered = bool(top3) and all(s.get("ranking") for s in top3)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
        bottomMargin=2.1 * cm,
        title=f"{mirna} — stem-loop RT-qPCR primer report",
        author="HG Lab stem-loop RT-qPCR primer designer",
        subject=f"Primer report for {mirna}, algorithm {meta.get('algorithm_version', '?')}",
        creator="HG Lab stem-loop RT-qPCR primer designer",
        initialFontName=SANS,
    )
    W = doc.width - 12          # the frame pads 6 pt on each side
    story: list = []

    def h2(t):
        story.extend(_heading(t, st))

    def p(t, sty="body"):
        story.append(Paragraph(t, st[sty]))

    def gap(h=6):
        story.append(Spacer(1, h))

    # ── Page 1: ready to order ───────────────────────────────────
    story.append(Paragraph("Stem-loop RT-qPCR primer report", st["title"]))
    p(f"HG Lab primer designer · algorithm v{esc(str(meta.get('algorithm_version', '?')))} · "
      f"exported {today}", "sub")
    gap(8)
    ident = [f"<b>{esc(mirna)}</b>", esc(_species_word(meta))]
    if meta.get("mirna_accession"):
        ident.append(esc(str(meta["mirna_accession"])))
    if meta.get("mirna_length"):
        ident.append(f"{meta['mirna_length']} nt")
    p(" · ".join(ident))
    if meta.get("mirna_sequence"):
        p(f"Mature sequence 5′-<font name='{MONO}'>{_seq_seed(meta['mirna_sequence'])}</font>-3′"
          f" <font size='7.5' color='#475569'>(seed, nt 2–8, in bold)</font>")

    if top3:
        best = top3[0]
        h2("Primers to order")
        rows = [["Primer", "Sequence (5′→3′)", "Length", "Tm", "GC"],
                ["Forward (rank 1)", _seq(best.get("sequence")), f"{best.get('length', '?')} nt",
                 fmt_tm(best.get("tm_full")), fmt_pct(best.get("gc_percent"))],
                ["RT stem-loop", _seq(sl.get("sequence")), f"{sl.get('length', '?')} nt",
                 fmt_tm(sl.get("tm_full")) + "*", fmt_pct(sl.get("gc_percent"))],
                ["Universal reverse", _seq(rev.get("sequence")), f"{rev.get('length', '?')} nt",
                 fmt_tm(reverse_tm(results)), fmt_pct(rev.get("gc_percent"))]]
        story.append(_table(rows, [0.17, 0.555, 0.09, 0.105, 0.08], st, width=W,
                            right_cols=(2, 3, 4), mono_cells=lambda r, c: r > 0 and c == 1))
        p(f"Tm: nearest-neighbour model at the design conditions {cite('SantaLucia1998')}. "
          "*RT stem-loop: full-primer DNA:DNA Tm, indicative only; it is not the "
          "overhang:miRNA hybrid Tm and is not used in the ranking.", "small")
        gap(4)
        p(f"<b>Rank 1:</b> {_grade_line(best)}."
          + (f" Primer rules not met: {esc(rule_labels(best.get('v4_rule_violations')))}."
             if best.get("v4_rule_violations") else ""))
        verdict = specificity_verdict(results)
        if verdict:
            p(f"<b>Specificity:</b> {verdict}")

    warns = action_warnings(results)
    if warns:
        h2("Warnings that need action")
        for sev, msg in warns:
            c = cite.auto(msg)
            story.append(KeepTogether([Paragraph(f"{_flag(sev)} {_text(msg)}{' ' + c if c else ''}",
                                                 st["body"]), Spacer(1, 3)]))
    p("For research use only. Validate all primers experimentally before use.", "small")
    story.append(PageBreak())

    # ── Primer set comparison ────────────────────────────────────
    if top3:
        h2("Primer set comparison")
        n = len(top3)
        crit: list[tuple[str, callable, bool]] = [
            ("Forward primer (5′→3′)", lambda s: _seq(s.get("sequence")), False),
        ]
        if tiered:
            crit += [
                ("Grade", lambda s: esc(str(s.get("grade", "—"))), True),
                ("Specificity (S)", lambda s: f"{s['ranking']['specificity']['total']}/{s['ranking']['specificity']['max']}", True),
                ("PCR (P)", lambda s: f"{s['ranking']['pcr']['total']}/{s['ranking']['pcr']['max']}", True),
                ("Composition &amp; structure (F)", lambda s: f"{s['ranking']['flexible']['total']}/{s['ranking']['flexible']['max']}", True),
                ("Closest other miRNA (assay ΔCq)", _closest, False),
            ]
        else:
            crit.append(("Score (grade)", lambda s: f"{s.get('total_score', '—')} ({esc(str(s.get('grade', '')))})", True))
        crit += [
            ("Forward Tm", lambda s: fmt_tm(s.get("tm_full")), True),
            ("GC", lambda s: fmt_pct(s.get("gc_percent")), True),
            ("Amplicon", lambda s: f"{s.get('amplicon_size', '—')} bp", True),
            ("Forward-primer specific length", lambda s: f"{s.get('specific_length', '—')} nt", True),
            ("Hairpin ΔG (kcal/mol)", lambda s: fmt_dg(_get(s, "structure_checks", "hairpin", "dg")), True),
            ("Self-dimer ΔG (kcal/mol)", lambda s: fmt_dg(_get(s, "structure_checks", "self_dimer", "dg_overall")), True),
            ("Dimer ΔG, RNAcofold 37 °C (kcal/mol)", lambda s: _cofold_dimer(s), True),
            ("Cycle-1 occupancy at Ta (% of primer bound)",
             lambda s: _occupancy(_get(s, "scores", "bound_fraction_binding_pct")), True),
            ("Primer rules not met", lambda s: esc(rule_labels(s.get("v4_rule_violations"))), False),
        ]
        if tiered:
            crit.append(("Tie-break score", lambda s: f"{s['ranking'].get('detailed_score', '—')}", True))
        rows = [["Criterion"] + [f"Rank {s.get('rank', i + 1)}" for i, s in enumerate(top3)]]
        numeric_rows = set()
        for r_i, (label, fn, numeric) in enumerate(crit, start=1):
            rows.append([label] + [fn(s) for s in top3])
            if numeric:
                numeric_rows.add(r_i)
        frac0 = 0.25
        fr = [frac0] + [(1 - frac0) / n] * n
        tbl = _table(rows, fr, st, width=W, mono_cells=lambda r, c: r == 1 and c > 0,
                     mono_style="seq_s", right_cols=lambda r, c: c > 0 and (r == 0 or r in numeric_rows))
        story.append(tbl)
        if tiered:
            p("Sets rank by Specificity (S: BLAST off-target, assay ΔCq, Tm margin) first, then "
              "PCR (P: forward Tm vs Ta), then Composition &amp; structure (F). The tie-break score "
              "only orders sets that are equal on every group.", "small")

    # ── Assay design (MIQE 2.0 §1) ───────────────────────────────
    h2(f"Assay design (MIQE 2.0 §1) {cite('Bustin2025')}")
    rows = [["Parameter", "Value"]] + [[esc(a), esc(b)] for a, b in design_rows(meta, top3)]
    story.append(_table(rows, [0.36, 0.64], st, width=W))
    p("Reported by the design tool. The oligonucleotide supplier and optimization details are "
      "added by the user.", "small")

    # ── Off-target specificity (BLAST) ───────────────────────────
    h2("Off-target specificity (BLAST)")
    blines = blast_lines(blast_result)
    db = design_blast(results)
    if blines:
        rows = [["Metric", "Value"]] + [[esc(a), b] for a, b in blines]
        story.append(_table(rows, [0.5, 0.5], st, width=W, right_cols=(1,)))
        p("The overall risk counts off-targets outside the target's seed family only; same-family "
          "cross-reactivity is reported separately.", "small")
    elif db.get("available"):
        hits = db.get("medium_hits") or 0
        p(f"BLAST against miRBase 22.1 ran during the design. Rank 1: "
          f"{_status_text(db.get('overall_risk'))}, {plural(hits, 'medium-risk hit')}"
          f" (S1 level {db.get('score')} of 5). Use “Show all hits” on the Results page to list "
          "every hit in this report.")
    elif db:
        p("Not assessed: BLAST was not available during this design"
          + (f" ({esc(str(db['reason']))})" if db.get("reason") else "") + ".")
    else:
        p("Not assessed. Run the off-target (BLAST) check on the Results page, then export again.")

    # ── Protocol advisor ─────────────────────────────────────────
    pa = results.get("protocol_advice") or []
    if pa:
        h2("Protocol advisor")
        p("Suggestions matched to your assay parameters, most relevant first. Descriptive only; "
          "validate experimentally.", "small")
        rank = {"high": 0, "medium": 1, "low": 2}
        for item in sorted(pa, key=lambda x: rank.get(str(x.get("match", "")).lower(), 3)):
            m = str(item.get("match", "")).lower()
            rel = f" — {m.capitalize()} relevance" if m else ""
            refs = [cite.add(src.get("tag") or src["doi"], _advisor_ref(src))
                    for src in item.get("sources") or [] if src.get("doi")]
            refs = ", ".join(r.strip("[]") for r in refs if r)
            block = [Paragraph(f"<b>{esc(clean(item.get('title', '')))}</b>{rel}"
                               + (f" [{refs}]" if refs else ""), st["body"])]
            if item.get("recommendation"):
                rec = item["recommendation"]
                c = cite.auto(rec)
                block.append(Paragraph(_text(rec) + (f" {c}" if c else ""), st["body"]))
            why = _advisor_match_note(item, results)
            if why:
                block.append(Paragraph(why, st["small"]))
            block.append(Spacer(1, 4))
            story.append(KeepTogether(block))

    # ── Controls & contamination ─────────────────────────────────
    if results.get("controls_advice"):
        story.extend(_controls(results["controls_advice"], history_count, st, W, cite))

    # ── Validation checklist ─────────────────────────────────────
    if include_checklist:
        story.extend(_checklist(results, blast_result, st, W, cite))

    # ── Appendix ─────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Appendix", st["title"]))
    notes = _scientific_notes(results, cite)
    if notes:
        h2("Scientific notes")
        for n_ in notes:
            p(f"• {n_}")
    tpi = sl.get("three_prime_isomir") or {}
    story.extend(_isoform_table(tpi, st, W, cite))
    h2("Methods")
    for m in _methods(results, cite):
        p(m, "body_math")
    h2("Reproducibility")
    rows = [["Item", "Value"]] + [[esc(a), f"<font name='{MONO}' size='7.6'>{esc(b)}</font>"
                                   if a.endswith("sha256") or "hash" in a else esc(b)]
                                  for a, b in reproducibility_rows(meta, today)]
    story.append(_table(rows, [0.34, 0.66], st, width=W))
    h2("References")
    for i, key in enumerate(cite.order, 1):
        p(f"{i}. {esc(cite.text(key))}", "ref")
    gap(6)
    p("For research use only. Validate all primers experimentally before use.", "small")

    doc.build(story, canvasmaker=_canvas_maker(
        f"{mirna} · HG Lab stem-loop RT-qPCR primer report · {today}"))
    return buf.getvalue()


# ── Section helpers ───────────────────────────────────────────────

def _advisor_ref(src: dict) -> str:
    """Reference text for a Protocol Advisor source ('Lagatie17' → 'Lagatie 2017. … doi:…')."""
    tag = str(src.get("tag") or "")
    m = re.match(r"([A-Za-z\-]+?)(\d{2})$", tag)
    who = f"{m.group(1)} 20{m.group(2)}" if m else tag
    bits = [who] if who else []
    if src.get("pmid"):
        bits.append(f"PMID {src['pmid']}")
    bits.append(f"doi:{src['doi']}")
    return ". ".join(bits)


def _advisor_match_note(item: dict, results: dict) -> str:
    """Why a rule matched when its title names a condition this design does not meet
    (P1 'SYBR + high family cross-reactivity' matches on SYBR alone, at half weight)."""
    if item.get("id") != "P1":
        return ""
    cr = ((results.get("specificity_warnings") or {}).get("cross_reactivity") or {})
    risks = {r.get("risk") for r in cr.get("cross_reactivity") or []}
    if risks & {"HIGH", "IDENTICAL"}:
        return ""
    return ("Matched on SYBR Green detection only: no seed-family member at high risk was found "
            "for this design.")


def _get(s, *keys):
    o = s
    for k in keys:
        o = o.get(k, {}) if isinstance(o, dict) else {}
    return o if isinstance(o, (int, float)) and not isinstance(o, bool) else None


def _cofold_dimer(s: dict) -> str:
    sc = s.get("structure_checks") or {}
    vals = [(sc.get(k) or {}).get("dg_cofold") for k in ("self_dimer", "hetero_dimer")]
    if any(v is None for v in vals):
        return "—"
    return fmt_dg(min(vals))


def _occupancy(v) -> str:
    if v is None:
        return "—"
    if v < 0.01:
        return "< 0.01%"
    return fmt_pct(v, 2 if v < 1 else 1)


def _closest(s: dict) -> str:
    ad = ((s.get("ranking") or {}).get("specificity") or {}).get("assay_dcq") or {}
    who, d = ad.get("worst_target"), ad.get("min_delta_cq")
    if not who:
        return "None"
    return f"{esc(who)} ({d:.1f})" if isinstance(d, (int, float)) else esc(who)


def design_rows(meta: dict, top3: list) -> list[tuple[str, str]]:
    """MIQE 2.0 §1 rows the tool can self-report (the hashes go to reproducibility_rows)."""
    ds = meta.get("design_settings") or {}
    ident = " · ".join(filter(None, [
        meta.get("mirna_id") or "—", setting_word(meta.get("species")),
        meta.get("mirna_accession") or None,
        f"{meta['mirna_length']} nt" if meta.get("mirna_length") else None,
    ]))
    if ds.get("na_mm") is not None:
        ions = (f"Na⁺/K⁺ total {ds['na_mm']} mM · extra K⁺ {ds.get('k_mm') or 0} mM · "
                f"Mg²⁺ {ds.get('mg_mm')} mM · dNTP {ds.get('dntp_mm')} mM")
    else:
        ef = ds.get("effective_p3") or {}
        ions = (f"Monovalent {ef['mv_conc']:g} mM · Mg²⁺ {ef['dv_conc']:g} mM · dNTP "
                f"{ef['dntp_conc']:g} mM (tool defaults)") if ef else "—"
    primer_nm = ds.get("primer_nm")
    if primer_nm is None:
        primer_nm = (ds.get("effective_p3") or {}).get("dna_conc", "—")
    lna = next((s.get("lna_positions") or s.get("lna") for s in top3 or []
                if s.get("lna_positions") or s.get("lna")), None)
    ta = ds.get("annealing_temp_c")
    return [
        ("Design tool", f"HG Lab stem-loop RT-qPCR primer designer, algorithm "
                        f"v{meta.get('algorithm_version', '?')}"
                        + (" (tiered ranking)" if (meta.get("provenance") or {}).get("scoring_system") == "tiered"
                           or meta.get("scoring_system") == "tiered" else "")),
        ("Target (name · species · accession · length)", ident),
        ("Detection method", setting_word(ds.get("detection_method"))),
        ("RT 3′ overhang (binding region)",
         f"{ds.get('rt_overhang_nt', meta.get('binding_region_nt', '?'))} nt (Chen 2005 stem-loop)"),
        ("Primer Tm window", fmt_range(ds.get("tm_target_c"), "°C")),
        ("Primer GC window", fmt_range(ds.get("gc_percent"), "%")),
        ("Amplicon length window", fmt_range(ds.get("amplicon_bp"), "bp")),
        ("Reaction ions", ions),
        ("Primer concentration", f"{primer_nm} nM"),
        ("Buffer pH", str(ds["buffer_ph"]) if ds.get("buffer_ph") is not None
         else "Not applied (default; no Tris term)"),
        ("Oligo modifications", f"LNA at forward positions {lna}" if lna
         else "None (standard DNA oligonucleotides)"),
        ("Planned Ta · cycles", f"{fmt_temp(ta) if ta is not None else '—'} · "
                                f"{ds.get('total_cycles') or '—'} cycles"),
        ("Efficiency acceptance", fmt_range(ds.get("efficiency_acceptance_pct"), "%")),
        ("Quantification · reference", " · ".join(
            x for x in (setting_word(ds.get("quantification")) if ds.get("quantification") else "",
                        str(ds.get("reference") or "")) if x) or "—"),
        ("Sample type · instrument", " · ".join(
            x for x in (setting_word(ds.get("sample_type")) if ds.get("sample_type") else "",
                        setting_word(ds.get("qpcr_instrument")) if ds.get("qpcr_instrument") else "")
            if x) or "—"),
    ]


def reproducibility_rows(meta: dict, today: str) -> list[tuple[str, str]]:
    pv = meta.get("provenance") or {}
    rows = [("Algorithm version", str(meta.get("algorithm_version", "?"))),
            ("Ranking system", str(pv.get("scoring_system") or meta.get("scoring_system") or "—"))]
    if pv.get("primer3_py"):
        rows.append(("primer3-py", str(pv["primer3_py"])))
    if pv.get("viennarna"):
        rows.append(("ViennaRNA", str(pv["viennarna"])))
    if pv.get("scoring_weights_sha256"):
        rows.append(("Scoring weights hash", str(pv["scoring_weights_sha256"])))
    if pv.get("tiered_thresholds_sha256"):
        rows.append(("Tiered thresholds hash", str(pv["tiered_thresholds_sha256"])))
    if pv:
        rows.append(("miRBase release", str(pv.get("mirbase_release", "unknown"))))
    if pv.get("mature_fa_sha256"):
        rows.append(("mature.fa sha256", str(pv["mature_fa_sha256"])))
    if meta.get("candidates_passed_prefilter") is not None:
        rows.append(("Candidate forward primers evaluated", str(meta["candidates_passed_prefilter"])))
    rows.append(("Exported", today))
    return rows


def blast_lines(blast_result) -> list[tuple[str, str]]:
    """Rows of a /api/blast-check result ('Show all hits'); [] when it was not run."""
    if not isinstance(blast_result, dict):
        return []
    s = blast_result.get("summary") or {}
    return [
        ("Overall off-target risk", _status_text(s.get("overall_risk", "?"))),
        ("Critical hits (outside the seed family)", str(s.get("critical_count", 0))),
        ("High-risk hits", str(s.get("high_risk_count", 0))),
        ("Medium-risk hits", str(s.get("medium_risk_count", 0))),
        ("Same-family hits (expected)", str(s.get("same_family_count", 0))),
        ("Other-species hits excluded", str(s.get("cross_species_excluded", 0))),
    ]


def _controls(ca: dict, history_count: int, st: dict, W: float, cite) -> list:
    ntc = f"No amplification, or Cq ≥ {NTC_DELTA_CQ_MIN} cycles later than the latest-Cq sample"
    rows = [["Control", "Set-up", "Checks", "Pass criterion"]]
    uses_note = False
    for c in ca.get("controls") or []:
        crit = clean(c.get("pass", ""))
        if crit.startswith("No amplification, or Cq"):
            crit, uses_note = "See note ¹", True
        rows.append([f"<b>{esc(clean(c.get('name', '')))}</b>", _text(c.get("setup", "")),
                     _text(c.get("checks", "")), esc(crit)])
    out = [*_heading("Controls &amp; contamination", st),
           Paragraph(f"Run these controls on every plate. Report NTC and no-RT results "
                     f"{cite('Bustin2025')}.", st["body"]), Spacer(1, 3),
           _table(rows, [0.17, 0.33, 0.27, 0.23], st, width=W)]
    if uses_note:
        out.append(Paragraph(f"¹ Pass criterion: {ntc} (HG Lab convention).", st["small"]))
    if ca.get("melt_note"):
        out += [Spacer(1, 4), Paragraph(_text(ca["melt_note"]), st["body"])]
    cont = ca.get("contamination") or {}
    reasons = cont.get("reasons") or []
    out.extend(_heading("Contamination risk", st, "h3"))
    if reasons:
        out.append(Paragraph("<b>Elevated</b>", st["body"]))
        for r in reasons:
            out.append(Paragraph("• " + esc(clean(r)), st["body"]))
    else:
        out.append(Paragraph(f"<b>Standard</b>. No specific risk factor found (abundance data: "
                             f"{esc(str(cont.get('abundance_data', 'n/a')))}).", st["body"]))
    if history_count:
        times = "once" if history_count == 1 else f"{history_count} times"
        out.append(Paragraph(f"This miRNA was designed {times} before in this browser. If its "
                             "amplicon has already been made in the lab, amplicon carry-over is the "
                             "most common cause of a positive NTC.", st["body"]))
    if cont.get("precautions"):
        out.extend(_heading("Precautions", st, "h3"))
        for pr in cont["precautions"]:
            out.append(Paragraph("• " + esc(clean(pr)), st["body"]))
    return out


def specificity_check_value(results: dict, blast_result=None) -> tuple[str, str]:
    """(acceptance text, value) of the in-silico specificity checklist row, from what the
    design and the optional 'Show all hits' check actually report."""
    fam = family_view(results)
    parts = [f"Seed group: {level_word(fam['worst']).lower() if fam['worst'] != 'None' else 'no close sibling'}"]
    top = (results.get("top3") or [{}])[0]
    ad = ((top.get("ranking") or {}).get("specificity") or {}).get("assay_dcq") or {}
    if ad.get("label"):
        parts.append(f"Assay ΔCq: {status(ad['label'])} ({level_word(ad['label'])})")
    bs = ((blast_result or {}).get("summary") or {}) if isinstance(blast_result, dict) else {}
    db = design_blast(results)
    if bs.get("overall_risk"):
        parts.append(f"BLAST: {status(bs['overall_risk'])} ({level_word(bs['overall_risk'])}, all hits)")
    elif db.get("available"):
        parts.append(f"BLAST: {status(db['overall_risk'])} ({level_word(db['overall_risk'])}, design screen)")
    else:
        parts.append("BLAST: not assessed")
    return ("Assessed in silico by the design tool", "; ".join(parts))


def _checklist(results: dict, blast_result, st: dict, W: float, cite) -> list:
    acc, val = specificity_check_value(results, blast_result)
    rows = [["Criterion", "Acceptance target", "Reference", "Pass (Y/N)", "Value / notes"],
            ["No-template control (NTC)", f"No amplification, or Cq ≥ {NTC_DELTA_CQ_MIN} cycles "
             "later than the latest-Cq sample", "HG Lab convention; reported per MIQE 2.0", "", ""],
            ["No-RT control", "No signal (excludes genomic DNA and self-priming)", "MIQE 2.0", "", ""],
            ["Melting curve (SYBR Green)", "Single peak; no primer-dimer or non-specific product",
             "MIQE 2.0; Varkonyi-Gasic 2007", "", ""],
            ["Standard curve", "≥ 5 points of 10-fold serial dilutions, ≥ 1 log range", "MIQE 2.0", "", ""],
            ["PCR efficiency (with 95% CI)", "90–110%, E = 10<super>−1/slope</super> − 1",
             "MIQE 2.0", "", ""],
            ["R² (linearity)", "≥ 0.98", "MIQE 2.0", "", ""],
            ["LOD, LLOQ and ULOQ", "Determine and report the limits of detection and quantification",
             "MIQE 2.0", "", ""],
            ["Efficiency-corrected quantification", "Report efficiency-corrected quantities with "
             "prediction intervals; avoid ΔΔCq alone", "MIQE 2.0", "", ""],
            ["Reference-gene normalization", "≥ 2 reference genes, geometric mean, stability "
             "validated in your samples", "MIQE 2.0", "", ""],
            ["Technical replicates", "≥ 3 replicates; report Cq mean ± SD (repeatability)",
             "MIQE 2.0", "", ""],
            ["Reproducibility (inter-assay)", "Variation across days, operators and instruments",
             "MIQE 2.0", "", ""],
            ["Raw fluorescence data", "Deposit raw data (RDML or RDES)", "MIQE 2.0", "", ""],
            ["Specificity (in silico)", acc, "In-silico design output", "", esc(val)]]
    tbl = _table(rows, [0.23, 0.30, 0.15, 0.13, 0.19], st, width=W)
    return [*_heading(f"Validation checklist (MIQE 2.0) {cite('Bustin2025', 'VarkonyiGasic2007')}", st),
            Paragraph("Complete after wet-lab validation. Only the in-silico specificity row is "
                      "filled in from the design.", st["body"]),
            Spacer(1, 3), tbl]


def _scientific_notes(results: dict, cite) -> list[str]:
    notes = []
    sl = results.get("stemloop_rt") or {}
    if sl.get("tm_full") is not None:
        notes.append(f"The RT stem-loop full-primer Tm ({fmt_tm(sl['tm_full'])}) is a DNA:DNA value, "
                     "indicative only, and is not used in the ranking.")
    tpi = sl.get("three_prime_isomir") or {}
    if tpi.get("median_3prime_fraction") is not None:
        notes.append(f"In isomiRdb, a median {fmt_pct(100 * tpi['median_3prime_fraction'])} of reads "
                     f"of this miRNA are 3′ isoforms {cite('isomiRdb')}.")
    if tpi.get("dominant_isoform_risk") and tpi.get("dominant_isoform_warning"):
        notes.append(esc(clean(tpi["dominant_isoform_warning"])))
    oc = (results.get("specificity_warnings") or {}).get("overhang_collision") or {}
    if oc:
        s = oc.get("summary") or {}
        co, pa = s.get("CO-AMPLIFIED", 0), s.get("PARTIAL", 0)
        if co or pa:
            notes.append(f"Assay specificity: {plural(co, 'other miRNA')} predicted to co-amplify and "
                         f"{pa} only partly discriminated {cite('Chen2005', 'Czimmerer2013')}.")
        else:
            notes.append(f"Assay specificity: no other miRNA is predicted to co-amplify; the model is "
                         f"described under Methods {cite('Chen2005', 'Czimmerer2013')}.")
    fam = family_view(results)
    if fam["seed"]:
        close = ("no sibling within 2 mismatches of the RT overhang" if not fam["close"]
                 else f"{plural(fam['close'], 'sibling')} within 2 mismatches of the RT overhang "
                      f"(worst risk {level_word(fam['worst']).lower()})")
        notes.append(f"{fam['name']}: {close}. Seed grouping is approximate and shown for "
                     "biological context only.")
    for s in results.get("top3") or []:
        flag = s.get("isomir_flag") or {}
        if flag.get("isomir_discrimination_risk"):
            notes.append(f"Rank {s.get('rank')}: isomiR co-amplification risk. "
                         f"{esc(clean(flag.get('note', '')))}")
    return notes


def _methods(results: dict, cite) -> list[str]:
    out = [
        f"<b>Tm.</b> primer3 nearest-neighbour Tm with SantaLucia 1998 parameters and salt "
        f"correction {cite('SantaLucia1998')}; Mg²⁺ and dNTP by the von Ahsen 2001 correction "
        f"{cite('vonAhsen2001')}, at the reaction conditions of the design.",
        f"<b>Secondary structure.</b> Hairpins and dimers by primer3; full-structure dimer ΔG by "
        f"RNAcofold with DNA parameters at 37 °C {cite('Kang2017')}; template structure around the "
        f"binding site by ViennaRNA {cite('Fan2019')}.",
    ]
    oc = (results.get("specificity_warnings") or {}).get("overhang_collision") or {}
    if oc.get("interpretation"):
        out.append(f"<b>Assay specificity (ΔCq model).</b> {_text(oc['interpretation'])} "
                   f"{cite('Chen2005', 'Czimmerer2013', 'Schamberger2014', 'Stadhouders2010', 'Magee2017')}")
    out.append(f"<b>Stem-loop RT-qPCR.</b> RT primer body and universal reverse primer as in Chen "
               f"2005 and Kramer 2011 {cite('Chen2005', 'Kramer2011')}.")
    return out


def _isoform_table(tpi: dict, st: dict, W: float, cite) -> list:
    variants = tpi.get("dominant_3prime_variants") or []
    if not variants or "rt_capture" not in variants[0]:
        return []
    out = _heading(f"Most common 3′ isoforms (isomiRdb, pooled) {cite('isomiRdb')}", st, "h3")
    if tpi.get("reference_note"):
        return out + [Paragraph(esc(clean(tpi["reference_note"])) + ".", st["body"])]

    def share(x):
        if x is None:
            return "—"
        return fmt_pct(100 * x, 1)

    def end(rna, at):
        rna = esc(rna or "")
        return rna if at is None else f"{rna[:at]}<b><u>{rna[at:]}</u></b>"

    rows = [["3′ end", "Type", "Share of reads", "Expected RT capture"],
            [end(tpi.get("canonical_end_rna"), None), "miRBase 22.1 end",
             share(tpi.get("canonical_3prime_share_pooled")), "Primer target"]]
    for v in variants:
        rows.append([end(v.get("end_rna"), v.get("end_diff_at")), esc(clean(v.get("type_label", ""))),
                     share(v.get("pooled_share")),
                     esc(clean((v.get("rt_capture") or {}).get("label", "")))])
    return out + [_table(rows, [0.18, 0.22, 0.17, 0.43], st, width=W, right_cols=(2,),
                         mono_cells=lambda r, c: r > 0 and c == 0)]
