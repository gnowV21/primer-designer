"""
session.py — hold the HRM numeric table of the current working session
[SPEC_Phase1 §5.1 step 1: "question + (optional) the session's HRM table"].

/api/hrm/analyze computes the table and returns a session_id; /api/chat passes that
id back so the RAG brain can ground its answer in the numbers.

In-process dict, deliberately:
  * the data never leaves the machine [SPEC_Phase1 §0 "self-host"];
  * an HRM run is scratch data for one sitting, not a record worth persisting.
Sessions are lost on restart, which is correct — the user re-uploads the file.
"""

import threading
import time
import uuid

# Cap and TTL exist so a long-running server cannot grow without bound.
MAX_SESSIONS = 50
TTL_SECONDS  = 6 * 60 * 60   # 6 hours — comfortably longer than one lab sitting

_sessions: dict[str, dict] = {}
_lock = threading.Lock()


def _evict_locked() -> None:
    """Drop expired sessions, then the oldest ones if still over cap. Caller holds the lock."""
    now = time.time()
    for sid in [s for s, v in _sessions.items() if now - v["created_at"] > TTL_SECONDS]:
        del _sessions[sid]

    if len(_sessions) > MAX_SESSIONS:
        oldest = sorted(_sessions, key=lambda s: _sessions[s]["created_at"])
        for sid in oldest[: len(_sessions) - MAX_SESSIONS]:
            del _sessions[sid]


def save(payload: dict) -> str:
    """Store one analysis result and return its session id."""
    sid = uuid.uuid4().hex
    with _lock:
        _sessions[sid] = {"created_at": time.time(), "payload": payload}
        _evict_locked()
    return sid


def get(session_id: str) -> dict | None:
    """Return the stored payload, or None if unknown or expired."""
    if not session_id:
        return None
    with _lock:
        entry = _sessions.get(session_id)
        if entry is None:
            return None
        if time.time() - entry["created_at"] > TTL_SECONDS:
            del _sessions[session_id]
            return None
        return entry["payload"]
