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

_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "known_5prime_isomir_mirnas.json"
)
_DB_CACHE: dict | None = None


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


# ── Internal helpers ──────────────────────────────────────────────

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
