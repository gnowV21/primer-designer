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
from utils.report_text import clean, fmt_dg, rule_labels

try:
    from routes import report_pdf
    _REPORTLAB_AVAILABLE = True
except ImportError:
    report_pdf = None
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
    # Tiered sets (algorithm 4.0.0, SPEC_ui_tiered_4.0.0 §2.5): the tiers get their own
    # columns and total_score is named for what it is there, the tie-break score.
    # Column titles follow the criteria groups (2026-11-22): Req_ = Required, Flex1/2/3 =
    # Flexible 1 No critical weakness / 2 PCR / 3 Composition & structure. Values and
    # column order unchanged. A V4 result keeps the V4 header (Total_Score) unchanged.
    tiered = bool(top3) and all(s.get("ranking") for s in top3)
    system = meta.get("scoring_system") or ("tiered" if tiered else "v4")
    score_cols = (["scoring_system", "grade", "grade_reasons", "Req_S1_BLAST", "Req_S2_dCq",
                   "Req_S3_Tm_margin", "Req_S_total", "Flex2_PCR", "Flex3_composition_structure",
                   "Flex1_structure", "Flex1_binding_floor", "Flex1_standard_rules", "tie_break_score"]
                  if tiered else ["Total_Score", "Grade"])
    writer.writerow([
        "Set_Rank", "Primer_Role", "Sequence", "Length_nt",
        "Tm_C", "GC_percent", "Hairpin_dG_kcalmol", "SelfDimer_dG_kcalmol",
        "Amplicon_bp", *score_cols, "Notes",
    ])
    blank_scores = [""] * len(score_cols)

    for s in top3:
        rank = s.get("rank", "?")
        sc   = s.get("structure_checks", {})
        hp   = sc.get("hairpin", {}).get("dg", "")
        sd   = sc.get("self_dimer", {}).get("dg", "")

        if tiered:
            rk = s["ranking"]
            sp = rk["specificity"]
            scores = [
                system, s.get("grade", ""), " | ".join(s.get("grade_reasons") or []),
                _lvl(sp["blast"]["score"]), _lvl(sp["assay_dcq"]["score"]),
                _lvl(sp["tm_margin"]["score"]),
                f"{sp['total']}/{sp['max']}", f"{rk['pcr']['total']}/{rk['pcr']['max']}",
                f"{rk['flexible']['total']}/{rk['flexible']['max']}",
                str(bool(rk.get("structure_veto"))), str(bool(rk.get("binding_floor_fail"))),
                " | ".join(s.get("v4_rule_violations") or []), _fmt(rk.get("detailed_score")),
            ]
        else:
            scores = [_fmt(s.get("total_score")), s.get("grade", "")]

        # Forward primer
        writer.writerow([
            rank, "Forward", s.get("sequence", ""), s.get("length", ""),
            _fmt(s.get("tm_full")), _fmt(s.get("gc_percent")),
            _dg2(hp), _dg2(sd),
            s.get("amplicon_size", ""), *scores,
            "; ".join(filter(None, [
                f"Forward-primer specific length {s.get('specific_length', '?')} nt",
                _selection_note(s),
                _ranking_note(s),
                _v4_rules_note(s),
                _isomir_note(s),
            ])),
        ])

    # RT stem-loop — same for all sets, written once
    sl_sc = sl.get("self_structure_check", {})
    writer.writerow([
        "", "RT_StemLoop", sl.get("sequence", ""), sl.get("length", ""),
        _fmt(sl.get("tm_full")), _fmt(sl.get("gc_percent")),
        _dg2(sl_sc.get("hairpin_dg")), "", "", *blank_scores,
        _rt_tm_note(sl),
    ])

    # Universal reverse — same for all sets, written once
    rev_sc = rev.get("self_structure_check", {})
    writer.writerow([
        "", "Universal_Reverse", rev.get("sequence", ""), rev.get("length", ""),
        _fmt(report_pdf.reverse_tm(results) if report_pdf else rev.get("tm")),
        _fmt(rev.get("gc_percent")),
        _dg2(rev_sc.get("hairpin_dg")), _dg2(rev_sc.get("self_dimer_dg")),
        "", *blank_scores,
        "Fixed universal reverse (Chen 2005; Kramer 2011); Tm at the design conditions",
    ])

    # ── Assay design (MIQE 2.0 §1) — the tool self-reports itself + settings ──
    buf.write("\r\n# ASSAY DESIGN (MIQE 2.0 §1: bioinformatics tool, version, settings)\r\n")
    writer.writerow(["Design_Parameter", "Value"])
    for _label, _val in report_pdf.design_rows(meta, top3):
        writer.writerow([_label, _val])
    for _label, _val in report_pdf.reproducibility_rows(meta, date.today().isoformat()):
        writer.writerow([_label, _val])

    # ── Specificity summary — its own clearly-delimited 2-column block ──
    buf.write("\r\n# SPECIFICITY SUMMARY\r\n")
    prov = _family_provenance_note(results)
    if prov:
        buf.write(f"# {prov}\r\n")
    writer.writerow(["Off_target_Metric", "Value"])
    blines = _blast_lines(blast_result)
    db = report_pdf.design_blast(results)
    if blines:
        for label, val in blines:
            writer.writerow([label, val])
    elif db.get("available"):
        writer.writerow(["BLAST off-target (design screen, rank 1)",
                         f"{db.get('overall_risk')}; {db.get('medium_hits') or 0} medium-risk hits; "
                         f"S1 level {db.get('score')} of 5"])
    else:
        writer.writerow(["BLAST off-target", "Not assessed"])

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
            writer.writerow(["three_prime_isomir_dominant_risk",
                             str(tpi.get("dominant_isoform_risk", False))])
            writer.writerow(["three_prime_canonical_share_pooled",
                             tpi.get("canonical_3prime_share_pooled", "")])
            # one row per top-3 isomiRdb variant: sequence|relation|pooled share|capture class
            for i, v in enumerate(tpi.get("dominant_3prime_variants") or [], 1):
                writer.writerow([f"three_prime_isomir_variant_{i}", "|".join(str(x) for x in (
                    v.get("sequence_dna", ""), v.get("relation", ""), v.get("pooled_share", ""),
                    (v.get("rt_capture") or {}).get("class", "")))])

    if include_checklist:
        _append_checklist_csv(writer, buf, results, blast_result)

    response = make_response(buf.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


def _append_checklist_csv(writer, buf, results: dict, blast_result=None):
    """Append the MIQE 2.0-aligned validation checklist block to the CSV [Bustin 2025].
    The in-silico specificity row reports what the design (and the optional
    'Show all hits' check) actually assessed — same text as the PDF."""
    acc, val = report_pdf.specificity_check_value(results, blast_result)
    buf.write("\r\n# VALIDATION CHECKLIST (MIQE 2.0, Bustin et al. 2025 Clin Chem 71:634)\r\n")
    buf.write("# Fill in Pass (Y/N) and Measured_Value after wet-lab validation.\r\n")
    buf.write("# For research use only. Validate primers experimentally before use.\r\n")
    writer.writerow(["Item", "Acceptance_Criterion", "Reference", "Pass", "Measured_Value"])
    checklist = [
        ("No-template control (NTC)",
         f"No amplification, or Cq ≥ {NTC_DELTA_CQ_MIN} cycles later than the latest-Cq sample",
         "HG Lab convention; reported per MIQE 2.0"),
        ("No-RT control", "No signal (excludes genomic DNA and self-priming)", "MIQE 2.0"),
        ("Melting curve (SYBR Green)", "Single peak; no primer-dimer or non-specific product",
         "MIQE 2.0; Varkonyi-Gasic 2007"),
        ("Standard curve", "≥ 5 points of 10-fold serial dilutions, ≥ 1 log range", "MIQE 2.0"),
        ("PCR efficiency (with 95% CI)", "90–110%, E = 10^(−1/slope) − 1", "MIQE 2.0"),
        ("R² (linearity)", "≥ 0.98", "MIQE 2.0"),
        ("LOD, LLOQ and ULOQ", "Determine and report the limits of detection and quantification",
         "MIQE 2.0"),
        ("Efficiency-corrected quantification",
         "Report efficiency-corrected quantities with prediction intervals; avoid ΔΔCq alone",
         "MIQE 2.0"),
        ("Reference-gene normalization",
         "≥ 2 reference genes, geometric mean, stability validated in your samples", "MIQE 2.0"),
        ("Technical replicates", "≥ 3 replicates; report Cq mean ± SD (repeatability)", "MIQE 2.0"),
        ("Reproducibility (inter-assay)", "Variation across days, operators and instruments",
         "MIQE 2.0"),
        ("Raw fluorescence data", "Deposit raw data (RDML or RDES)", "MIQE 2.0"),
    ]
    for item, crit, ref in checklist:
        writer.writerow([item, crit, ref, "", ""])
    writer.writerow(["Specificity (in silico)", acc, "In-silico design output", "", val])


# ── PDF ───────────────────────────────────────────────────────────

def _build_pdf(results: dict, filename: str, blast_result=None, include_checklist: bool = True,
               history_count: int = 0):
    pdf_bytes = report_pdf.build_pdf_bytes(results, blast_result=blast_result,
                                           include_checklist=include_checklist,
                                           history_count=history_count)
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


# ── Scientific-content helpers (shared by CSV + PDF) ──────────────

def _rt_tm_note(sl: dict) -> str:
    """
    Describe the RT stem-loop primer Tm honestly. tm_full is the DNA:DNA
    nearest-neighbor Tm of the whole 50-nt oligo (primer3) — INDICATIVE only, NOT
    the hybridization Tm of the 3' overhang with the miRNA. When available, the
    DNA:RNA overhang hybrid Tm (Sugimoto 1995) is the biologically relevant value.
    """
    parts = []
    if sl.get("tm_full") is not None:
        parts.append(f"full-primer Tm {_fmt(sl.get('tm_full'))} °C (DNA:DNA, indicative)")
    if sl.get("tm_hybrid_c") is not None:
        parts.append(f"overhang hybrid Tm {_fmt(sl.get('tm_hybrid_c'))} °C (DNA:RNA, Sugimoto 1995)")
    if sl.get("mfe") is not None:
        parts.append(f"MFE {fmt_dg(sl.get('mfe'))} kcal/mol ({sl.get('mfe_method', '')})")
    return clean("; ".join(parts))


def _isomir_note(s: dict) -> str:
    """Return an isoMiR co-amplification caveat for a set, or '' if not flagged."""
    flag = s.get("isomir_flag") or {}
    if flag.get("isomir_discrimination_risk"):
        return clean(f"isomiR co-amplification risk: {flag.get('note', 'yes')}")
    return ""


def _selection_note(s: dict) -> str:
    """How a lower-ranked set relates to the higher ones (select_diverse_top), or ''."""
    sel = s.get("selection")
    if sel == "tail_variant":
        return (f"same binding region as rank {s.get('same_binding_as_rank', '?')}, "
                f"other 5′ tail (same specificity)")
    if sel == "adjacent_3prime":
        return "3′ end 1 nt from a higher-ranked set"
    return ""


def _ranking_note(s: dict) -> str:
    """Group totals of one tiered set (Required S, Flexible P and F; SPEC §4), '' for a V4 set."""
    rk = s.get("ranking")
    if not rk:
        return ""
    sp, pcr, fx = rk["specificity"], rk["pcr"], rk["flexible"]
    note = (f"Specificity S {sp['total']}/{sp['max']} · PCR P {pcr['total']}/{pcr['max']} · "
            f"Composition & structure F {fx['total']}/{fx['max']}")
    if s.get("grade"):
        note = f"Grade {s['grade']} · " + note
    if rk.get("structure_veto"):
        note += " · secondary structure too strong"
    if rk.get("binding_floor_fail"):
        note += " · cycle-1 binding Tm < 39 °C"
    if rk.get("eliminated"):
        note += " · fails specificity (fallback)"
    return note


def _lvl(v) -> str:
    """A tier level 1–5, or 'n/a' (S1 when BLAST did not run)."""
    return "n/a" if v is None else str(v)


def _v4_rules_note(s: dict) -> str:
    """Standard primer rules (the V4 hard filters, SPEC QD 25) this set does not meet;
    '' when none or not reported."""
    v = s.get("v4_rule_violations")
    return f"Primer rules not met: {rule_labels(v)}" if v else ""


def _family_provenance_note(results: dict) -> str:
    """Clarify that seed grouping is biological context, not the primer specificity axis."""
    cr = results.get("specificity_warnings", {}).get("cross_reactivity", {})
    note = (
        "Seed-family grouping (positions 2–8) is the mRNA-targeting axis, shown for biological "
        "context only. Primer specificity is assessed on the RT 3′ overhang and the forward-primer "
        "5′ prefix (assay ΔCq rows below)."
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
                   f"{top.get('cross_reactivity_pct')}%)")
    rows = [
        ("assay_worst_label",      str(oc.get("worst_assay_label", ""))),
        ("n_co_amplified",         str(summ.get("CO-AMPLIFIED", 0))),
        ("n_partial",              str(summ.get("PARTIAL", 0))),
        ("top_off_target",         top_txt),
        ("n_same_molecule_entries", str(summ.get("shifted_5p", 0) + summ.get("shifted_3p", 0)
                                        + summ.get("same_sequence", 0))),
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

def _fmt_pct(v) -> str:
    """Occupancy %: cycle 1 is often < 1 %, so keep two decimals there."""
    if not isinstance(v, (int, float)):
        return ""
    if v < 0.01:
        return "< 0.01"
    return f"{v:.2f}" if v < 1 else f"{v:.1f}"


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def _dg2(v) -> str:
    """ΔG with 2 decimals (ASCII minus: numeric CSV column)."""
    return f"{v:.2f}" if isinstance(v, (int, float)) and not isinstance(v, bool) else ""


def _dg(s: dict, *keys) -> str:
    obj = s
    for k in keys:
        obj = obj.get(k, {}) if isinstance(obj, dict) else {}
    if isinstance(obj, (int, float)):
        return f"{obj:.2f}"
    return ""


def _cofold_dimer_dg(s: dict) -> str:
    """Worst RNAcofold (DNA, 37 °C) dimer ΔG — the hard-filter rule 1 value [Kang17]."""
    sc = s.get("structure_checks", {}) or {}
    vals = [(sc.get(k) or {}).get("dg_cofold") for k in ("self_dimer", "hetero_dimer")]
    if any(v is None for v in vals):
        return ""
    return f"{min(vals):.2f}"
