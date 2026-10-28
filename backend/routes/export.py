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

from algorithm.constants import NTC_DELTA_CQ_MIN

try:
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    )
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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
      "format": "pdf" | "csv" | "fasta",
      "results": <object /api/design returned>,
      "blast_result": <object /api/blast-check returned>   (optional),
      "include_checklist": true | false   (default: true, Phase 7 PART E)
    }
    200 → file stream (Content-Disposition: attachment)
    400 → invalid format / missing results
    503 → reportlab not installed (PDF only)
    """
    body    = request.get_json(force=True) or {}
    fmt     = (body.get("format") or "").lower().strip()
    results = body.get("results")
    blast_result = body.get("blast_result")  # optional — off-target analysis, if run
    include_checklist = body.get("include_checklist", True)
    # Prior designs of the same miRNA in this browser (IndexedDB history) — a
    # carry-over hint for the Controls section. Optional, client-supplied.
    try:
        history_count = max(0, int(body.get("history_count") or 0))
    except (TypeError, ValueError):
        history_count = 0

    # Validate format — whitelist only
    if fmt not in ("pdf", "csv", "fasta"):
        return jsonify({"error": "format must be 'pdf', 'csv' or 'fasta'"}), 400

    # Validate results structure
    if not results or not isinstance(results, dict):
        return jsonify({"error": "results object is required"}), 400
    if not results.get("top3"):
        return jsonify({"error": "results.top3 is required and must be non-empty"}), 400

    meta    = results.get("metadata", {})
    mirna_id = _sanitize(meta.get("mirna_id", "unknown"))
    ext      = "fasta" if fmt == "fasta" else fmt
    stem     = "primer_order" if fmt == "fasta" else "primer_report"
    filename = f"{stem}_{mirna_id}.{ext}"

    if fmt == "fasta":
        return _build_fasta(results, filename)
    if fmt == "csv":
        return _build_csv(results, filename, blast_result=blast_result, include_checklist=include_checklist)
    else:
        if not _REPORTLAB_AVAILABLE:
            return jsonify({
                "error": "PDF export requires 'reportlab'. Run: pip install reportlab>=4.0"
            }), 503
        return _build_pdf(results, filename, blast_result=blast_result, include_checklist=include_checklist,
                          history_count=history_count)


# ── CSV builder ───────────────────────────────────────────────────

# ── MIQE 2.0 §1 "Assay Design" self-report ────────────────────────

def _fmt_range(pair, unit=""):
    """Format a [min, max] pair like '58–62 °C', tolerant of None/missing."""
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        return "—"
    lo, hi = pair
    if lo is None and hi is None:
        return "—"
    suffix = f" {unit}" if unit else ""
    return f"{lo}{suffix}" if lo == hi else f"{lo}–{hi}{suffix}"


def _miqe_modifications(top3):
    """Report oligo modifications (e.g. LNA) if any were used (MIQE 2.0 §1)."""
    for s in (top3 or []):
        lna = s.get("lna_positions") or s.get("lna") or []
        if lna:
            return f"LNA at forward positions {lna}"
    return "None (standard DNA oligonucleotides)"


def _ions_row(ds: dict) -> str:
    """User-entered ions, or the effective values the engine used when none were given."""
    if ds.get("na_mm") is not None:
        return (f"Na+ {ds.get('na_mm')} / K+ {ds.get('k_mm') or 0} / Mg2+ {ds.get('mg_mm')} / "
                f"dNTP {ds.get('dntp_mm')}")
    ef = ds.get("effective_p3") or {}
    if not ef:
        return "—"
    return (f"monovalent {ef['mv_conc']:g} / Mg2+ {ef['dv_conc']:g} / dNTP {ef['dntp_conc']:g} "
            "(tool defaults)")


def _miqe_design_rows(meta, top3):
    """MIQE 2.0 §1 rows the design tool can self-report (reagent prep / assay design)."""
    ds = meta.get("design_settings", {}) or {}
    tool = (
        f"HG Lab Stem-loop RT-qPCR Primer Designer "
        f"(algorithm v{meta.get('algorithm_version', '?')}, "
        f"scoring {meta.get('scoring_version', 'V4')})"
    )
    ident = " · ".join(filter(None, [
        meta.get("mirna_id") or "—",
        meta.get("species") or None,
        (f"accession {meta['mirna_accession']}" if meta.get("mirna_accession") else None),
        (f"{meta.get('mirna_length')} nt" if meta.get("mirna_length") else None),
    ]))
    pv = meta.get("provenance") or {}
    engines = " · ".join(filter(None, [
        f"primer3-py {pv['primer3_py']}" if pv.get("primer3_py") else None,
        f"ViennaRNA {pv['viennarna']}" if pv.get("viennarna") else None,
        f"weights #{pv['scoring_weights_sha256']}" if pv.get("scoring_weights_sha256") else None,
        f"miRBase release {pv.get('mirbase_release', 'unknown')}" if pv else None,
    ])) or "—"
    return [
        ("Design tool + version + settings", tool),
        ("Computation engines (reproducibility)", engines),
        ("Target (symbol · species · accession · length)", ident),
        ("Detection method", str(ds.get("detection_method", "—")).upper()),
        ("RT 3' overhang (binding region)",
         f"{ds.get('rt_overhang_nt', meta.get('binding_region_nt', '?'))} nt (Chen 2005 stem-loop)"),
        ("Primer Tm target", _fmt_range(ds.get("tm_target_c"), "°C")),
        ("Primer length", _fmt_range(ds.get("primer_length_nt"), "nt")),
        ("Primer GC", _fmt_range(ds.get("gc_percent"), "%")),
        ("Amplicon length target", _fmt_range(ds.get("amplicon_bp"), "bp")),
        ("Reaction ions (mM)", _ions_row(ds)),
        ("Primer concentration",
         f"{ds['primer_nm'] if ds.get('primer_nm') is not None else (ds.get('effective_p3') or {}).get('dna_conc', '?')} nM"),
        ("Buffer pH", str(ds["buffer_ph"]) if ds.get("buffer_ph") is not None else "—"),
        ("Oligo modifications", _miqe_modifications(top3)),
        ("Planned Ta / cycles",
         f"{ds.get('annealing_temp_c') or '?'} °C / {ds.get('total_cycles') or '?'} cycles"),
        ("Efficiency acceptance", _fmt_range(ds.get("efficiency_acceptance_pct"), "%")),
        ("Quantification · reference",
         " · ".join(str(x) for x in (ds.get("quantification"), ds.get("reference")) if x) or "—"),
        ("Sample type · instrument",
         " · ".join(str(x) for x in (ds.get("sample_type"), ds.get("qpcr_instrument")) if x) or "—"),
    ]


def _build_csv(results: dict, filename: str, blast_result=None, include_checklist: bool = True):
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
            s.get("grade", ""),
            "; ".join(filter(None, [
                f"Binding region {s.get('specific_length', '?')} nt",
                _selection_note(s),
                _isomir_note(s),
            ])),
        ])

    # RT stem-loop — same for all sets, written once
    sl_sc = sl.get("self_structure_check", {})
    writer.writerow([
        "", "RT_StemLoop", sl.get("sequence", ""), sl.get("length", ""),
        _fmt(sl.get("tm_full")), _fmt(sl.get("gc_percent")),
        _fmt(sl_sc.get("hairpin_dg")), "", "", "", "",
        _rt_tm_note(sl),
    ])

    # Universal reverse — same for all sets, written once
    rev_sc = rev.get("self_structure_check", {})
    writer.writerow([
        "", "Universal_Reverse", rev.get("sequence", ""), rev.get("length", ""),
        _fmt(rev.get("tm")), _fmt(rev.get("gc_percent")),
        _fmt(rev_sc.get("hairpin_dg")), _fmt(rev_sc.get("self_dimer_dg")),
        "", "", "", "Fixed universal reverse [Chen05][K11]",
    ])

    # ── Assay design (MIQE 2.0 §1) — the tool self-reports itself + settings ──
    buf.write("\r\n# ASSAY DESIGN (MIQE 2.0 §1: bioinformatics tool, version, settings)\r\n")
    writer.writerow(["Design_Parameter", "Value"])
    for _label, _val in _miqe_design_rows(meta, top3):
        writer.writerow([_label, _val])

    # ── Specificity summary — its own clearly-delimited 2-column block ──
    buf.write("\r\n# SPECIFICITY SUMMARY\r\n")
    prov = _family_provenance_note(results)
    if prov:
        buf.write(f"# {prov}\r\n")
    writer.writerow(["Off_target_Metric", "Value"])
    blines = _blast_lines(blast_result)
    if blines:
        for label, val in blines:
            writer.writerow([label, val])
    else:
        writer.writerow([
            "BLAST off-target",
            "not assessed — run the Off-target (BLAST) check before ordering",
        ])

    # Primer-binding (RT 3'-overhang x forward 5'-prefix) collision axes — the scoring axis.
    oc_rows, _oc_interp = _overhang_axis_summary(results)
    for label, val in oc_rows:
        writer.writerow([label, val])

    # 3' isomiR capture caveat (affects the RT overhang binding site).
    tpi = results.get("stemloop_rt", {}).get("three_prime_isomir", {}) or {}
    if tpi:
        writer.writerow(["three_prime_isomir_risk", str(tpi.get("three_prime_isomir_risk", False))])
        writer.writerow(["three_prime_isomir_level", str(tpi.get("level", "n/a"))])
        if tpi.get("median_3prime_fraction") is not None:
            writer.writerow(["three_prime_isomir_median_fraction", tpi["median_3prime_fraction"]])
            writer.writerow(["three_prime_isomir_source", tpi.get("source", "")])

    if include_checklist:
        _append_checklist_csv(writer, buf, results, blast_result)

    response = make_response(buf.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


def _append_checklist_csv(writer, buf, results: dict, blast_result=None):
    """Append MIQE 2.0-aligned validation checklist block to CSV. [Bustin 2025]"""
    # Auto-fill specificity data from results
    spec = results.get("specificity_warnings", {})
    cr   = spec.get("cross_reactivity", {})
    cr_risks = [r.get("risk") for r in cr.get("cross_reactivity", [])]
    worst_family_risk = (
        "HIGH" if "HIGH" in cr_risks or "IDENTICAL" in cr_risks
        else ("LOW" if "LOW" in cr_risks else "SAFE")
    )
    # Fill in the BLAST off-target risk if the check was run and passed in.
    _bsumm = (blast_result or {}).get("summary", {}) if isinstance(blast_result, dict) else {}
    blast_risk = _bsumm.get("overall_risk", "")

    buf.write("\r\n# VALIDATION CHECKLIST (MIQE 2.0-aligned, Bustin et al. 2025 Clin Chem 71:634)\r\n")
    buf.write("# Fill in Pass (Y/N) and Measured_Value after wet-lab validation.\r\n")
    buf.write("# For research use only. Validate primers experimentally before use.\r\n")
    writer.writerow(["Item", "Acceptance_Criterion", "Reference", "Pass", "Measured_Value"])

    checklist = [
        (
            "No-template control (NTC)",
            f"No amplification, or Cq ≥{NTC_DELTA_CQ_MIN} cycles later than the latest-Cq sample",
            "HG Lab convention; reporting per MIQE 2.0",
            "",
            "",
        ),
        (
            "No-RT control",
            "No signal (confirms absence of genomic DNA / self-priming)",
            "MIQE 2.0",
            "",
            "",
        ),
        (
            "Melting curve (SYBR Green)",
            "Single peak; no primer-dimer or non-specific product",
            "MIQE 2.0, Varkonyi-Gasic 2007",
            "",
            "",
        ),
        (
            "Standard curve",
            "≥5 dilution points, ≥1 log range (10-fold serial dilutions)",
            "MIQE 2.0",
            "",
            "",
        ),
        (
            "PCR efficiency (report with CI)",
            "90–110%  [E = 10^(−1/slope) − 1]; report ±95% confidence interval",
            "MIQE 2.0",
            "",
            "",
        ),
        (
            "R² (linearity)",
            "≥ 0.98",
            "MIQE 2.0",
            "",
            "",
        ),
        (
            "LOD and LLOQ/ULOQ (dynamic range)",
            "Determine and report LOD, lower/upper limits of quantification",
            "MIQE 2.0",
            "",
            "",
        ),
        (
            "Efficiency-corrected quantification",
            "Report efficiency-corrected quantities with prediction intervals; avoid Cq/ΔΔCq alone",
            "MIQE 2.0",
            "",
            "",
        ),
        (
            "Reference-gene normalization",
            "≥2 reference genes, geometric-mean normalization, stability validated in-context",
            "MIQE 2.0",
            "",
            "",
        ),
        (
            "Technical replicates",
            "≥3 replicates; report Cq mean and SD (repeatability)",
            "MIQE 2.0",
            "",
            "",
        ),
        (
            "Reproducibility (inter-assay)",
            "Report variation across days / operators / instruments",
            "MIQE 2.0",
            "",
            "",
        ),
        (
            "Raw fluorescence data",
            "Deposit/submit raw fluorescence data (RDML or RDES format)",
            "MIQE 2.0",
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

def _seq_with_seed_markup(seq: str) -> str:
    """Reportlab markup for a mature miRNA sequence with the seed (nt 2-8) picked
    out in brand teal bold — the app's signature visual motif. Seed = positions
    2-8 from the 5' end (0-indexed 1:8), which define target recognition."""
    seq = _html.escape(str(seq))
    if len(seq) < 8:
        return f"<font name='Courier'>{seq}</font>"
    pre, seed, post = seq[:1], seq[1:8], seq[8:]
    return (
        f"<font name='Courier'>{pre}"
        f"<font color='{_TEAL}'><b>{seed}</b></font>{post}</font>"
    )


def _build_pdf(results: dict, filename: str, blast_result=None, include_checklist: bool = True,
               history_count: int = 0):
    from reportlab.lib import colors as rl_colors
    teal     = rl_colors.HexColor(_TEAL)
    teal_bg  = rl_colors.HexColor(_TEAL_BG)

    meta  = results.get("metadata", {})
    top3  = results.get("top3", [])
    sl    = results.get("stemloop_rt", {})
    rev   = results.get("universal_reverse", {})
    gw    = results.get("global_warnings", [])
    ec    = results.get("edge_cases", [])
    pa    = results.get("protocol_advice", [])

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
        f"Sequence 5′→3′: {_seq_with_seed_markup(meta.get('mirna_sequence', ''))} "
        f"&nbsp;<font size=7 color='#64748B'>(seed nt 2-8 highlighted)</font>",
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

        # Wrap sequence cells in a mono Paragraph so long (50-nt) strings wrap
        # inside the cell instead of overflowing into the next column.
        seq_cell = ParagraphStyle("seqcell", fontName="Courier", fontSize=7, leading=8.5, wordWrap="CJK")
        def _sq(x):
            return Paragraph(esc(str(x or "")), seq_cell)
        seq_table_data = [
            ["Role", "Sequence (5′→3′)", "Length", "Tm", "GC%"],
            ["Forward", _sq(best.get("sequence", "")), f"{best.get('length', '?')} nt",
             f"{_fmt(best.get('tm_full'))}°C", f"{_fmt(best.get('gc_percent'))}%"],
            ["RT Stem-loop", _sq(sl.get("sequence", "")), f"{sl.get('length', '?')} nt",
             f"{_fmt(sl.get('tm_full'))}°C", f"{_fmt(sl.get('gc_percent'))}%"],
            ["Universal Reverse", _sq(rev.get("sequence", "")), f"{rev.get('length', '?')} nt",
             f"{_fmt(rev.get('tm'))}°C", f"{_fmt(rev.get('gc_percent'))}%"],
        ]
        col_widths = [3.3*cm, 7.7*cm, 1.8*cm, 2.2*cm, 1.5*cm]
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
        story.append(Spacer(1, 0.3*cm))

        # Scientific caveats a reader must not miss (mirror the app's careful labelling)
        notes = []
        rt_note = _rt_tm_note(sl)
        if rt_note:
            notes.append(
                f"<b>RT stem-loop Tm:</b> {rt_note}. The full-primer Tm is DNA:DNA and "
                f"INDICATIVE only — it is not the overhang:miRNA hybridization Tm and is "
                f"not used in scoring."
            )
        iso = _isomir_note(best)
        if iso:
            notes.append(f"<b>{esc(iso)}</b>")
        tpi = sl.get("three_prime_isomir") or {}
        if tpi.get("warning") or tpi.get("summary"):
            # 3' isomiRs (isomiRdb): a warning when the canonical 3' form is a minority.
            text = tpi.get("warning") or tpi.get("summary")
            notes.append(f"<b>3' isomiRs:</b> {esc(text)} Source: {esc(str(tpi.get('source', '')))}.")
        oc_rows, oc_interp = _overhang_axis_summary(results)
        if oc_interp:
            oc = results.get("specificity_warnings", {}).get("overhang_collision", {})
            worst = oc.get("worst_assay_label", "")
            summ = oc.get("summary", {})
            notes.append(
                f"<b>Assay specificity (ΔCq model):</b> worst other miRNA {esc(str(worst))}; "
                f"{summ.get('CO-AMPLIFIED', 0)} co-amplified, {summ.get('PARTIAL', 0)} partial; "
                f"{summ.get('isomir_5p', 0) + summ.get('isomir_3p', 0) + summ.get('identical', 0)} "
                f"isomiR/identical entr(ies) not scored. {esc(oc_interp)}"
            )
        prov = _family_provenance_note(results)
        if prov:
            notes.append(esc(prov))
        if notes:
            story.append(Paragraph("Scientific notes", h3))
            for n in notes:
                story.append(Paragraph(f"• {n}", body))
        story.append(Spacer(1, 0.4*cm))

    # ── Comparison table (Tab A summary) ─────────────────────────
    story.append(Paragraph("Primer Set Comparison", h2))
    cmp_header = ["Criterion"] + [f"Rank {i + 1}" for i in range(len(top3))]
    criteria = [
        ("Total score",    lambda s: f"{_fmt(s.get('total_score'))} ({s.get('grade', '')})"),
        ("Forward Tm",     lambda s: f"{_fmt(s.get('tm_full'))}°C"),
        ("GC%",            lambda s: f"{_fmt(s.get('gc_percent'))}%"),
        ("Amplicon",       lambda s: f"{s.get('amplicon_size', '?')} bp"),
        ("Binding region", lambda s: f"{s.get('specific_length', '?')} nt"
                                     + (f" — {_selection_note(s)}" if _selection_note(s) else "")),
        ("Hairpin ΔG",     lambda s: _dg(s, "structure_checks", "hairpin", "dg")),
        ("Self-dimer ΔG",  lambda s: _dg(s, "structure_checks", "self_dimer", "dg_overall")),
        ("Cycle-1 occupancy % (Ta)", lambda s: f"{_fmt(s.get('scores', {}).get('bound_fraction_binding_pct'))}"),
    ]
    cmp_data = [cmp_header] + [
        [label] + [fn(s) for s in top3]
        for label, fn in criteria
    ]
    cmp_tbl = Table(cmp_data, colWidths=[4.5*cm] + [4*cm] * len(top3))
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

    # ── Assay design (MIQE 2.0 §1) — the tool self-reports itself + settings ──
    from reportlab.lib.styles import ParagraphStyle as _PS
    _dcell = _PS("miqedesign", parent=body, fontSize=8, leading=10)
    story.append(Paragraph("Assay Design (MIQE 2.0 §1)", h2))
    dr_data = [["Parameter", "Value"]] + [
        [Paragraph(e(lbl), _dcell), Paragraph(e(val), _dcell)]
        for lbl, val in _miqe_design_rows(meta, top3)
    ]
    dr_tbl = Table(dr_data, colWidths=[6.5*cm, 9.5*cm])
    dr_tbl.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0), teal),
        ("TEXTCOLOR",      (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",       (0, 0), (-1, 0), 9),
        ("GRID",           (0, 0), (-1, -1), 0.5, rl_colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F8FAFB")]),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(dr_tbl)
    story.append(Paragraph(
        "<i>Self-reported by the design tool for MIQE 2.0 §1 (Reagent preparation / "
        "assay design). Manufacturer of oligonucleotides and optimization details are "
        "supplied by the user.</i>", body,
    ))
    story.append(Spacer(1, 0.4*cm))

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

    # ── Off-target specificity (BLAST) ───────────────────────────
    story.append(Paragraph("Off-target Specificity (BLAST)", h2))
    blines = _blast_lines(blast_result)
    if blines:
        bl_data = [["Metric", "Value"]] + [[e(lbl), e(val)] for lbl, val in blines]
        bl_tbl = Table(bl_data, colWidths=[7*cm, 5*cm])
        bl_tbl.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0), teal),
            ("TEXTCOLOR",      (0, 0), (-1, 0), rl_colors.white),
            ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, -1), 9),
            ("GRID",           (0, 0), (-1, -1), 0.5, rl_colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F8FAFB")]),
        ]))
        story.append(bl_tbl)
        story.append(Paragraph(
            "<i>Overall risk reflects OUT-of-family off-targets only. Same-family "
            "cross-reactivity is expected for this miRNA family and is assessed "
            "separately (family cross-reactivity).</i>",
            body,
        ))
    else:
        story.append(Paragraph(
            "Not assessed. Run the Off-target (BLAST) check on the Results page, then "
            "re-export to include the analysis in this report.",
            body,
        ))
    story.append(Spacer(1, 0.4*cm))

    # ── Protocol Advisor (moved off the results page into the report) ──
    if pa:
        story.append(Paragraph("Protocol Advisor", h2))
        story.append(Paragraph(
            "<i>Evidence-backed protocol suggestions based on your assay parameters. "
            "Descriptive only — validate experimentally before use.</i>", body))
        for item in pa:
            match = str(item.get("match", "")).upper()
            iid   = esc(str(item.get("id", "")))
            title = esc(str(item.get("title", "")))
            rec   = esc(str(item.get("recommendation", "")))
            head  = f"<b>[{iid}] {title}</b>" + (f" — {match} match" if match else "")
            story.append(Paragraph(head, body))
            if rec:
                story.append(Paragraph(rec, body))
            doi = item.get("doi") or item.get("source_doi")
            if doi:
                story.append(Paragraph(f"<i>doi:{esc(str(doi))}</i>", body))
        story.append(Spacer(1, 0.4*cm))

    # ── Controls & Contamination (audit SCI-11) ──────────────────
    if results.get("controls_advice"):
        story.extend(_build_controls_pdf_section(
            results["controls_advice"], history_count, h2, h3, body, teal, rl_colors))

    # ── Validation Checklist (Phase 7 PART E) ────────────────────
    if include_checklist:
        story.extend(_build_checklist_pdf_section(results, h2, body, teal, teal_bg, rl_colors, blast_result))

    # ── Footer ────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        "<i>For research use only. Validate all primers experimentally before use.</i>",
        body,
    ))
    story.append(Paragraph(
        "Sources: Chen et al. 2005 (Nucleic Acids Res.); Kramer 2011 (Curr Protoc Mol Biol); "
        "MIQE 2.0 guidelines Bustin et al. 2025 (Clin Chem 71:634); SantaLucia & Hicks 2004.",
        body,
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()

    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


# ── Controls & contamination PDF helper (audit SCI-11) ───────────

def _build_controls_pdf_section(ca, history_count, h2, h3, body, teal, rl_colors) -> list:
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle

    esc = _html.escape
    cell = ParagraphStyle("ctlcell", fontName="Helvetica", fontSize=8, leading=9.5)
    P = lambda t: Paragraph(esc(str(t)), cell)  # noqa: E731

    rows = [["Control", "Set-up", "Checks", "Pass criterion"]] + [
        [P(c["name"]), P(c["setup"]), P(c["checks"]), P(c["pass"])] for c in ca.get("controls", [])
    ]
    tbl = Table(rows, colWidths=[3*cm, 5.6*cm, 4.2*cm, 4.2*cm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), teal),
        ("TEXTCOLOR",  (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("GRID",       (0, 0), (-1, -1), 0.5, rl_colors.grey),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
    ]))

    cont = ca.get("contamination", {})
    reasons = cont.get("reasons", [])
    risk = "ELEVATED" if reasons else "standard"

    out = [
        Spacer(1, 0.5*cm),
        Paragraph("Controls &amp; Contamination", h2),
        Paragraph("Run these controls on every plate. NTC and no-RT results must be reported "
                  "(MIQE 2.0, Bustin et al. 2025).", body),
        Spacer(1, 0.2*cm),
        tbl,
    ]
    if ca.get("melt_note"):
        out += [Spacer(1, 0.2*cm), Paragraph(esc(ca["melt_note"]), body)]
    out += [
        Spacer(1, 0.3*cm),
        Paragraph(f"Contamination risk: <b>{risk}</b>", h3),
    ]
    for r in reasons:
        out.append(Paragraph("• " + esc(r), body))
    if not reasons:
        out.append(Paragraph(f"No specific risk factor found (abundance data: "
                             f"{esc(cont.get('abundance_data', 'n/a'))}).", body))
    if history_count:
        # Designing is not amplifying, so this is a prompt, not a risk factor.
        out.append(Paragraph(
            f"<i>Note: this miRNA was designed {history_count} time(s) before in this browser. "
            "If its amplicon has already been made in the lab, amplicon carry-over is the most "
            "common cause of a positive NTC.</i>", body))
    out.append(Paragraph("<b>Precautions</b>", body))
    for pr in cont.get("precautions", []):
        out.append(Paragraph("• " + esc(pr), body))
    return out


# ── Checklist PDF helper ──────────────────────────────────────────

def _build_checklist_pdf_section(results, h2, body, teal, teal_bg, rl_colors, blast_result=None) -> list:
    """Build Validation Checklist PDF section (MIQE 2.0-aligned). (Phase 7 PART E)"""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle

    _cell = ParagraphStyle("chkcell", fontName="Helvetica", fontSize=8, leading=9.5)
    def _P(t):
        return Paragraph(_html.escape(str(t)).replace("\n", "<br/>"), _cell)

    spec = results.get("specificity_warnings", {})
    cr   = spec.get("cross_reactivity", {})
    cr_risks = [r.get("risk") for r in cr.get("cross_reactivity", [])]
    worst_family = (
        "HIGH" if "HIGH" in cr_risks or "IDENTICAL" in cr_risks
        else ("LOW" if "LOW" in cr_risks else "SAFE")
    )
    _bsumm = (blast_result or {}).get("summary", {}) if isinstance(blast_result, dict) else {}
    blast_risk = _bsumm.get("overall_risk", "")
    spec_value = f"Family: {worst_family}" + (f" · BLAST: {blast_risk}" if blast_risk else "")

    checklist_data = [
        ["Criterion", "Acceptance Target", "Reference", "Pass ☐", "Value / Notes"],
        ["No-template control (NTC)",
         f"No amplification, or Cq ≥{NTC_DELTA_CQ_MIN} cycles later than the latest-Cq sample",
         "HG Lab convention; reporting per MIQE 2.0", "", ""],
        ["No-RT control",
         "No signal (excludes genomic DNA / self-priming)",
         "MIQE 2.0", "", ""],
        ["Melting curve (SYBR Green)",
         "Single peak; no primer-dimer or non-specific product",
         "MIQE 2.0\nVarkonyi-Gasic 2007", "", ""],
        ["Standard curve (≥5 points)",
         "10-fold serial dilutions, ≥1 log range",
         "MIQE 2.0", "", ""],
        ["PCR efficiency (report with CI)",
         "90–110%  [E = 10^(−1/slope) − 1]; ±95% CI",
         "MIQE 2.0", "", ""],
        ["R² (linearity)",
         "≥ 0.98",
         "MIQE 2.0", "", ""],
        ["LOD and LLOQ/ULOQ",
         "Determine + report LOD and limits of quantification (dynamic range)",
         "MIQE 2.0", "", ""],
        ["Efficiency-corrected quantification",
         "Report efficiency-corrected quantities + prediction intervals; avoid ΔΔCq alone",
         "MIQE 2.0", "", ""],
        ["Reference-gene normalization",
         "≥2 reference genes, geometric-mean, validated in-context",
         "MIQE 2.0", "", ""],
        ["Technical replicates (repeatability)",
         "≥3 replicates; report Cq mean ± SD",
         "MIQE 2.0", "", ""],
        ["Reproducibility (inter-assay)",
         "Variation across days / operators / instruments",
         "MIQE 2.0", "", ""],
        ["Raw fluorescence data",
         "Deposit/submit raw data (RDML or RDES)",
         "MIQE 2.0", "", ""],
        ["Specificity (in-silico)",
         "Family cross-reactivity: reviewed. BLAST off-target: reviewed.",
         "Phase 3",
         "",
         spec_value],
    ]

    # Wrap the long text columns in Paragraphs so they wrap inside the cell
    # rather than overflowing into (and overprinting) the neighbouring column.
    wrapped = [checklist_data[0]] + [
        [row[0], _P(row[1]), _P(row[2]), row[3], _P(row[4])]
        for row in checklist_data[1:]
    ]
    col_widths = [4*cm, 5.5*cm, 2.7*cm, 1.3*cm, 3.5*cm]
    tbl = Table(wrapped, colWidths=col_widths)
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
        Paragraph("Validation Checklist (MIQE 2.0-aligned)", h2),
        Paragraph(
            "Complete the checklist below after wet-lab validation. "
            "Criteria per the MIQE 2.0 guidelines (Bustin et al. 2025, Clin Chem 71:634).",
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


# ── Scientific-content helpers (shared by CSV + PDF) ──────────────

def _rt_tm_note(sl: dict) -> str:
    """
    Describe the RT stem-loop primer Tm honestly. tm_full is the DNA:DNA
    nearest-neighbor Tm of the whole 50-nt oligo (primer3) — INDICATIVE only, NOT
    the hybridization Tm of the 6-nt overhang with the miRNA. When available, the
    DNA:RNA overhang hybrid Tm (Sugimoto 1995) is the biologically relevant value.
    """
    parts = []
    if sl.get("tm_full") is not None:
        parts.append(f"full-primer Tm {_fmt(sl.get('tm_full'))}°C (DNA:DNA, indicative)")
    if sl.get("tm_hybrid_c") is not None:
        parts.append(f"overhang hybrid Tm {_fmt(sl.get('tm_hybrid_c'))}°C (DNA:RNA, Sugimoto 1995)")
    if sl.get("mfe") is not None:
        parts.append(f"MFE {_fmt(sl.get('mfe'))} kcal/mol ({sl.get('mfe_method', '')})")
    return "; ".join(parts)


def _isomir_note(s: dict) -> str:
    """Return an isoMiR co-amplification caveat for a set, or '' if not flagged."""
    flag = s.get("isomir_flag") or {}
    if flag.get("isomir_discrimination_risk"):
        return f"isoMiR co-amplification risk: {flag.get('note', 'yes')}"
    return ""


def _selection_note(s: dict) -> str:
    """How a lower-ranked set relates to the higher ones (select_diverse_top), or ''."""
    sel = s.get("selection")
    if sel == "tail_variant":
        return (f"same binding region as rank {s.get('same_binding_as_rank', '?')}, "
                f"other 5' tail (same specificity)")
    if sel == "adjacent_3prime":
        return "3' end 1 nt from a higher-ranked set"
    return ""


def _family_provenance_note(results: dict) -> str:
    """Clarify that seed grouping is biological context, not the primer specificity axis."""
    cr = results.get("specificity_warnings", {}).get("cross_reactivity", {})
    note = (
        "Seed-family grouping (positions 2-8) is the mRNA-targeting axis, shown for biological "
        "context only. Primer specificity is assessed on the RT 3'-overhang and forward 5'-prefix "
        "axes (see the primer-binding specificity summary)."
    )
    base = cr.get("data_warning", "") or ""
    return f"{note} {base}".strip()


def _overhang_axis_summary(results: dict):
    """Return ([(label, value), ...], interpretation) for the assay-level ΔCq screen."""
    oc = results.get("specificity_warnings", {}).get("overhang_collision", {}) or {}
    if not oc:
        return [], ""
    summ = oc.get("summary", {})
    top = next(iter(oc.get("collisions", [])), None)
    top_txt = "none"
    if top and top.get("assay_label") != "DISCRIMINATED":
        top_txt = (f"{top.get('mirna')} (ΔCq {top.get('delta_cq')}, "
                   f"{top.get('cross_reactivity_pct')} %)")
    rows = [
        ("assay_worst_label",      str(oc.get("worst_assay_label", ""))),
        ("n_co_amplified",         str(summ.get("CO-AMPLIFIED", 0))),
        ("n_partial",              str(summ.get("PARTIAL", 0))),
        ("top_off_target",         top_txt),
        ("n_isomir_or_identical",  str(summ.get("isomir_5p", 0) + summ.get("isomir_3p", 0)
                                       + summ.get("identical", 0))),
    ]
    return rows, oc.get("interpretation", "")


def _blast_lines(blast_result) -> list[tuple[str, str]]:
    """
    Flatten a /api/blast-check result into (label, value) rows. Returns [] when no
    BLAST was run so callers can render a clear "not assessed" placeholder instead.
    """
    if not isinstance(blast_result, dict):
        return []
    summ = blast_result.get("summary", {}) or {}
    return [
        ("Overall off-target risk", str(summ.get("overall_risk", "?"))),
        ("Critical (out-of-family)", str(summ.get("critical_count", 0))),
        ("High",                     str(summ.get("high_risk_count", 0))),
        ("Medium",                   str(summ.get("medium_risk_count", 0))),
        ("Same-family (expected)",   str(summ.get("same_family_count", 0))),
        ("Cross-species excluded",   str(summ.get("cross_species_excluded", 0))),
    ]


# ── FASTA builder (order-ready) ───────────────────────────────────

def _build_fasta(results: dict, filename: str):
    """
    Clean, synthesis-order-ready FASTA of the three primers. One record per
    forward primer (all ranked sets) plus the shared RT stem-loop and universal
    reverse primer. Sequences are DNA 5'→3' exactly as ordered.
    """
    meta = results.get("metadata", {})
    top3 = results.get("top3", [])
    sl   = results.get("stemloop_rt", {})
    rev  = results.get("universal_reverse", {})
    mid  = _sanitize(meta.get("mirna_id", "unknown"))

    lines = [
        f"; HG Lab Stem-loop RT-qPCR primers for {meta.get('mirna_id', 'unknown')}",
        f"; algorithm v{meta.get('algorithm_version', '?')} · exported {date.today().isoformat()}",
        "; DNA 5'->3', ready to order. For research use only — validate experimentally.",
    ]
    for s in top3:
        seq = (s.get("sequence") or "").strip()
        if seq:
            lines.append(f">{mid}_Forward_rank{s.get('rank', '?')} len={s.get('length', len(seq))} Tm={_fmt(s.get('tm_full'))}C")
            lines.append(seq)
    if sl.get("sequence"):
        lines.append(f">{mid}_RT_StemLoop len={sl.get('length', '')}")
        lines.append(sl.get("sequence").strip())
    if rev.get("sequence"):
        lines.append(f">Universal_Reverse len={rev.get('length', '')} [Chen05][Kramer11]")
        lines.append(rev.get("sequence").strip())

    response = make_response("\n".join(lines) + "\n")
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


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
