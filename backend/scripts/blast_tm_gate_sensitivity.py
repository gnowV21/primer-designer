"""
blast_tm_gate_sensitivity.py — sensitivity of the BLAST duplex-Tm gate to its SAFE margin.

For every distinct (forward primer, target) in validation/results.json, BLAST runs
ONCE against the miRBase DB; the hits are then re-classified with the SAFE margin
at 5, 10, 15 and 20 °C (CRITICAL margin fixed at 5 °C), plus a baseline without
the Tm gate (Ye12/Kwok90 rules + the legacy 10-nt anchor). If the per-tier counts
are stable around 10 °C, the margin is not cherry-picked.

There is no ground truth here: counts are classifier outputs, not confirmed
false or true positives. Wet-lab cross-reactivity tests supply that.

On-target sequence: reference_mirnas.json matureSequence if given, else the BLAST
DB entry for the id. A target is skipped if the primer's specific region is not a
prefix of that sequence (e.g. a sequence that differs between miRBase releases).

Usage (repo root; needs blastn + the BLAST DB, not the Flask server):
    python backend/scripts/blast_tm_gate_sensitivity.py
Writes: benchmark/blast_tm_gate_sensitivity.json
"""

import json
import os
import re
import sys
from collections import Counter
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.constants import BLAST_TM_CRITICAL_MARGIN, BLAST_CLASSIFIER_VERSION  # noqa: E402
from algorithm.sequence_utils import rna_to_dna  # noqa: E402
from algorithm.specificity_check import blast_offtarget as bo  # noqa: E402

_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
_RESULTS = os.path.join(_ROOT, "validation", "results.json")
_REFERENCE = os.path.join(_ROOT, "validation", "reference_mirnas.json")
_OUT = os.path.join(_ROOT, "benchmark", "blast_tm_gate_sensitivity.json")

SAFE_MARGINS = (5.0, 10.0, 15.0, 20.0)
TIERS = ("CRITICAL", "HIGH", "MEDIUM")


def _memoise_blast():
    """Each primer is searched once, however many margins are evaluated."""
    blast_cache, seq_cache = {}, {}
    run_blastn, fetch = bo.run_blastn, bo.fetch_sequences

    def cached_blastn(primer, db_path, timeout=60):
        if primer not in blast_cache:
            blast_cache[primer] = run_blastn(primer, db_path, timeout)
        return blast_cache[primer]

    def cached_fetch(ids, db_path, timeout=60):
        missing = [i for i in ids if i not in seq_cache]
        if missing:
            got = fetch(missing, db_path, timeout)
            for i in missing:
                seq_cache[i] = got.get(i)
        return {i: seq_cache[i] for i in ids if seq_cache.get(i)}

    bo.run_blastn, bo.fetch_sequences = cached_blastn, cached_fetch


def _targets():
    results = json.load(open(_RESULTS, encoding="utf-8"))["targets"]
    ref = json.load(open(_REFERENCE, encoding="utf-8"))
    given = {m["id"]: m.get("matureSequence") for m in ref["mirnas"]}
    seen, out = set(), []
    for t in results:
        primer = (t.get("published_forward_tool") or "").upper()
        specific = (t.get("forward_tool_specific") or "").upper()
        if not primer or not specific or t.get("edge_expected"):
            continue
        mirna_id = re.sub(r"\s*\(.*\)\s*$", "", t["target"]).strip()
        if (primer, mirna_id) in seen:
            continue
        seen.add((primer, mirna_id))
        out.append({"target": t["target"], "mirna_id": mirna_id, "primer": primer,
                    "specific": specific, "given_seq": given.get(t["target"])})
    return out


def main() -> int:
    _memoise_blast()
    rows, skipped = [], []
    for t in _targets():
        seq = t["given_seq"]
        source = "reference_mirnas.json"
        if not seq:
            seq = bo.fetch_sequences([t["mirna_id"]], bo._MIRBASE_DB).get(t["mirna_id"])
            source = "blast_db"
        if not seq:
            skipped.append({**t, "reason": "target sequence not found"})
            continue
        seq = rna_to_dna(seq).upper()
        if not seq.startswith(t["specific"]):
            skipped.append({**t, "reason": "specific region is not a prefix of the target sequence"})
            continue

        per_margin = {}
        for m in SAFE_MARGINS:
            r = bo.check_offtarget(t["primer"], "", t["mirna_id"], target_sequence=seq,
                                   safe_margin=m, critical_margin=BLAST_TM_CRITICAL_MARGIN)
            per_margin[f"{m:g}"] = r
        # Baseline: the same hits classified without Tm data (tm_on=None → legacy rules).
        hits, safe, _, fam = bo._check_primer(
            t["primer"], [bo._MIRBASE_DB], t["mirna_id"],
            bo._normalize_mirna_name(t["mirna_id"].lower()),
            bo._extract_species_prefix(t["mirna_id"]), 60,
            bo.get_family_id(t["mirna_id"]))
        per_margin["no_tm_gate"] = {"summary": bo._summarise(hits, safe, 0, fam),
                                    "forward_primer_hits": hits}

        rows.append({
            "target": t["target"], "mirna_id": t["mirna_id"], "primer": t["primer"],
            "target_sequence_source": source,
            "tm_ontarget": per_margin["10"]["classification"]["tm_ontarget"],
            "results": {k: {"overall_risk": v["summary"]["overall_risk"],
                            **{tier: sum(h["risk"] == tier for h in v["forward_primer_hits"])
                               for tier in TIERS},
                            "safe": v["summary"]["safe_count"],
                            "same_family": v["summary"]["same_family_count"]}
                        for k, v in per_margin.items()},
            "critical_hits_at_10": [
                {"subject_id": h["subject_id"], "risk": h["risk"],
                 "tm_offtarget": h["alignment"]["tm_offtarget"], "reason": h["risk_reason"]}
                for h in per_margin["10"]["forward_primer_hits"] if h["risk"] in ("CRITICAL", "HIGH")
            ],
        })
        print(f"{t['target']:40s} Tm_on={rows[-1]['tm_ontarget']}  "
              + "  ".join(f"{k}:{v['overall_risk']}" for k, v in rows[-1]["results"].items()),
              flush=True)

    settings = [f"{m:g}" for m in SAFE_MARGINS] + ["no_tm_gate"]
    summary = {}
    for k in settings:
        summary[k] = {
            "primers_by_overall_risk": dict(Counter(r["results"][k]["overall_risk"] for r in rows)),
            "hits_by_tier": {tier: sum(r["results"][k][tier] for r in rows) for tier in TIERS},
            "safe_hits": sum(r["results"][k]["safe"] for r in rows),
        }

    out = {
        "generated_by": "backend/scripts/blast_tm_gate_sensitivity.py",
        "run_date": date.today().isoformat(),
        "classifier_version": BLAST_CLASSIFIER_VERSION,
        "blast_db": json.load(open(bo._METADATA, encoding="utf-8")),
        "critical_margin_c": BLAST_TM_CRITICAL_MARGIN,
        "safe_margins_c": list(SAFE_MARGINS),
        "conditions": bo.resolve_p3_conditions(None),
        "note": ("Counts are classifier outputs with no ground truth — not confirmed "
                 "false/true positives. 'no_tm_gate' = Ye12/Kwok90 rules + 10-nt anchor "
                 "(with the Kwok orientation fix), i.e. the rules without the Tm gate."),
        "n_primers": len(rows),
        "n_skipped": len(skipped),
        "summary": summary,
        "skipped": skipped,
        "primers": rows,
    }
    with open(_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(json.dumps(summary, indent=1))
    print(f"{len(rows)} primers, {len(skipped)} skipped → {os.path.normpath(_OUT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
