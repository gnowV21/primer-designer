# ================================================================
# routes/export.py — POST /api/export  (Phase 4)
#
# Generates PDF (reportlab) or CSV (stdlib csv) from /api/design
# results object. Stream in-memory — no file written to disk.
#
# Security:
#  - format whitelisted to {"pdf", "csv"} — no eval
#  - filename built server-side from sanitized mirna_id — no path traversal
#  - mirna_id sanitized: [^A-Za-z0-9._-] → '_', capped 40 chars
#  - results validated before render
#  - CORS: inherits app.py settings (localhost:5173/3000)
# ================================================================

import csv
import html as _html
import io
import re
from datetime import date

from flask import Blueprint, jsonify, request, make_response

try:
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    )
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False

export_bp = Blueprint("export", __name__)

# Brand colours (Week 1 §4)
_TEAL       = "#0F6E56"
_TEAL_LIGHT = "#5DCAA5"
_TEAL_BG    = "#E1F5EE"

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")
_CSV_ROLES  = ("Forward", "RT_StemLoop", "Universal_Reverse")


def _sanitize(mirna_id: str) -> str:
    s = _SAFE_CHARS.sub("_", mirna_id)[:40] if mirna_id else "unknown"
    return re.sub(r"\.\.+", "_", s)  # collapse .. to block path traversal


# ── Route ─────────────────────────────────────────────────────────

@export_bp.route("/export", methods=["POST"])
def export_primers():
    """
    POST /api/export
    body: {
      "format": "pdf" | "csv",
      "results": <object /api/design returned>,
      "include_checklist": true | false   (default: true, Phase 7 PART E)
    }
    200 → file stream (Content-Disposition: attachment)
    400 → invalid format / missing results
    503 → reportlab not installed (PDF only)
    """
    body    = request.get_json(force=True) or {}
    fmt     = (body.get("format") or "").lower().strip()
    results = body.get("results")
    include_checklist = body.get("include_checklist", True)

    # Validate format — whitelist only
    if fmt not in ("pdf", "csv"):
        return jsonify({"error": "format must be 'pdf' or 'csv'"}), 400

    # Validate results structure
    if not results or not isinstance(results, dict):
        return jsonify({"error": "results object is required"}), 400
    if not results.get("top3"):
        return jsonify({"error": "results.top3 is required and must be non-empty"}), 400

    meta    = results.get("metadata", {})
    mirna_id = _sanitize(meta.get("mirna_id", "unknown"))
    filename = f"primer_report_{mirna_id}.{fmt}"

    if fmt == "csv":
        return _build_csv(results, filename, include_checklist=include_checklist)
    else:
        if not _REPORTLAB_AVAILABLE:
            return jsonify({
                "error": "PDF export requires 'reportlab'. Run: pip install reportlab>=4.0"
            }), 503
        return _build_pdf(results, filename, include_checklist=include_checklist)


# ── CSV builder ───────────────────────────────────────────────────

def _build_csv(results: dict, filename: str, include_checklist: bool = True):
    meta    = results.get("metadata", {})
    top3    = results.get("top3", [])
    sl      = results.get("stemloop_rt", {})
    rev     = results.get("universal_reverse", {})

    buf = io.StringIO()
    buf.write(
        f"# HG Lab Primer Designer — miRNA {meta.get('mirna_id', 'unknown')}, "
        f"algorithm v{meta.get('algorithm_version', '?')}, "
        f"exported {date.today().isoformat()}\r\n"
    )

    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow([
        "Set_Rank", "Primer_Role", "Sequence", "Length_nt",
        "Tm_C", "GC_percent", "Hairpin_dG_kcalmol", "SelfDimer_dG_kcalmol",
        "Amplicon_bp", "Total_Score", "Grade", "Notes",
    ])

    for s in top3:
        rank = s.get("rank", "?")
        sc   = s.get("structure_checks", {})
        hp   = sc.get("hairpin", {}).get("dg", "")
        sd   = sc.get("self_dimer", {}).get("dg", "")

        # Forward primer
        writer.writerow([
            rank, "Forward", s.get("sequence", ""), s.get("length", ""),
            _fmt(s.get("tm_full")), _fmt(s.get("gc_percent")),
            _fmt(hp), _fmt(sd),
            s.get("amplicon_size", ""), _fmt(s.get("total_score")),
            s.get("grade", ""), f"Binding region {s.get('specific_length', '?')} nt",
        ])

    # RT stem-loop — same for all sets, written once
    sl_sc = sl.get("self_structure_check", {})
    writer.writerow([
        "", "RT_StemLoop", sl.get("sequence", ""), sl.get("length", ""),
        _fmt(sl.get("tm_full")), _fmt(sl.get("gc_percent")),
        _fmt(sl_sc.get("hairpin_dg")), "", "", "", "",
        f"MFE {_fmt(sl.get('mfe'))} kcal/mol ({sl.get('mfe_method', '')})",
    ])

    # Universal reverse — same for all sets, written once
    rev_sc = rev.get("self_structure_check", {})
    writer.writerow([
        "", "Universal_Reverse", rev.get("sequence", ""), rev.get("length", ""),
        _fmt(rev.get("tm")), _fmt(rev.get("gc_percent")),
        _fmt(rev_sc.get("hairpin_dg")), _fmt(rev_sc.get("self_dimer_dg")),
        "", "", "", "Fixed universal reverse [Chen05][K11]",
    ])

    if include_checklist:
        _append_checklist_csv(writer, buf, results)

    response = make_response(buf.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


def _append_checklist_csv(writer, buf, results: dict):
    """Append MIQE-aligned validation checklist block to CSV. [MIQE09]"""
    # Auto-fill specificity data from results
    spec = results.get("specificity_warnings", {})
    cr   = spec.get("cross_reactivity", {})
    cr_risks = [r.get("risk") for r in cr.get("cross_reactivity", [])]
    worst_family_risk = (
        "HIGH" if "HIGH" in cr_risks or "IDENTICAL" in cr_risks
        else ("LOW" if "LOW" in cr_risks else "SAFE")
    )
    blast_risk = ""  # populated by user from BLAST results

    buf.write("\r\n# VALIDATION CHECKLIST (MIQE-aligned, Bustin et al. 2009 Clin Chem)\r\n")
    buf.write("# Fill in Pass (Y/N) and Measured_Value after wet-lab validation.\r\n")
    buf.write("# For research use only. Validate primers experimentally before use.\r\n")
    writer.writerow(["Item", "Acceptance_Criterion", "Reference", "Pass", "Measured_Value"])

    checklist = [
        (
            "No-template control (NTC)",
            "No amplification, or Cq ≥5 cycles above lowest standard",
            "MIQE09",
            "",
            "",
        ),
        (
            "No-RT control",
            "No signal (confirms absence of genomic DNA / self-priming)",
            "MIQE09",
            "",
            "",
        ),
        (
            "Melting curve (SYBR Green)",
            "Single peak; no primer-dimer or non-specific product",
            "MIQE09, Varkonyi-Gasic 2007",
            "",
            "",
        ),
        (
            "Standard curve",
            "≥5 dilution points, ≥1 log range (10-fold serial dilutions)",
            "MIQE09",
            "",
            "",
        ),
        (
            "PCR efficiency",
            "90–110%  [= 10^(−1/slope) − 1]",
            "MIQE09",
            "",
            "",
        ),
        (
            "R² (linearity)",
            "≥ 0.98",
            "MIQE09",
            "",
            "",
        ),
        (
            "Technical replicates",
            "≥3 replicates; report Cq mean and SD",
            "MIQE09",
            "",
            "",
        ),
        (
            "Specificity (in-silico)",
            (
                f"Family cross-reactivity: {worst_family_risk} risk "
                f"(see family_cross_reactivity in design output). "
                f"BLAST off-target risk: {blast_risk or 'run /api/blast-check to assess'}."
            ),
            "Phase 3 specificity_check",
            "",
            worst_family_risk,
        ),
    ]

    for row in checklist:
        writer.writerow(list(row))


# ── PDF builder ───────────────────────────────────────────────────

def _build_pdf(results: dict, filename: str, include_checklist: bool = True):
    from reportlab.lib import colors as rl_colors
    teal     = rl_colors.HexColor(_TEAL)
    teal_bg  = rl_colors.HexColor(_TEAL_BG)

    meta  = results.get("metadata", {})
    top3  = results.get("top3", [])
    sl    = results.get("stemloop_rt", {})
    rev   = results.get("universal_reverse", {})
    gw    = results.get("global_warnings", [])
    ec    = results.get("edge_cases", [])

    # Escape meta strings used in reportlab XML Paragraphs
    esc = _html.escape
    e = esc  # keep short alias for meta fields below
    mirna_id_safe  = e(str(meta.get("mirna_id", "unknown")))
    mirna_seq_safe = e(str(meta.get("mirna_sequence", "")))
    alg_ver_safe   = e(str(meta.get("algorithm_version", "?")))
    score_ver_safe = e(str(meta.get("scoring_version", "V4")))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()
    h1  = styles["Heading1"]
    h2  = styles["Heading2"]
    h3  = styles["Heading3"]
    body = styles["Normal"]
    mono_style = styles["Code"]

    story = []

    # ── Header ──────────────────────────────────────────────────
    story.append(Paragraph("HG Lab — Stem-loop RT-qPCR Primer Report", h1))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        f"miRNA: <b>{mirna_id_safe}</b> "
        f"({meta.get('mirna_length', '?')} nt) &nbsp;|&nbsp; "
        f"Sequence: <font name='Courier'>{mirna_seq_safe}</font>",
        body,
    ))
    story.append(Paragraph(
        f"Exported: {date.today().isoformat()} &nbsp;|&nbsp; "
        f"Algorithm v{alg_ver_safe} &nbsp;|&nbsp; "
        f"Scoring: {score_ver_safe}",
        body,
    ))
    story.append(Spacer(1, 0.5*cm))

    # ── Recommended set (Rank 1) ─────────────────────────────────
    if top3:
        best = top3[0]
        story.append(Paragraph("Recommended Primer Set (Rank 1)", h2))
        story.append(Paragraph(
            f"Score: <b>{e(str(best.get('total_score', '?')))}</b> — {e(str(best.get('grade', '')))} "
            f"&nbsp;|&nbsp; Total primers designed: {meta.get('candidates_passed_prefilter', '?')}",
            body,
        ))

        seq_table_data = [
            ["Role", "Sequence (5′→3′)", "Length", "Tm", "GC%"],
            ["Forward", best.get("sequence", ""), f"{best.get('length', '?')} nt",
             f"{_fmt(best.get('tm_full'))}°C", f"{_fmt(best.get('gc_percent'))}%"],
            ["RT Stem-loop", sl.get("sequence", ""), f"{sl.get('length', '?')} nt",
             f"{_fmt(sl.get('tm_full'))}°C", f"{_fmt(sl.get('gc_percent'))}%"],
            ["Universal Reverse", rev.get("sequence", ""), f"{rev.get('length', '?')} nt",
             f"{_fmt(rev.get('tm'))}°C", f"{_fmt(rev.get('gc_percent'))}%"],
        ]
        col_widths = [3.5*cm, 8.5*cm, 2*cm, 2*cm, 1.5*cm]
        seq_tbl = Table(seq_table_data, colWidths=col_widths)
        seq_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), teal),
            ("TEXTCOLOR",     (0, 0), (-1, 0), rl_colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME",      (1, 1), (1, -1), "Courier"),
            ("FONTSIZE",      (1, 1), (1, -1), 7),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("BACKGROUND",    (0, 1), (-1, 1), teal_bg),
            ("GRID",          (0, 0), (-1, -1), 0.5, rl_colors.grey),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F8FAFB")]),
        ]))
        story.append(seq_tbl)
        story.append(Spacer(1, 0.5*cm))

    # ── Comparison table (Tab A summary) ─────────────────────────
    story.append(Paragraph("Primer Set Comparison", h2))
    cmp_header = ["Criterion", "Rank 1", "Rank 2", "Rank 3"]
    criteria = [
        ("Total score",    lambda s: f"{_fmt(s.get('total_score'))} ({s.get('grade', '')})"),
        ("Forward Tm",     lambda s: f"{_fmt(s.get('tm_full'))}°C"),
        ("GC%",            lambda s: f"{_fmt(s.get('gc_percent'))}%"),
        ("Amplicon",       lambda s: f"{s.get('amplicon_size', '?')} bp"),
        ("Hairpin ΔG",     lambda s: _dg(s, "structure_checks", "hairpin", "dg")),
        ("Self-dimer ΔG",  lambda s: _dg(s, "structure_checks", "self_dimer", "dg")),
        ("Bound frac. binding", lambda s: f"{_fmt(s.get('scores', {}).get('bound_fraction_binding'))}"),
    ]
    cmp_data = [cmp_header] + [
        [label] + [fn(s) for s in top3 + [{}]*(3 - len(top3))]
        for label, fn in criteria
    ]
    cmp_tbl = Table(cmp_data, colWidths=[4.5*cm, 4*cm, 4*cm, 4*cm])
    cmp_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), teal),
        ("TEXTCOLOR",     (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("BACKGROUND",    (1, 1), (1, -1), teal_bg),
        ("GRID",          (0, 0), (-1, -1), 0.5, rl_colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F8FAFB")]),
    ]))
    story.append(cmp_tbl)
    story.append(Spacer(1, 0.5*cm))

    # ── Quality summary ───────────────────────────────────────────
    issues = [w for w in gw if w.get("severity") in ("critical", "warning")]
    if issues:
        story.append(Paragraph("Quality Warnings", h2))
        for w in issues:
            prefix = "⚠ Critical:" if w["severity"] == "critical" else "ℹ Warning:"
            story.append(Paragraph(f"<b>{prefix}</b> {esc(w.get('message', ''))}", body))
        story.append(Spacer(1, 0.3*cm))

    # ── Edge cases ────────────────────────────────────────────────
    criticals = [ec_item for ec_item in ec if ec_item.get("severity") in ("critical", "warning")]
    if criticals:
        story.append(Paragraph("Sequence Edge Cases", h2))
        for ec_item in criticals:
            story.append(Paragraph(f"[{esc(ec_item['code'])}] {esc(ec_item.get('message', ''))}", body))
        story.append(Spacer(1, 0.3*cm))

    # ── Validation Checklist (Phase 7 PART E) ────────────────────
    if include_checklist:
        story.extend(_build_checklist_pdf_section(results, h2, body, teal, teal_bg, rl_colors))

    # ── Footer ────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        "<i>For research use only. Validate all primers experimentally before use.</i>",
        body,
    ))
    story.append(Paragraph(
        "Sources: Chen et al. 2005 (Nucleic Acids Res.); Kramer 2011 (Curr Protoc Mol Biol); "
        "MIQE guidelines Bustin et al. 2009 (Clin Chem); SantaLucia & Hicks 2004.",
        body,
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()

    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


# ── Checklist PDF helper ──────────────────────────────────────────

def _build_checklist_pdf_section(results, h2, body, teal, teal_bg, rl_colors) -> list:
    """Build Validation Checklist PDF section (MIQE09-aligned). (Phase 7 PART E)"""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import cm

    spec = results.get("specificity_warnings", {})
    cr   = spec.get("cross_reactivity", {})
    cr_risks = [r.get("risk") for r in cr.get("cross_reactivity", [])]
    worst_family = (
        "HIGH" if "HIGH" in cr_risks or "IDENTICAL" in cr_risks
        else ("LOW" if "LOW" in cr_risks else "SAFE")
    )

    checklist_data = [
        ["Criterion", "Acceptance Target", "Reference", "Pass ☐", "Value / Notes"],
        ["No-template control (NTC)",
         "No amplification, or Cq ≥5 cycles above lowest standard",
         "MIQE09", "", ""],
        ["No-RT control",
         "No signal (excludes genomic DNA / self-priming)",
         "MIQE09", "", ""],
        ["Melting curve (SYBR Green)",
         "Single peak; no primer-dimer or non-specific product",
         "MIQE09\nVarkonyi-Gasic 2007", "", ""],
        ["Standard curve (≥5 points)",
         "10-fold serial dilutions, ≥1 log range",
         "MIQE09", "", ""],
        ["PCR efficiency",
         "90–110%  [= 10^(−1/slope) − 1]",
         "MIQE09", "", ""],
        ["R² (linearity)",
         "≥ 0.98",
         "MIQE09", "", ""],
        ["Technical replicates",
         "≥3 replicates; report Cq mean ± SD",
         "MIQE09", "", ""],
        ["Specificity (in-silico)",
         "Family cross-reactivity: reviewed. BLAST off-target: reviewed.",
         "Phase 3",
         "",
         f"Family: {worst_family}"],
    ]

    col_widths = [4.5*cm, 5.5*cm, 2.5*cm, 1.5*cm, 3*cm]
    tbl = Table(checklist_data, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), teal),
        ("TEXTCOLOR",     (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("BACKGROUND",    (0, 1), (-1, 1), teal_bg),
        ("GRID",          (0, 0), (-1, -1), 0.5, rl_colors.grey),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [rl_colors.white, rl_colors.HexColor("#F8FAFB")]),
    ]))

    return [
        Spacer(1, 0.5*cm),
        Paragraph("Validation Checklist (MIQE-aligned)", h2),
        Paragraph(
            "Complete the checklist below after wet-lab validation. "
            "Criteria per Bustin et al. 2009 (Clin Chem) MIQE guidelines.",
            body,
        ),
        Spacer(1, 0.3*cm),
        tbl,
        Spacer(1, 0.3*cm),
        Paragraph(
            "<i>Specificity (in-silico) is pre-filled from the design output. "
            "All other fields require wet-lab measurement.</i>",
            body,
        ),
    ]


# ── Helpers ───────────────────────────────────────────────────────

def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def _dg(s: dict, *keys) -> str:
    obj = s
    for k in keys:
        obj = obj.get(k, {}) if isinstance(obj, dict) else {}
    if isinstance(obj, (int, float)):
        return f"{obj:.2f}"
    return ""
