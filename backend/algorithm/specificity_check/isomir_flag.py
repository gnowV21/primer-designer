# ================================================================
# specificity_check/isomir_flag.py
# isoMiR 5'-end discrimination flag for forward primer candidates
#
# Checks whether a forward primer's 3' end falls within the region
# that varies between canonical miRNA and its known 5' isomiRs.
# This is an INFORMATIONAL WARNING only — does not block primer generation.
#
# Data: backend/data/known_5prime_isomir_mirnas.json (offline, needs verification)
# WARNING: isoMiR data is PLACEHOLDER — verify before production use.
#
# Sources: Neilsen et al. 2012 Bioinformatics; Morin et al. 2008 Genome Research
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
            "note": "No known 5' isomiR reported for this miRNA.",
            "data_warning": (
                "isoMiR database is PLACEHOLDER — only a small subset of miRNAs "
                "is listed. Absence of an entry does NOT guarantee no 5' isomiRs exist."
            ),
        }

    risk_window = int(entry.get("risk_window_nt", 2))
    shift_nt    = int(entry.get("known_5prime_shift_nt", 1))

    # Forward primer 3' end is at position `forward_3prime_position` (1-based).
    # 5' isoMiR shifts the start by ±shift_nt, so the first risk_window_nt positions
    # from the 5' end of the miRNA are in the variable region.
    in_risk_window = forward_3prime_position <= risk_window

    if in_risk_window:
        note = (
            f"Forward primer 3' end is at position {forward_3prime_position} (1-based) "
            f"on the mature miRNA. A known 5' isomiR (±{shift_nt} nt shift) exists for "
            f"this miRNA — the primer 3' end falls within the {risk_window}-nt risk window "
            f"and may not discriminate between the canonical sequence and the isomiR. "
            f"Source: {entry.get('source', 'PLACEHOLDER — verify')}."
        )
    else:
        note = (
            f"Forward primer 3' end is at position {forward_3prime_position} (1-based), "
            f"beyond the {risk_window}-nt 5' isoMiR risk window. "
            f"Primer is likely to discriminate canonical from shifted 5' isomiRs."
        )

    return {
        "isomir_discrimination_risk": in_risk_window,
        "mirna_name": mirna_name,
        "forward_3prime_position": forward_3prime_position,
        "known_5prime_shift_nt": shift_nt,
        "risk_window_nt": risk_window,
        "note": note,
        "data_warning": (
            "isoMiR data is PLACEHOLDER — verify against literature before "
            "interpreting this result in a production context."
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
