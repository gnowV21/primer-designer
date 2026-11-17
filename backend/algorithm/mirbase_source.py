# ================================================================
# mirbase_source.py — which miRBase release the tool's sequences come from
#
# The BLAST database, the overhang index (assay-level ΔCq screen) and the local
# lookup database (db/mirbase.db, served by /api/mirbase) are all built from the
# same miRBase file: mature.fa of Release 22.1, sha256 3c521fc9… (48,885 mature).
# The overhang index records the release and the sha256 of that file in its
# _metadata, so it is the single source for the release reported in results and
# exports. Checked 2026-11-17: /api/mirbase returns the mature.fa sequence and
# accession for all 2656 hsa entries, by name and by accession.
#
# A sequence that is not in that file (typed by hand, or fetched online when the
# local lookup misses) is outside the BLAST DB and the index: the specificity
# checks then compare it with miRBase 22.1 entries that may not include its true
# relatives. The design result says so (`sequence_not_in_mirbase_release`).
# Since algorithm 3.8.2 (PROMPT_thesis_freeze_4.0.0 §3.3).
# ================================================================

from functools import lru_cache

from .specificity_check.overhang_collision import _load_index


@lru_cache(maxsize=1)
def release_info() -> dict:
    """{'mirbase_release', 'mature_fa_sha256', 'mature_fa_build_date'} of the files
    behind the BLAST DB, the overhang index and the local lookup database."""
    meta = (_load_index().get("_metadata") or {})
    return {
        "mirbase_release": meta.get("mirbase_release") or "unknown",
        "mature_fa_sha256": meta.get("mature_fa_sha256"),
        "mature_fa_build_date": meta.get("build_date"),
    }


@lru_cache(maxsize=1)
def _entries() -> tuple[dict, frozenset]:
    by_name, seqs = {}, set()
    for sp_map in (_load_index().get("mature") or {}).values():
        for name, seq in sp_map.items():
            s = seq.upper().replace("T", "U")
            by_name[name.lower()] = (name, s)
            seqs.add(s)
    return by_name, frozenset(seqs)


def sequence_warning(seq: str, mirna_name: str = "") -> dict | None:
    """Warning dict when `seq` is not a mature sequence of the release, or differs
    from the release's entry for `mirna_name`; None when it is covered."""
    s = (seq or "").upper().replace("T", "U")
    rel = release_info()["mirbase_release"]
    by_name, seqs = _entries()
    entry = by_name.get((mirna_name or "").strip().lower())
    if entry and entry[1] != s:
        return {
            "field": "sequence_not_in_mirbase_release",
            "severity": "warning",
            "message": (
                f"The sequence differs from the miRBase {rel} entry for {entry[0]} "
                f"({len(entry[1])} nt, used by the BLAST database and the overhang index). "
                f"Specificity results compare this sequence with miRBase {rel} entries; "
                "check which annotation your samples and published assays use."
            ),
        }
    if s not in seqs:
        return {
            "field": "sequence_not_in_mirbase_release",
            "severity": "warning",
            "message": (
                f"This sequence is not a mature miRNA in miRBase {rel}, the release of "
                "the BLAST database and the overhang index. Specificity checks compare it "
                f"with miRBase {rel} entries only and may miss its true relatives."
            ),
        }
    return None
