# ================================================================
# specificity_check/isomir_flag.py
# isoMiR 5'-end discrimination flag for forward primer candidates
#
# Checks whether a forward primer's 3' end falls within the region
# that varies between canonical miRNA and its known 5' isomiRs.
# This is an INFORMATIONAL WARNING only — does not affect scoring.
#
# Data: backend/data/known_5prime_isomir_mirnas.json (v1.0.0, literature-verified)
#
# Primary sources (PMIDs verified):
#   [Morin08]    PMID:18285502  doi:10.1101/gr.7179508      Genome Res 2008;18:610
#   [Neilsen12]  PMID:22883467  doi:10.1016/j.tig.2012.07.005  Trends Genet 2012;28:544
#   [Swierniak13] PMID:23783103 doi:10.1210/jc.2013-1214    J Clin Endocrinol Metab 2013;98:E1401
#
# LOGIC NOTE: in_risk_window = (forward_3prime_position <= risk_window_nt).
# For typical specific_lengths (12-17 nt), this is never True with risk_window_nt=2-3.
# The flag identifies miRNAs WHERE co-amplification risk exists; the geometric
# check is a secondary filter for pathologically short primers.
# ================================================================

import json
import os

from ..constants import (
    ISOMIR_3P_FRACTION_HIGH, ISOMIR_3P_FRACTION_MODERATE,
    ISOMIR_3P_BIAS_MIN_FRACTION, ISOMIR_3P_BIAS_MIN_IQR,
    ISOMIR_DOMINANT_RATIO, ASSAY_DCQ_RT_SHIFT_RANGE,
    OVERHANG_LENGTH_DEFAULT,
)
from .assay_model import rt_axis

_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "known_5prime_isomir_mirnas.json"
)
_DB_CACHE: dict | None = None

_DB3_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "known_3prime_isomir_mirnas.json"
)
_DB3_CACHE: dict | None = None


def check_isomir_flag(
    mirna_name: str,
    forward_3prime_position: int,
) -> dict:
    """
    Flag whether a forward primer's 3' end falls within the 5' isoMiR risk window.

    Args:
        mirna_name:              miRNA identifier, e.g. 'hsa-miR-21-5p'.
        forward_3prime_position: 1-based position of the forward primer's 3' end
                                 on the mature miRNA sequence (= specific_length,
                                 since the primer covers miRNA[0 : specific_length]).

    Returns dict with keys:
        isomir_discrimination_risk (bool), mirna_name, forward_3prime_position,
        risk_window_nt, note, data_warning.

    The forward primer 3' end falls in the risk window when its 3' position
    (= specific_length) ≤ risk_window_nt of the canonical isoMiR shift position,
    meaning the primer cannot distinguish canonical from shifted isoMiR.
    """
    db = _load_db()
    entry = _find_entry(db, mirna_name)

    if entry is None:
        return {
            "isomir_discrimination_risk": False,
            "mirna_name": mirna_name,
            "forward_3prime_position": forward_3prime_position,
            "risk_window_nt": None,
            "note": "No known 5' isomiR reported for this miRNA in the current database.",
            "data_warning": (
                "Database covers 8 well-documented human miRNAs (v1.0.0). "
                "Absence of an entry does NOT guarantee no 5' isomiRs exist — "
                "5' isomiRs are prevalent across abundant miRNAs. "
                "Sources: Morin 2008 [PMID:18285502], Neilsen 2012 [PMID:22883467]."
            ),
        }

    shift_nt    = int(entry.get("known_5prime_shift_nt", 1))
    risk_window = int(entry.get("risk_window_nt", 2))
    evidence    = entry.get("evidence_level", "unknown")

    # DB lookup only — entry found means this miRNA has documented 5' isomiRs.
    # Geometric `in_risk_window` check removed (v2.1 §6.3): for typical specific_lengths
    # (12–17 nt) the check was never True and produced confusing False negatives.
    return {
        "isomir_discrimination_risk": True,
        "mirna_name": mirna_name,
        "forward_3prime_position": forward_3prime_position,
        "known_5prime_shift_nt": shift_nt,
        "risk_window_nt": risk_window,
        "evidence_level": evidence,
        "note": (
            f"This miRNA has documented 5'-isomiRs (±{shift_nt} nt shift). "
            "Stem-loop RT-qPCR forward primers span the 5' end of the miRNA and "
            "will co-amplify canonical and shifted isomiR species."
        ),
        "co_amplification_warning": (
            f"This miRNA has documented 5'-isomiRs (±{shift_nt} nt shift). "
            "Stem-loop RT-qPCR forward primers span the 5' end of the miRNA and "
            "will co-amplify canonical and isomiR species. "
            f"Evidence level: {evidence}. "
            f"Source: {entry.get('source', 'see known_5prime_isomir_mirnas.json')}"
        ),
    }


_BIOFLUIDS = ("serum", "plasma", "urine")


def check_3prime_isomir_flag(mirna_name: str, overhang_len: int = OVERHANG_LENGTH_DEFAULT,
                             sample_type: str | None = None,
                             target_seq: str | None = None) -> dict:
    """
    How much of this miRNA exists as 3'-end isoforms (isomiRdb, audit SCI-10).
    The stem-loop RT primer pairs with the canonical 3'-terminal `overhang_len` nt.
    Variants 1 nt shorter or 1–2 nt longer, and 2 nt shorter, are captured with the
    measured delays of ASSAY_DCQ_RT_SHIFT_RANGE (a range over one or two miRNAs)
    [Schamberger14], so the signal is a capture-weighted sum of 3' isoforms, not the
    canonical form alone [Magee17]. Informational — not scored.

    sample_type: the design's sampleType. For biofluids a note says the fraction is
    a median over all isomiRdb samples, of which serum + plasma are a small share.

    target_seq: the design's mature sequence (RNA or DNA). Each top-3 variant is
    compared with it (shift_3p, relation, rt_capture — display only, not scored).
    None → the miRBase 22.1 sequence of `mirna_name`. A design sequence that differs
    from that entry is not assessed: the isomiRdb shares refer to the 22.1 3' end.
    """
    db = _load_db3()
    meta = db.get("_metadata", {})
    entry = _find_entry(db, mirna_name) if mirna_name else None
    source = meta.get("source", {})
    base = {
        "mirna_name": mirna_name,
        "overhang_len": overhang_len,
        "data_warning": meta.get("coverage_warning", ""),
        "source": f"{source.get('name', '?')} (PMID {source.get('pmid', '?')})" if source else None,
        "sample_type_note": _biofluid_note(meta, sample_type),
        "dominant_isoform_risk": False,
        "dominant_isoform_warning": None,
    }

    # Entries may carry abundance only (no 3' isoform data) — same as no data here.
    if entry is None or "median_3prime_fraction" not in entry:
        return {
            **base,
            "three_prime_isomir_risk": False,
            "level": "no_data",
            "note": (
                "No 3' isomiR data for this miRNA (isomiRdb covers human miRNAs only). "
                "Absence of data is not evidence that 3' isomiRs are absent."
            ),
            "coverage_note": "not in the 3' isomiR reference set",
        }

    f = entry["median_3prime_fraction"]
    lo, hi = entry.get("iqr_3prime_fraction", [None, None])
    level = ("high" if f >= ISOMIR_3P_FRACTION_HIGH
             else "moderate" if f >= ISOMIR_3P_FRACTION_MODERATE else "low")
    bias = _fold_change_bias_warning(mirna_name, f, lo, hi)
    summary = (
        f"In isomiRdb, a median {f:.0%} of {mirna_name} reads are 3'-end isoforms "
        f"(IQR {lo:.0%}–{hi:.0%}, {entry.get('n_samples_expressed', '?')} human samples)."
    )
    pooled = entry.get("pooled_3prime_fraction")
    canonical = round(1 - pooled, 3) if pooled is not None else None
    assessed = assess_3prime_variants(mirna_name, entry.get("top_3prime_variants", []),
                                      overhang_len, target_seq)
    dominant = _dominant_isoform_warning(mirna_name, assessed, canonical, overhang_len,
                                         base["sample_type_note"])
    return {
        **base,
        "three_prime_isomir_risk": level == "high",
        "level": level,
        "median_3prime_fraction": f,
        "iqr_3prime_fraction": [lo, hi],
        "n_samples_expressed": entry.get("n_samples_expressed"),
        "dominant_3prime_variants": assessed["variants"],
        # Reads that end at the isomiRdb reference 3' end (= miRBase 22.1 when
        # reference_status is "matches"), 5'-end variants included; pooled over samples.
        "canonical_3prime_share_pooled": canonical,
        "canonical_3prime_share_note": (
            "Pooled share of isomiRdb reads that end at the miRBase 3' end "
            "(5'-end variants included)."),
        "reference_status": assessed["reference_status"],
        "reference_note": assessed["reference_note"],
        "dominant_isoform_risk": dominant is not None,
        "dominant_isoform_warning": dominant,
        "rt_capture_impact": level,
        "fold_change_bias_risk": bias is not None,
        "fold_change_bias_warning": bias,
        "summary": summary,
        "warning": (
            summary + f" The stem-loop RT primer pairs with the canonical 3'-terminal "
            f"{overhang_len} nt, yet variants 1 nt shorter or 1–2 nt longer are detected "
            f"{_shift_phrase()} [Schamberger14]. "
            "The signal is therefore a capture-weighted sum of 3' isoforms, not the canonical "
            "form alone — here the canonical form is a minority. Report the result as the sum "
            "of isoforms [Magee17]; isoform-resolved quantification needs sequencing."
            + (" " + base["sample_type_note"] if base["sample_type_note"] else "")
        ) if level == "high" else None,
    }


# ── 3' variants vs the design sequence (display only) ─────────────
#
# Rules approved by the project owner on 2026-11-21 (docs/ISOMIR_VARIANTS_DRYRUN.md,
# counted over all 2927 variants by backend/scripts/isomir_variants_dryrun.py).
# Every capture value comes from ASSAY_DCQ_RT_SHIFT_RANGE; nothing else is quoted.

_TAIL_MAX = 3      # a divergence inside the last 3 nt of the target = a 3'-tail change
_ANCHOR = 15       # nt compared when testing a 5'-end offset
_NUM_WORD = {1: "one", 2: "two", 3: "three"}

REFERENCE_NOTES = {
    "isomirdb_reference_may_differ":
        "isomiRdb reference may differ from miRBase 22.1 — not assessed",
    "design_sequence_differs":
        "design sequence differs from miRBase 22.1 — not assessed",
}
_VARIANT_DIFFERS_NOTE = "differs from miRBase 22.1 — not assessed"
_NTA_TRIM_NOTE = (
    "Non-templated addition at the stem-side end after trimming has not been measured "
    "by qPCR; the 3.5-Ct value of Czimmerer 2013 is for an internal mismatch and does "
    "not apply.")
_NTA_EXT_NOTE = ("Non-templated addition not measured by qPCR; treated like a templated "
                 "extension of the same length.")
_OUTSIDE_NOTE = "No ΔCq measurement for end differences of 3 nt or more."
_MIXED_NOTE = ("Mixed or mismatched 3' variant (isomiRdb label mlv3p/mv); not measured "
               "by qPCR.")


def _n_mirnas(n: int) -> str:
    return f"{_NUM_WORD.get(n, n)} miRNA{'s' if n != 1 else ''} measured"


def _measured(key: str) -> str:
    """'0–4 Ct later (two miRNAs measured)' from ASSAY_DCQ_RT_SHIFT_RANGE[key]."""
    lo, hi, n = ASSAY_DCQ_RT_SHIFT_RANGE[key]
    return f"{lo:g}–{hi:g} Ct later ({_n_mirnas(n)})"


def _shift_phrase() -> str:
    """Capture of ±1/+2-nt and −2-nt variants, read from ASSAY_DCQ_RT_SHIFT_RANGE."""
    if ASSAY_DCQ_RT_SHIFT_RANGE["short1"] == ASSAY_DCQ_RT_SHIFT_RANGE["longer"]:
        return f"{_measured('short1')} and 2-nt-shorter ones {_measured('short2')}"
    return (f"{_measured('short1')} (1 nt shorter) or {_measured('longer')} (longer), and "
            f"2-nt-shorter ones {_measured('short2')}")


def _dna(s: str | None) -> str:
    return (s or "").strip().upper().replace("U", "T")


def _rna(s: str) -> str:
    return (s or "").upper().replace("T", "U")


def _parse_label(label: str | None) -> dict:
    """isomiRdb label → kind ('trimmed' lv3pT | 'extended' lv3pE | 'nta' | 'mlv3p' |
    'mv' | 'unknown') and label_shift (number after lv3p#, mlv3p# or nta#X#)."""
    parts = (label or "").split("|")
    kind = ("mv" if any(p == "mv" or p.startswith("mv#") for p in parts)
            else "mlv3p" if any(p.startswith("mlv3p") for p in parts)
            else "nta" if any(p.startswith("nta") for p in parts)
            else "trimmed" if "lv3pT" in parts
            else "extended" if "lv3pE" in parts else "unknown")
    shift = None
    for p in parts:
        bits = p.split("#")
        if bits[0] in ("lv3p", "mlv3p") and len(bits) == 2:
            shift = int(bits[1])
        elif bits[0] == "nta" and len(bits) == 3:
            shift = int(bits[2])
    return {"kind": kind, "label_shift": shift}


def _seq_relation(target: str, var: str) -> dict:
    """Variant vs target by sequence alone (DNA). seq: 'trimmed' / 'extended' / 'same'
    (full 5' prefix shared), 'tail_replaced' (diverges only in the target's last
    _TAIL_MAX nt: trimmed_nt removed, `added` appended), '5p_offset', 'internal'.
    first_diff: 1-based first target position the variant does not match (the last
    three kinds only)."""
    shift = len(var) - len(target)
    p = 0
    while p < min(len(var), len(target)) and var[p] == target[p]:
        p += 1
    if p == len(var) and shift <= 0:
        return {"seq": "trimmed" if shift < 0 else "same", "shift_3p": shift,
                "trimmed_nt": -shift, "added": ""}
    if p == len(target):
        return {"seq": "extended", "shift_3p": shift, "trimmed_nt": 0,
                "added": _rna(var[len(target):])}
    if p >= len(target) - _TAIL_MAX:
        return {"seq": "tail_replaced", "shift_3p": shift, "trimmed_nt": len(target) - p,
                "added": _rna(var[p:]), "first_diff": p + 1}
    for off in (1, -1, 2, -2, 3, -3):
        lo = max(0, -off)
        hi = min(len(target), len(var) - off, lo + _ANCHOR)
        if hi - lo >= 10 and all(var[i + off] == target[i] for i in range(lo, hi)):
            return {"seq": "5p_offset", "shift_3p": shift - off, "trimmed_nt": None,
                    "added": None, "first_diff": p + 1}
    return {"seq": "internal", "shift_3p": shift, "trimmed_nt": None, "added": None,
            "first_diff": p + 1}


def _suspect_position(lab: dict, rel: dict) -> int | None:
    """Target position (1-based) that a variant calls into question when it hints that
    isomiRdb's reference is not the target: it differs at the 5' end or inside, or a
    templated label sits on a different 3' tail. A labelled mismatch variant (mv) is
    expected to differ. None = no hint."""
    if lab["kind"] == "mv":
        return None
    if rel["seq"] in ("5p_offset", "internal") or (
            lab["kind"] in ("trimmed", "extended") and rel["seq"] == "tail_replaced"):
        return rel["first_diff"]
    return None


def _confirmed_length(lab: dict, rel: dict, target_len: int) -> int:
    """How many 5' nt of isomiRdb's reference a variant proves equal to the target.

    lv3pE#k that is the target + k nt → reference = target (all of it). lv3pT#-k that
    is the target minus its last k nt → only the first L−k nt (the reference's last k
    nt are not seen). Anything else proves nothing (0)."""
    if lab["kind"] not in ("trimmed", "extended") or rel["seq"] != lab["kind"]             or lab["label_shift"] != rel["shift_3p"]:
        return 0
    return target_len if lab["kind"] == "extended" else target_len + rel["shift_3p"]


def _capture(cls: str, label: str, note: str | None, key: str | None = None) -> dict:
    lo = hi = n = None
    if key:
        lo, hi, n = ASSAY_DCQ_RT_SHIFT_RANGE[key]
    return {"class": cls, "delta_cq_low": lo, "delta_cq_high": hi, "n_mirnas": n,
            "label": label, "note": note}


def _range_label(key: str) -> str:
    """'0–4 Ct later · n = 2 miRNAs' (table cell)."""
    lo, hi, n = ASSAY_DCQ_RT_SHIFT_RANGE[key]
    return f"{lo:g}–{hi:g} Ct later · n = {n} miRNA{'s' if n != 1 else ''}"


def _classify(target: str, var: str, lab: dict, rel: dict, overhang_len: int) -> dict:
    """relation, type_label and rt_capture of one variant (before any miRNA-level
    override). rt_axis is called only for templated shifts of at most 2 nt."""
    shift, sr = rel["shift_3p"], rel["seq"]
    if lab["kind"] in ("mlv3p", "mv", "unknown"):
        return {"relation": "other", "type_label": "other",
                "rt_capture": _capture("not_measured", "not measured", _MIXED_NOTE)}
    if sr == "same":       # only when the design sequence is not the 22.1 entry
        return {"relation": "same_as_target", "type_label": "same as design sequence",
                "rt_capture": _capture("not_assessed", "not assessed", _VARIANT_DIFFERS_NOTE)}
    if sr in ("5p_offset", "internal") or (
            lab["kind"] in ("trimmed", "extended") and sr == "tail_replaced"):
        return {"relation": "reference_mismatch", "type_label": "differs from miRBase 22.1",
                "rt_capture": _capture("not_assessed", "not assessed", _VARIANT_DIFFERS_NOTE)}
    if lab["kind"] == "nta":
        added = rel["added"]
        if sr == "tail_replaced":
            t = rel["trimmed_nt"]
            return {"relation": "nta", "added_nt": added, "trimmed_nt": t,
                    "type_label": f"−{t} nt then +{added}",
                    "rt_capture": _capture("not_measured", "not measured", _NTA_TRIM_NOTE)}
        # The label counts the non-templated nt only; a longer tail starts with
        # templated nt (e.g. nta#T#1 on +UU = +1 nt templated, then +U).
        k = lab["label_shift"]
        templ = shift - k if k and 0 < k < shift else 0
        if templ:
            added = added[templ:]
        out = {"relation": "nta", "added_nt": added, "trimmed_nt": 0,
               "type_label": (f"+{templ} nt then +{added}" if templ
                              else f"+{added} non-templated")}
        if templ:
            out["templated_nt"] = templ
        out["rt_capture"] = (
            _capture("assumed_templated",
                     f"assumed like +{shift} nt (non-templated, not measured)",
                     _NTA_EXT_NOTE, "longer")
            if 1 <= shift <= 2 else
            _capture("outside_measured_range", "not measured (≥ 3 nt)", _OUTSIDE_NOTE))
        return out
    # templated, full 5' prefix shared with the target
    relation = "trimmed" if shift < 0 else "extended"
    out = {"relation": relation, "type_label": f"{'−' if shift < 0 else '+'}{abs(shift)} nt"}
    if abs(shift) > 2:      # rt_axis only tries ±2-nt registers (8-Ct artefact beyond)
        out["rt_capture"] = _capture("outside_measured_range", "not measured (≥ 3 nt)",
                                     _OUTSIDE_NOTE)
        return out
    rt = rt_axis(target, var, overhang_len)
    if rt["shift_3p"] != shift or rt["mismatch_positions"]:
        why = []
        if rt["shift_3p"] != shift:
            why.append(f"the RT model's best register ({rt['shift_3p']:+d} nt) differs from "
                       f"the sequence shift ({shift:+d} nt)")
        if rt["mismatch_positions"]:
            why.append("mismatch in the overhang at position(s) "
                       + ", ".join(str(p) for p in rt["mismatch_positions"]))
        out["rt_capture"] = _capture("other", "not assessed",
                                     "Not assessed: " + "; ".join(why) + ".")
        return out
    key = "longer" if shift > 0 else "short1" if shift == -1 else "short2"
    out["rt_capture"] = _capture("measured_range", _range_label(key),
                                 "Measured range [Schamberger14].", key)
    return out


def _reference_sequence(mirna_name: str) -> str | None:
    """miRBase 22.1 sequence (DNA) of mirna_name, from the release behind the BLAST DB."""
    from ..mirbase_source import _entries      # lazy: mirbase_source imports this package
    hit = _entries()[0].get((mirna_name or "").strip().lower())
    return _dna(hit[1]) if hit else None


def assess_3prime_variants(mirna_name: str, variants: list, overhang_len: int,
                           target_seq: str | None = None) -> dict:
    """Each top-3 variant with its original keys (sequence_dna, label, pooled_share)
    plus shift_3p, relation (+ added_nt / trimmed_nt for NTA), type_label and
    rt_capture; and the miRNA's reference_status: 'matches' |
    'isomirdb_reference_may_differ' | 'design_sequence_differs' | 'unknown'."""
    ref = _reference_sequence(mirna_name)
    target = _dna(target_seq) if target_seq else ref
    if not target:
        return {"variants": [dict(v) for v in variants], "reference_status": "unknown",
                "reference_note": None}
    # The reference counts as confirmed only if a templated variant that matches the
    # target covers every position questioned by another variant (owner, 2026-11-21).
    out, questioned, confirmed = [], [], 0
    for v in variants:
        var = _dna(v.get("sequence_dna"))
        lab, rel = _parse_label(v.get("label")), _seq_relation(target, var)
        pos = _suspect_position(lab, rel)
        if pos is not None:
            questioned.append(pos)
        confirmed = max(confirmed, _confirmed_length(lab, rel, len(target)))
        out.append({**v, "shift_3p": rel["shift_3p"],
                    **_classify(target, var, lab, rel, overhang_len)})
    status = ("design_sequence_differs" if ref and target != ref
              else "isomirdb_reference_may_differ" if questioned and max(questioned) > confirmed
              else "matches")
    note = REFERENCE_NOTES.get(status)
    if note:                       # the table shows this one line instead
        for v in out:
            v["rt_capture"] = _capture("not_assessed", "not assessed", note)
    return {"variants": out, "reference_status": status, "reference_note": note}


def _capture_phrase(cap: dict) -> str:
    """How the RT primer is expected to capture a variant, for the warning text."""
    c = cap["class"]
    if c in ("measured_range", "assumed_templated"):
        rng = (f"{cap['delta_cq_low']:g}–{cap['delta_cq_high']:g} Ct later than the "
               f"reference form ({_n_mirnas(cap['n_mirnas'])})")
        return (f"captured {rng}" if c == "measured_range" else
                "not measured (non-templated addition); if it behaves like a templated "
                f"extension of the same length, captured {rng}")
    if c == "outside_measured_range":
        return "not measured — no qPCR data exist for 3' end differences of 3 nt or more"
    if c == "not_measured":
        return "not measured by qPCR"
    return "not assessed"


def _dominant_isoform_warning(mirna_name: str, assessed: dict, canonical: float | None,
                              overhang_len: int, sample_type_note: str | None) -> str | None:
    """Rule R2 (owner, 2026-11-21): the most common 3' isoform's pooled share is
    >= ISOMIR_DOMINANT_RATIO x the pooled share with the miRBase 22.1 3' end (3-decimal
    values; own threshold of the tool, not calibrated). Not raised when the reference
    is not assessed. Pooled shares only — never mixed with the median used elsewhere."""
    vs = assessed["variants"]
    if assessed["reference_status"] != "matches" or not vs or canonical is None:
        return None
    top = vs[0]
    if top["pooled_share"] < ISOMIR_DOMINANT_RATIO * canonical - 1e-9:
        return None
    return (
        f"Dominant 3' isoform: the most common 3' form of {mirna_name} in isomiRdb is "
        f"{top['type_label']} ({top['pooled_share']:.0%} of reads, pooled), against "
        f"{canonical:.0%} (pooled) with the miRBase 22.1 3' end. The RT primer's "
        f"{overhang_len}-nt overhang pairs with the miRBase 22.1 3' end; this isoform is "
        f"{_capture_phrase(top['rt_capture'])}. The measured value can therefore follow "
        "the reference form more than the dominant one: if the isoform mix differs between "
        "groups, the fold change can be wrong, even in direction — Pillman et al. 2019 "
        "found this for miR-221-3p and miR-27b-3p in stimulated macrophages with stem-loop "
        "TaqMan assays [Pillman KA et al. RNA 2019;25(2):232–238, PMID 30487268]. "
        "isomiRdb pools all sample types, so the isoform mix in your samples may differ."
        + (" " + sample_type_note if sample_type_note else "")
    )


# ── Internal helpers ──────────────────────────────────────────────

def _fold_change_bias_warning(mirna_name: str, f: float, lo, hi) -> str | None:
    """Warn when a shift in 3'-isoform composition could masquerade as a fold change.

    Fires on a sizeable isoform pool (median share) that also varies widely between
    samples (IQR width) — the condition under which length-selective capture turns a
    composition change into an apparent expression change [Nejad18]. Deliberately
    qualitative: no bias factor, because the per-variant capture values rest on two
    miRNAs (see ASSAY_SHIFT_EVIDENCE_NOTE).
    """
    if f < ISOMIR_3P_BIAS_MIN_FRACTION or lo is None or hi is None:
        return None
    if (hi - lo) < ISOMIR_3P_BIAS_MIN_IQR:
        return None
    return (
        f"Fold-change caution: {f:.0%} of {mirna_name} reads are 3'-end isoforms and that "
        f"share itself swings between samples (IQR {lo:.0%}–{hi:.0%}). Stem-loop RT-qPCR "
        "captures 3' isoforms selectively by length, so if a treatment, infection or disease "
        "state shifts the isoform mix, the measured fold change mixes that shift with the "
        "real change in miRNA level — Nejad et al. 2018 showed exactly this for miR-222-3p "
        "under IFN-β and for >40 miRNA families after Salmonella infection, and warned it "
        "'can lead to misinterpretation of results'. Keep the comparison qualitative, or "
        "confirm a surprising fold change by small RNA sequencing."
    )


def _biofluid_note(meta: dict, sample_type: str | None) -> str | None:
    """For serum/plasma/urine designs: the isomiRdb median pools every sample type."""
    if (sample_type or "").lower() not in _BIOFLUIDS:
        return None
    method = meta.get("method") or {}
    comp = method.get("sample_composition") or {}      # largest groups only
    total = method.get("three_prime_samples_used") or sum(v.get("used", 0) for v in comp.values())
    fluid = sum(comp.get(k, {}).get("used", 0) for k in ("serum", "plasma"))
    share = (f"serum + plasma are {fluid:,} of {total:,} samples ({fluid / total:.0%}); "
             if total else "")
    return (f"This fraction is a median over all isomiRdb samples — {share}circulating "
            "miRNAs can carry different 3' trimming and tailing, so the share in a "
            f"{sample_type.lower()} sample may differ.")


def _load_db3() -> dict:
    global _DB3_CACHE
    if _DB3_CACHE is not None:
        return _DB3_CACHE
    try:
        with open(_DB3_PATH, encoding="utf-8") as f:
            _DB3_CACHE = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _DB3_CACHE = {}
    return _DB3_CACHE


def _load_db() -> dict:
    global _DB_CACHE
    if _DB_CACHE is not None:
        return _DB_CACHE
    try:
        with open(_DB_PATH, encoding="utf-8") as f:
            _DB_CACHE = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _DB_CACHE = {}
    return _DB_CACHE


def _find_entry(db: dict, mirna_name: str) -> dict | None:
    """
    Look up mirna_name in the DB. Tries exact match first,
    then case-insensitive substring match.
    """
    # Exact match
    if mirna_name in db:
        return db[mirna_name]
    # Case-insensitive
    name_lower = mirna_name.lower()
    for key, val in db.items():
        if key.startswith("_"):
            continue
        if key.lower() == name_lower:
            return val
    return None
