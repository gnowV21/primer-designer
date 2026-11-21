"""
Dry-run for the isomiR display task (docs/PROMPT_isomir_variants_4.0.0.md, Part 1).

Read-only: loads data/known_3prime_isomir_mirnas.json (isomiRdb) and the local
miRBase 22.1 lookup database (db/mirbase.db, the one /api/mirbase serves), and
compares every top-3 3' variant with the 22.1 sequence. No design is run and no
module of the web app is changed; rt_axis and check_3prime_isomir_flag are only
called.

  1.1  3' shift from the sequence (shared 5' prefix) vs the isomiRdb label
  1.2  variants per RT-capture class (Part 2.1 as approved on 2026-11-21)
  1.3  |shift| > 2 nt: what rt_axis returns today (the ±2-nt register artefact)
  1.4  dominant-isoform rules R1 (top > canonical) and R2 (top >= 0.8 x canonical)
  1.5  the nine published cases
  plus the register check of rt_axis at overhang 5, 6 and 7 nt, the miRNAs whose
  isomiRdb reference may differ from 22.1, and a reconciliation of every count.

Approved rules (owner, 2026-11-21):
  - R2 on the 3-decimal values: top-1 pooled share >= 0.8 x canonical 3' share;
    0.8 is an own threshold of the tool, not calibrated.
  - trimmed then non-templated addition: relation "nta" + trimmed_nt, class
    not_measured (no rt_axis call).
  - mlv3p / mv: relation "other", class not_measured.
  - miRNA whose isomiRdb reference may differ from 22.1 (a variant differs at the
    5' end / inside, and no lv3pT/lv3pE variant that matches 22.1 exactly covers the
    questioned position — option B, tightened on 2026-11-21):
    no dominant-isoform warning; every variant not_assessed (the table shows one line).
  - any other variant differing from 22.1 at the 5' end or inside: relation
    "reference_mismatch", class not_assessed.

Usage (from backend/):
  python scripts/isomir_variants_dryrun.py
Writes ../benchmark/isomir_variants_dryrun.json.
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)

from db import local_db                                                   # noqa: E402
from algorithm.constants import ASSAY_DCQ_RT_SHIFT_RANGE                  # noqa: E402
from algorithm.specificity_check.assay_model import rt_axis              # noqa: E402
from algorithm.specificity_check.isomir_flag import (                     # noqa: E402
    check_3prime_isomir_flag, _load_db3)

OVERHANG = 6
OVERHANGS = (5, 6, 7)
R2_FACTOR = 0.8          # own threshold of the tool, not calibrated
EPS = 1e-9               # float guard for the >= on 3-decimal values
OUT = os.path.join(os.path.dirname(BACKEND), "benchmark", "isomir_variants_dryrun.json")
CASES = ["hsa-miR-21-5p", "hsa-miR-33b-5p", "hsa-miR-877-5p", "hsa-miR-222-3p",
         "hsa-miR-221-3p", "hsa-miR-27b-3p", "hsa-miR-27a-3p", "hsa-miR-107",
         "hsa-miR-30a-5p"]
TAIL_MAX = 3      # a divergence inside the last 3 nt of the 22.1 sequence = 3'-tail change
ANCHOR = 15       # nt compared when testing a 5' offset
CLASSES = ("measured_range", "assumed_templated", "outside_measured_range",
           "not_measured", "other", "not_assessed")


def to_rna(s: str) -> str:
    return s.upper().replace("T", "U")


def parse_label(label: str) -> dict:
    """isomiRdb label → {kind, label_shift, nta_base}.

    kind: 'trimmed' (lv3pT) | 'extended' (lv3pE) | 'nta' | 'mlv3p' | 'mv' (any
    label with a mismatch tag) | 'unknown'. label_shift: the signed number after
    lv3p# (templated), the count after nta#X# (non-templated) or after mlv3p#."""
    parts = label.split("|")
    out = {"kind": "unknown", "label_shift": None, "nta_base": None}
    if any(p == "mv" or p.startswith("mv#") for p in parts):
        out["kind"] = "mv"
    elif any(p.startswith("mlv3p") for p in parts):
        out["kind"] = "mlv3p"
    elif any(p.startswith("nta") for p in parts):
        out["kind"] = "nta"
    elif "lv3pT" in parts:
        out["kind"] = "trimmed"
    elif "lv3pE" in parts:
        out["kind"] = "extended"
    for p in parts:
        bits = p.split("#")
        if bits[0] in ("lv3p", "mlv3p") and len(bits) == 2:
            out["label_shift"] = int(bits[1])
        if bits[0] == "nta" and len(bits) == 3:
            out["nta_base"] = to_rna(bits[1])
            out["label_shift"] = int(bits[2])
    return out


def _lcp(a: str, b: str) -> int:
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return i


def seq_relation(target: str, var: str) -> dict:
    """3' shift from the sequences alone (DNA alphabet).

    seq_relation:
      trimmed / extended / same  — the variant shares the full 5' prefix with 22.1
      tail_replaced              — diverges only in the last TAIL_MAX nt of 22.1:
                                   trimmed_nt removed, then added_nt appended
      5p_offset                  — 5' end differs from 22.1 (offset r, r>0: extra 5' nt)
      internal_mismatch          — differs from 22.1 inside the sequence
    The last three are the 'prefix mismatch' cases of Part 1.1."""
    shift = len(var) - len(target)
    p = _lcp(target, var)
    if p == len(var) and shift <= 0:
        return {"seq_relation": "trimmed" if shift < 0 else "same", "shift_3p": shift,
                "trimmed_nt": -shift, "added": ""}
    if p == len(target):
        return {"seq_relation": "extended", "shift_3p": shift, "trimmed_nt": 0,
                "added": to_rna(var[len(target):])}
    if p >= len(target) - TAIL_MAX:
        return {"seq_relation": "tail_replaced", "shift_3p": shift,
                "trimmed_nt": len(target) - p, "added": to_rna(var[p:])}
    for off in (1, -1, 2, -2, 3, -3):
        lo = max(0, -off)
        hi = min(len(target), len(var) - off, lo + ANCHOR)
        if hi - lo >= 10 and all(var[i + off] == target[i] for i in range(lo, hi)):
            return {"seq_relation": "5p_offset", "offset_5p": off,
                    "shift_3p": shift - off, "trimmed_nt": None, "added": None}
    return {"seq_relation": "internal_mismatch", "shift_3p": shift, "trimmed_nt": None,
            "added": None, "first_mismatch_pos_1based": p + 1}


PREFIX_MISMATCH = ("tail_replaced", "5p_offset", "internal_mismatch")


def reference_suspect_reason(lab: dict, rel: dict) -> str | None:
    """Why this variant suggests that isomiRdb's reference is not the 22.1 sequence.

    A labelled mismatch variant (mv) is expected to differ and does not count."""
    if lab["kind"] == "mv":
        return None
    if rel["seq_relation"] in ("5p_offset", "internal_mismatch"):
        return rel["seq_relation"]
    if lab["kind"] in ("trimmed", "extended") and rel["seq_relation"] == "tail_replaced":
        return "templated label, 3' tail differs from 22.1"
    return None


def classify(target: str, var: str, lab: dict, rel: dict, overhang: int) -> dict:
    """Relation + RT-capture class of one variant (approved Part 2.1 rules), before
    the miRNA-level override for a suspect reference."""
    shift = rel["shift_3p"]
    sr = rel["seq_relation"]
    if sr in ("5p_offset", "internal_mismatch") or (
            lab["kind"] in ("trimmed", "extended") and sr == "tail_replaced") or sr == "same":
        if lab["kind"] in ("mlv3p", "mv"):
            return {"relation": "other", "class": "not_measured",
                    "reason": f"label {lab['kind']}"}
        return {"relation": "reference_mismatch", "class": "not_assessed",
                "reason": f"differs from miRBase 22.1 ({sr})"}
    if lab["kind"] in ("mlv3p", "mv", "unknown"):
        return {"relation": "other", "class": "not_measured", "reason": f"label {lab['kind']}"}
    if lab["kind"] == "nta":
        if sr == "tail_replaced":
            return {"relation": "nta", "class": "not_measured",
                    "trimmed_nt": rel["trimmed_nt"], "added_nt": rel["added"],
                    "display": f"−{rel['trimmed_nt']} nt then +{rel['added']}"}
        # sr == "extended"
        if 1 <= shift <= 2:
            lo, hi, n = ASSAY_DCQ_RT_SHIFT_RANGE["longer"]
            return {"relation": "nta", "class": "assumed_templated", "trimmed_nt": 0,
                    "added_nt": rel["added"], "delta_cq_low": lo, "delta_cq_high": hi,
                    "n_mirnas": n}
        return {"relation": "nta", "class": "outside_measured_range", "trimmed_nt": 0,
                "added_nt": rel["added"]}
    # templated (lv3pT / lv3pE) with the full 5' prefix
    relation = "trimmed" if shift < 0 else "extended"
    if abs(shift) > 2:
        return {"relation": relation, "class": "outside_measured_range"}
    rt = rt_axis(target, var, overhang)
    if rt["shift_3p"] != shift or rt["mismatch_positions"]:
        why = []
        if rt["shift_3p"] != shift:
            why.append(f"rt_axis best register {rt['shift_3p']:+d} != sequence shift {shift:+d}")
        if rt["mismatch_positions"]:
            why.append(f"overhang mismatch at {rt['mismatch_positions']}")
        return {"relation": relation, "class": "other", "reason": "; ".join(why)}
    lo, hi, n = rt["shift_range"]
    return {"relation": relation, "class": "measured_range",
            "delta_cq_low": lo, "delta_cq_high": hi, "n_mirnas": n}


def label_agrees(lab: dict, rel: dict):
    """True/False when the label implies a shift that the sequence can confirm; None
    otherwise (prefix mismatch, mlv3p, mv)."""
    sr = rel["seq_relation"]
    if sr in PREFIX_MISMATCH:
        return None
    if lab["kind"] in ("trimmed", "extended"):
        return sr == lab["kind"] and lab["label_shift"] == rel["shift_3p"]
    if lab["kind"] == "nta":
        return (sr == "extended" and lab["label_shift"] == rel["shift_3p"]
                and rel["added"] == (lab["nta_base"] or "") * rel["shift_3p"])
    return None


_ROW_KEYS = ("mirna", "rank", "target_rna", "sequence_rna", "label", "pooled_share",
             "seq_relation", "shift_3p", "trimmed_nt", "added", "offset_5p",
             "first_mismatch_pos_1based")


def _compact(out: dict) -> dict:
    """Keep the file small: listed rows carry only identifying fields, and the
    per-miRNA / per-variant records become two column tables (miRNAs without
    variants are left out)."""
    sec = out["1_1_label_vs_sequence"]
    sec["label_disagrees_rows"] = [{f: r[f] for f in _ROW_KEYS if f in r and r[f] is not None}
                                   for r in sec["label_disagrees_rows"]]
    del sec["prefix_mismatch_rows"]      # = variants_table rows whose seq_relation is
    #                                      tail_replaced / 5p_offset / internal_mismatch
    mcols = ["mirna", "target_rna", "canonical_3prime_share_pooled", "level",
             "three_prime_isomir_risk", "fold_change_bias_risk", "reference_suspect",
             "reference_confirmed_by_lv3p", "reference_may_differ", "R1", "R2"]
    vcols = ["mirna", "rank", "sequence_rna", "label", "pooled_share", "seq_relation",
             "shift_3p", "trimmed_nt", "added", "relation", "class",
             "class_before_reference_override", "class_5nt", "class_7nt", "note"]
    mrows, vrows = [], []
    for n, p in out["per_mirna"].items():
        if not p["variants"]:
            continue
        mrows.append([n] + [p[c] for c in mcols[1:]])
        for v in p["variants"]:
            c, b = v["capture"], v["capture_before_override"]
            by = v["capture_by_overhang"]
            vrows.append([n, v["rank"], v["sequence_rna"], v["label"], v["pooled_share"],
                          v["seq_relation"], v["shift_3p"], v["trimmed_nt"], v["added"],
                          c["relation"], c["class"], b["class"], by["5"]["class"],
                          by["7"]["class"], c.get("reason") or c.get("display")])
    del out["per_mirna"]
    out["mirnas_table"] = {"columns": mcols, "rows": mrows}
    out["variants_table"] = {"columns": vcols, "rows": vrows}
    return out


def main() -> None:
    db = _load_db3()
    names = sorted(k for k, v in db.items()
                   if not k.startswith("_") and "median_3prime_fraction" in v)
    per_mirna, missing_seq = {}, []

    for name in names:
        e = db[name]
        row = local_db.lookup(name)
        if row is None:
            missing_seq.append(name)
            continue
        target = row["sequence"].upper().replace("U", "T")
        vs, suspect = [], []
        for rank, v in enumerate(e.get("top_3prime_variants") or [], 1):
            var = v["sequence_dna"].upper()
            lab = parse_label(v["label"])
            rel = seq_relation(target, var)
            caps = {str(oh): classify(target, var, lab, rel, oh) for oh in OVERHANGS}
            why = reference_suspect_reason(lab, rel)
            if why:
                suspect.append({"rank": rank, "reason": why,
                                "questioned_pos": _lcp(target, var) + 1})
            vs.append({"rank": rank, "sequence_rna": to_rna(var), "label": v["label"],
                       "pooled_share": v["pooled_share"], **lab, **rel,
                       "label_agrees_with_sequence": label_agrees(lab, rel),
                       "capture_before_override": caps[str(OVERHANG)],
                       "capture_by_overhang": caps})
        # A templated-label variant that matches 22.1 exactly proves the reference's first
        # nt equal to 22.1: all of it for lv3pE, the first L-k nt for lv3pT#-k. The
        # reference counts as confirmed only if that covers every questioned position
        # (rule tightened by the owner, 2026-11-21: miR-378c, miR-4443, miR-4791).
        covered = max([len(target) if v["kind"] == "extended" else len(target) + v["shift_3p"]
                       for v in vs if v["kind"] in ("trimmed", "extended")
                       and v["label_agrees_with_sequence"]] or [0])
        confirmed = bool(suspect) and covered >= max(x["questioned_pos"] for x in suspect)
        ref_differs = bool(suspect) and not confirmed
        for v in vs:      # miRNA-level override (approved rule b, option B)
            v["capture"] = ({"relation": v["capture_before_override"]["relation"],
                             "class": "not_assessed",
                             "reason": "isomiRdb reference may differ from miRBase 22.1"}
                            if ref_differs else v["capture_before_override"])
        canon = round(1 - e["pooled_3prime_fraction"], 3)
        top1 = vs[0]["pooled_share"] if vs else None
        r1 = bool(vs) and top1 > canon
        r1_ge = bool(vs) and top1 >= canon - EPS
        r2 = bool(vs) and top1 >= R2_FACTOR * canon - EPS
        flag = check_3prime_isomir_flag(name, OVERHANG)
        per_mirna[name] = {
            "target_rna": to_rna(target), "length": len(target),
            "canonical_3prime_share_pooled": canon,
            "pooled_3prime_fraction": e["pooled_3prime_fraction"],
            "median_3prime_fraction": e["median_3prime_fraction"],
            "level": flag["level"],
            "three_prime_isomir_risk": flag["three_prime_isomir_risk"],
            "fold_change_bias_risk": flag.get("fold_change_bias_risk", False),
            "reference_suspect": bool(suspect), "reference_confirmed_by_lv3p": confirmed,
            "reference_may_differ": ref_differs, "reference_suspect_variants": suspect,
            "R1": r1, "R1_ge": r1_ge, "R2_raw": r2,
            "R2": r2 and not ref_differs,        # approved: R2, not where the reference may differ
            "variants": vs,
        }

    P = per_mirna
    allv = [(n, v) for n, p in P.items() for v in p["variants"]]
    n_var = len(allv)
    sus = sorted(n for n, p in P.items() if p["reference_may_differ"])
    sus_all = sorted(n for n, p in P.items() if p["reference_suspect"])

    # ── 1.1 ───────────────────────────────────────────────────────────
    prefix_rows = [{"mirna": n, "target_rna": P[n]["target_rna"], **v} for n, v in allv
                   if v["seq_relation"] in PREFIX_MISMATCH]
    label_rows = [{"mirna": n, "target_rna": P[n]["target_rna"], **v} for n, v in allv
                  if v["label_agrees_with_sequence"] is False]

    # ── 1.2 classes (must sum to n_var) ───────────────────────────────
    def class_counts(key, rank1=False):
        c = Counter(v[key]["class"] for _, v in allv if not rank1 or v["rank"] == 1)
        return {k: c.get(k, 0) for k in CLASSES}
    cls_final = class_counts("capture")
    cls_before = class_counts("capture_before_override")
    assert sum(cls_final.values()) == n_var and sum(cls_before.values()) == n_var

    # ── register check at 5/6/7 nt: templated ±1–2 nt with the full 5' prefix ──
    register = {}
    for oh in OVERHANGS:
        rows = [(n, v) for n, v in allv if v["kind"] in ("trimmed", "extended")
                and v["seq_relation"] in ("trimmed", "extended") and 1 <= abs(v["shift_3p"]) <= 2]
        bad = [{"mirna": n, "target_rna": P[n]["target_rna"], "variant_rna": v["sequence_rna"],
                "shift_3p": v["shift_3p"], "reason": v["capture_by_overhang"][str(oh)]["reason"]}
               for n, v in rows if v["capture_by_overhang"][str(oh)]["class"] != "measured_range"]
        register[str(oh)] = {"checked": len(rows), "register_matches": len(rows) - len(bad),
                             "mismatching": bad}

    # ── 1.3 ───────────────────────────────────────────────────────────
    big = []
    for n, v in allv:
        if v["seq_relation"] in ("trimmed", "extended") and abs(v["shift_3p"]) > 2:
            t = P[n]["target_rna"].replace("U", "T")
            rt = rt_axis(t, v["sequence_rna"].replace("U", "T"), OVERHANG)
            big.append({"mirna": n, "variant_rna": v["sequence_rna"], "label": v["label"],
                        "kind": v["kind"], "shift_3p": v["shift_3p"],
                        "pooled_share": v["pooled_share"],
                        "class_before_override": v["capture_before_override"]["class"],
                        "rt_axis_delta_cq": rt["delta_cq"], "rt_axis_register": rt["shift_3p"],
                        "rt_axis_basis": rt["basis"]})
    big_hist = Counter((r["rt_axis_delta_cq"], r["rt_axis_register"]) for r in big)

    # ── reconciliation of the counts questioned on 2026-11-21 ─────────
    prefix_by_type = Counter(r["seq_relation"] for r in prefix_rows)
    prefix_by_kind = Counter(r["kind"] for r in prefix_rows)
    kind_all = Counter(v["kind"] for _, v in allv)
    mlv_mv_in_prefix = sum(1 for r in prefix_rows if r["kind"] in ("mlv3p", "mv"))
    big_not_outside = [r for r in big if r["class_before_override"] != "outside_measured_range"]
    reconciliation = {
        "old_unclassified_537": (
            f"{len(prefix_rows)} prefix mismatches (tail {prefix_by_type['tail_replaced']} + "
            f"5' offset {prefix_by_type['5p_offset']} + internal {prefix_by_type['internal_mismatch']})"
            f" already include {mlv_mv_in_prefix} mlv3p/mv variants; adding mlv3p "
            f"{kind_all['mlv3p']} + mv {kind_all['mv']} counts those {mlv_mv_in_prefix} twice: "
            f"{len(prefix_rows)} + {kind_all['mlv3p'] + kind_all['mv'] - mlv_mv_in_prefix} = "
            f"{len(prefix_rows) + kind_all['mlv3p'] + kind_all['mv'] - mlv_mv_in_prefix}"),
        "old_big_shift_216_vs_outside_214": (
            f"{len(big)} variants with |shift| > 2 nt and the full 5' prefix; "
            f"{len(big_not_outside)} of them are not outside_measured_range because their label "
            "is mlv3p/mv (class not_measured): "
            + ", ".join(f"{r['mirna']} {r['label']} {r['shift_3p']:+d}" for r in big_not_outside)),
        "classes_sum": f"{sum(cls_final.values())} = {n_var} variants",
    }

    # ── 1.4 rules ─────────────────────────────────────────────────────
    def rule(key):
        fired = [n for n, p in P.items() if p[key]]
        return {"n_fire": len(fired), "of": len(P),
                "top1_class_before_override": dict(Counter(
                    P[n]["variants"][0]["capture_before_override"]["class"] for n in fired)),
                "by_current_level": dict(Counter(P[n]["level"] for n in fired)),
                "mirnas": fired}
    rules = {
        "R1": {"rule": "top-1 pooled share > canonical 3' share", **rule("R1")},
        "R1_ge": {"rule": "top-1 pooled share >= canonical 3' share", **rule("R1_ge")},
        "R2_raw": {"rule": f"top-1 >= {R2_FACTOR} x canonical (3-decimal values), all miRNAs",
                   **rule("R2_raw")},
        "R2": {"rule": (f"APPROVED: top-1 >= {R2_FACTOR} x canonical (3-decimal values); "
                        "not for miRNAs whose isomiRdb reference may differ from 22.1 (option B). "
                        f"{R2_FACTOR} = own threshold of the tool, not calibrated."),
               **rule("R2"),
               "removed_as_reference_suspect": sorted(n for n, p in P.items()
                                                      if p["R2_raw"] and not p["R2"])},
    }

    # ── reference check (approved rule a/b/c) ─────────────────────────
    sus_high = [n for n in sus if P[n]["three_prime_isomir_risk"]]
    sus_fc = [n for n in sus if P[n]["fold_change_bias_risk"]]
    sus_any = [n for n in sus if P[n]["three_prime_isomir_risk"] or P[n]["fold_change_bias_risk"]]
    reference_check = {
        "definition_suspect": ("a top-3 variant differs from the 22.1 sequence at the 5' end or "
                               "inside the sequence, or carries a templated label (lv3pT/lv3pE) "
                               "while its 3' tail differs from 22.1; a labelled mismatch "
                               "variant (mv) does not count"),
        "definition_may_differ": ("suspect AND no templated-label variant that matches 22.1 "
                                  "exactly covers every questioned position (lv3pE covers the "
                                  "whole reference, lv3pT#-k its first L-k nt) — option B, "
                                  "tightened by the owner on 2026-11-21"),
        "confirmed": sorted(n for n in sus_all if n not in sus),
        "n_suspect": len(sus_all),
        "n_suspect_confirmed_by_lv3p": len(sus_all) - len(sus),
        "n_reference_may_differ": len(sus),
        "by_reason_suspect": dict(Counter(s["reason"] for n in sus_all
                                          for s in P[n]["reference_suspect_variants"])),
        "by_reason_may_differ": dict(Counter(s["reason"] for n in sus
                                             for s in P[n]["reference_suspect_variants"])),
        "n_with_high_3prime_warning": len(sus_high),
        "n_with_fold_change_warning": len(sus_fc),
        "n_with_either_warning": len(sus_any),
        "with_either_warning": sus_any,
        "mirnas": sus,
    }

    cases = []
    for name in CASES:
        p = P[name]
        cases.append({
            "mirna": name, "sequence_rna_22_1": p["target_rna"], "length": p["length"],
            "overhang_6nt_rna": p["target_rna"][-OVERHANG:], "level": p["level"],
            "median_3prime_fraction": p["median_3prime_fraction"],
            "three_prime_isomir_risk": p["three_prime_isomir_risk"],
            "fold_change_bias_risk": p["fold_change_bias_risk"],
            "canonical_3prime_share_pooled": p["canonical_3prime_share_pooled"],
            "reference_may_differ": p["reference_may_differ"],
            "top3": [{"sequence_rna": v["sequence_rna"], "label": v["label"],
                      "shift_3p": v["shift_3p"], "pooled_share": v["pooled_share"],
                      "capture": v["capture"]} for v in p["variants"]],
            "R1": p["R1"], "R2": p["R2"],
        })

    out = {
        "_about": ("Dry-run, PROMPT_isomir_variants_4.0.0.md Part 1, with the rules approved on "
                   f"2026-11-21. Read-only. Overhang {OVERHANG} nt unless stated; R2 factor "
                   f"{R2_FACTOR} is an own threshold of the tool, not calibrated. Shares are "
                   "pooled over all isomiRdb samples."),
        "source_files": {"isomir": "backend/data/known_3prime_isomir_mirnas.json",
                         "mirbase": "backend/db/mirbase.db (miRBase 22.1, served by /api/mirbase)"},
        "counts": {
            "mirnas_with_3prime_data": len(names),
            "mirnas_with_variants": sum(1 for p in P.values() if p["variants"]),
            "mirnas_missing_22_1_sequence": missing_seq,
            "variants_total": n_var,
            "variants_by_label_kind": dict(kind_all),
            "mirnas_with_nta_in_top3": sum(1 for p in P.values()
                                           if any(v["kind"] == "nta" for v in p["variants"])),
        },
        "reconciliation": reconciliation,
        "1_1_label_vs_sequence": {
            "prefix_mismatch": len(prefix_rows),
            "prefix_mismatch_by_type": dict(prefix_by_type),
            "prefix_mismatch_by_label_kind": dict(prefix_by_kind),
            "prefix_mismatch_mirnas": len({r["mirna"] for r in prefix_rows}),
            "tail_replaced_by_trim_add": dict(Counter(
                f"-{r['trimmed_nt']}+{len(r['added'])}" for r in prefix_rows
                if r["seq_relation"] == "tail_replaced")),
            "label_disagrees_with_sequence": len(label_rows),
            "label_disagrees_by_type": dict(Counter(
                f"{r['kind']} label #{r['label_shift']} vs sequence {r['shift_3p']:+d}"
                for r in label_rows)),
            "label_disagrees_rows": label_rows,
            "prefix_mismatch_rows": prefix_rows,
        },
        "1_2_capture_class": {
            "final": cls_final, "final_rank1": class_counts("capture", True),
            "before_reference_override": cls_before,
            "before_reference_override_rank1": class_counts("capture_before_override", True),
        },
        "register_check_by_overhang": register,
        "1_3_big_shift": {
            "variants_abs_shift_gt_2": len(big),
            "rt_axis_delta_cq_8": sum(1 for r in big if r["rt_axis_delta_cq"] == 8.0),
            "rt_axis_result_hist": [{"delta_cq": k[0], "register": k[1], "n": c}
                                    for k, c in big_hist.most_common()],
            "rows": big,
        },
        "1_4_rules": rules,
        "reference_check": reference_check,
        "1_5_cases": cases,
        "per_mirna": per_mirna,
    }
    tables = _compact(out)
    rows = {k: tables.pop(k) for k in ("mirnas_table", "variants_table")}
    text = json.dumps(tables, indent=1, ensure_ascii=False)[:-2]
    NL = chr(10)
    for k, t in rows.items():      # one line per table row
        body = ("," + NL).join("   " + json.dumps(r, ensure_ascii=False) for r in t["rows"])
        text += ("," + NL + f' "{k}": {{' + NL + f'  "columns": {json.dumps(t["columns"])},' + NL
                 + '  "rows": [' + NL + body + NL + "  ]" + NL + " }")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text + NL + "}" + NL)

    print(json.dumps(out["counts"], indent=1))
    print(json.dumps(reconciliation, indent=1, ensure_ascii=False))
    print("1.1", len(prefix_rows), dict(prefix_by_type), "label mismatch", len(label_rows))
    print("1.2 final", cls_final)
    print("1.2 before override", cls_before)
    print("register", {k: (v["checked"], v["register_matches"]) for k, v in register.items()})
    print("1.3", len(big), out["1_3_big_shift"]["rt_axis_delta_cq_8"])
    for k, r in rules.items():
        print("1.4", k, r["n_fire"], r["by_current_level"])
    print("ref", {k: v for k, v in reference_check.items() if k not in ("mirnas", "with_either_warning")})
    for c in cases:
        print(c["mirna"], c["R1"], c["R2"], c["reference_may_differ"],
              [(v["shift_3p"], v["pooled_share"], v["capture"]["class"]) for v in c["top3"]])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
