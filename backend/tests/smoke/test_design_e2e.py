# ================================================================
# tests/smoke/test_design_e2e.py — End-to-end smoke test for /api/design
# Requires backend running at localhost:5000
# ================================================================

import requests

BASE = "http://localhost:5000/api"

PAYLOAD_MIR21 = {
    "sequence": {
        "matureSequence": "UAGCUUAUCAGACUGAUGUUGA",
        "mirnaId": "hsa-miR-21-5p",
    },
    "thermodynamic": {},
    "primerConstraints": {},
    "qpcr": {},
    "detectionMethod": {},
    "experimentalContext": {},
}


def test_health():
    r = requests.get(f"{BASE}/health", timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_design_returns_top3():
    r = requests.post(f"{BASE}/design", json=PAYLOAD_MIR21, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "top3" in data
    assert len(data["top3"]) >= 1


def test_design_v4_scoring_present():
    r = requests.post(f"{BASE}/design", json=PAYLOAD_MIR21, timeout=30)
    data = r.json()
    top = data["top3"][0]
    # V4 criteria must be present
    # bound_fraction_binding is informational only since audit SCI-02
    assert "bound_fraction_binding_pct" in top["scores"]
    assert "bound_fraction_full" in top["scores"]
    assert "family_discrimination" in top["scores"]


def test_design_scoring_version_v4():
    r = requests.post(f"{BASE}/design", json=PAYLOAD_MIR21, timeout=30)
    data = r.json()
    meta = data.get("metadata", {})
    assert meta.get("scoring_version", "").startswith("V4")


def test_design_isomir_flag_present():
    r = requests.post(f"{BASE}/design", json=PAYLOAD_MIR21, timeout=30)
    data = r.json()
    top = data["top3"][0]
    assert "isomir_flag" in top
