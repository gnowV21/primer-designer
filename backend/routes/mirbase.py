import re
import time

import requests
from flask import Blueprint, jsonify

from db import local_db
from db.circuit_breaker import CircuitBreaker

mirbase_bp = Blueprint('mirbase', __name__)

MIRBASE_API    = "https://mirbase.org/api/mirna/"
RNACENTRAL_API = "https://rnacentral.org/api/v1/rna/"

# One circuit breaker per process — shared across all Flask threads
_breaker = CircuitBreaker()

SPECIES_MAP = {
    "hsa": "Homo sapiens",
    "mmu": "Mus musculus",
    "rno": "Rattus norvegicus",
}

# Three attempts: immediate, then wait 2 s, then wait 5 s before the next
_RETRY_DELAYS    = [0, 2, 5]
_ATTEMPT_TIMEOUT = 6  # seconds per individual HTTP call

_RE_ACCESSION = re.compile(r'^MIMAT\d+$', re.IGNORECASE)
_RE_SEQUENCE  = re.compile(r'^[AUGCU]+$', re.IGNORECASE)
_MIN_SEQ_LEN  = 10


def _input_type(mirna_id: str) -> str:
    """Return 'accession', 'sequence', or 'name'."""
    if _RE_ACCESSION.match(mirna_id):
        return 'accession'
    if _RE_SEQUENCE.match(mirna_id) and len(mirna_id) >= _MIN_SEQ_LEN:
        return 'sequence'
    return 'name'


def _parse_mirna(mirna: dict, mirna_id: str) -> dict:
    seq      = mirna.get("mature_sequence", mirna.get("sequence", "")).upper()
    acc      = mirna.get("mature_acc", mirna.get("accession", ""))
    prefix   = mirna_id[:3].lower() if "-" in mirna_id else ""
    species  = SPECIES_MAP.get(prefix, mirna.get("organism", "Unknown"))
    return {
        "id":        mirna_id,
        "accession": acc,
        "sequence":  seq,
        "family":    mirna.get("family", ""),
        "species":   species,
        "length":    len(seq),
    }


def _fetch_mirbase(mirna_id: str) -> dict | None:
    """
    Query miRBase REST API with exponential-backoff retries.
    Returns parsed dict on success, None if ID not found (200 but empty),
    or raises the last exception after all attempts are exhausted.
    """
    # Use the single correct param for this input type — avoids one wasted HTTP probe per call
    param = "accession" if _RE_ACCESSION.match(mirna_id) else "name"
    last_exc = None
    for delay in _RETRY_DELAYS:
        if delay:
            time.sleep(delay)
        try:
            r = requests.get(
                MIRBASE_API,
                params={param: mirna_id},
                timeout=_ATTEMPT_TIMEOUT,
            )
            if r.status_code != 200:
                return None
            body    = r.json()
            results = body.get("results", []) if isinstance(body, dict) else (body if isinstance(body, list) else [])
            return _parse_mirna(results[0], mirna_id) if results else None
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
        except Exception as exc:
            last_exc = exc
            break  # Non-transient (e.g. JSON decode) — stop retrying
    raise last_exc or RuntimeError("miRBase API unreachable")


def _fetch_rnacentral(mirna_id: str) -> dict | None:
    """
    Secondary fallback: RNAcentral (EBI-hosted, more reliable infra).
    Supports both miRBase names (hsa-miR-21-5p) and accessions (MIMAT0000076).
    """
    try:
        r = requests.get(
            RNACENTRAL_API,
            params={"external_id": mirna_id, "format": "json"},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        results = r.json().get("results", [])
        if not results:
            return None
        hit = results[0]
        seq = hit.get("sequence", "").upper().replace("T", "U")
        if not seq:
            return None
        desc    = hit.get("description", "")
        parts   = desc.split()
        species = f"{parts[0]} {parts[1]}" if len(parts) >= 2 else ""
        return {
            "id":        mirna_id,
            "accession": "",
            "sequence":  seq,
            "family":    "",
            "species":   species,
            "length":    len(seq),
        }
    except Exception:
        return None


@mirbase_bp.route('/mirbase/<mirna_id>')
def get_mirna(mirna_id):
    mirna_id = mirna_id.strip()
    if not mirna_id or len(mirna_id) > 100:
        return jsonify({"error": "Invalid ID"}), 400

    # ── 1. Local SQLite (fast, offline, always first) ──────────────────────
    local = local_db.lookup(mirna_id)
    if local:
        return jsonify({
            "id":        local.get("name", mirna_id),
            "accession": local.get("accession", ""),
            "sequence":  local.get("sequence", ""),
            "family":    local.get("family", ""),
            "species":   local.get("species", ""),
            "length":    local.get("length", 0),
            "source":    "local",
        })

    # ── 1b. Sequence inputs have no miRBase lookup path — skip external calls
    if _input_type(mirna_id) == 'sequence':
        return jsonify({"error": "miRNA not found", "id": mirna_id}), 404

    # ── 2. Circuit breaker guard ────────────────────────────────────────────
    breaker_open, secs = _breaker.check()
    if breaker_open:
        return jsonify({
            "error":   "miRBase temporarily unavailable",
            "message": (
                f"miRBase has been unreachable after repeated failures. "
                f"Retrying in {secs // 60}m {secs % 60}s. "
                "Enter the sequence manually in the meantime."
            ),
        }), 503

    # ── 3. miRBase REST API with retry + exponential backoff ───────────────
    try:
        result = _fetch_mirbase(mirna_id)
        if result is None:
            # API returned 200 but no matching miRNA — not a connectivity issue
            return jsonify({
                "error":      "miRNA not found",
                "id":         mirna_id,
                "suggestion": "Check the ID and try again. Examples: hsa-miR-21-5p, MIMAT0000076",
            }), 404
        _breaker.record_success()
        local_db.upsert(result)
        result["source"] = "mirbase"
        return jsonify(result)
    except Exception:
        _breaker.record_failure()

    # ── 4. Fallback: RNAcentral (EBI) ──────────────────────────────────────
    result = _fetch_rnacentral(mirna_id)
    if result:
        local_db.upsert(result)
        result["source"] = "rnacentral"
        return jsonify(result)

    # ── 5. All sources exhausted ────────────────────────────────────────────
    return jsonify({
        "error":   "Cannot reach miRBase",
        "message": (
            "miRBase did not respond after 3 attempts and RNAcentral also failed. "
            "Please enter the sequence manually."
        ),
    }), 504
