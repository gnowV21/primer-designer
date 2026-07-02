# ================================================================
# tests/test_edge_cases.py — Unit tests for edge_cases.py (Phase 4)
# 8 rules E1–E8 + normal case.
# ================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.edge_cases import detect_edge_cases


def _codes(seq):
    return [e["code"] for e in detect_edge_cases(seq)]


def _severities(seq):
    return {e["code"]: e["severity"] for e in detect_edge_cases(seq)}


# ── E1: critical short ────────────────────────────────────────────

def test_short_mirna_critical():
    seq = "UAGCUUAUCA"  # 10 nt — well below 18
    result = detect_edge_cases(seq)
    codes = [e["code"] for e in result]
    assert "E1" in codes
    e1 = next(e for e in result if e["code"] == "E1")
    assert e1["severity"] == "critical"
    assert e1["value"] == 10


def test_short_mirna_17_critical():
    seq = "UAGCUUAUCAGACUG"  # 15 nt
    assert "E1" in _codes(seq)


# ── E2: borderline short warning ─────────────────────────────────

def test_borderline_short_warning():
    seq = "UAGCUUAUCAGACUG GA"  # 18 nt — exactly MIRNA_LEN_WARN_SHORT - 2 → warning
    # Build 18-nt RNA
    seq18 = "UAGCUUAUCAGACUGAGA"  # 18 nt
    result = detect_edge_cases(seq18)
    codes = [e["code"] for e in result]
    assert "E1" not in codes
    assert "E2" in codes
    e2 = next(e for e in result if e["code"] == "E2")
    assert e2["severity"] == "warning"


def test_19nt_is_warning():
    seq = "UAGCUUAUCAGACUGAGAG"  # 19 nt
    assert "E2" in _codes(seq)
    assert "E1" not in _codes(seq)


# ── E3: long miRNA info ───────────────────────────────────────────

def test_long_mirna_info():
    seq = "UAGCUUAUCAGACUGAGAUCAAGCAG"  # 26 nt — MIRNA_LEN_INFO_LONG = 26, so 27+ → info
    seq27 = seq + "U"  # 27 nt
    result = detect_edge_cases(seq27)
    codes = [e["code"] for e in result]
    assert "E3" in codes
    assert next(e for e in result if e["code"] == "E3")["severity"] == "info"


def test_26nt_no_e3():
    seq = "UAGCUUAUCAGACUGAGAUCAAGCAG"  # 26 nt — exactly at limit, not over
    assert "E3" not in _codes(seq)


# ── E4: low GC warning ────────────────────────────────────────────

def test_low_gc_warning():
    # 25% GC: only A/U rich sequence (22 nt)
    seq = "UUUUAUUAUUAUUAUUAUUAUU"  # mostly U/A → very low GC
    result = detect_edge_cases(seq)
    assert "E4" in _codes(seq)
    assert next(e for e in result if e["code"] == "E4")["severity"] == "warning"


# ── E5: high GC warning ───────────────────────────────────────────

def test_high_gc_warning():
    # ~77% GC
    seq = "CGCGCGCGCGCGCGCGCGCGAU"  # 22 nt, 20 GC + 2 AU
    result = detect_edge_cases(seq)
    assert "E5" in _codes(seq)
    assert next(e for e in result if e["code"] == "E5")["severity"] == "warning"


# ── E6: homopolymer run ───────────────────────────────────────────

def test_homopolymer_run():
    seq = "UAGCUUAUCAGACUGAGGGGG"  # 5 G run
    result = detect_edge_cases(seq)
    assert "E6" in _codes(seq)
    assert next(e for e in result if e["code"] == "E6")["severity"] == "warning"


def test_poly_g_4_triggers_e6():
    seq = "UAGCUUAUCAGACUGAGGGG"  # 4 G run → POLY_G_RUN_MIN = 4
    assert "E6" in _codes(seq)


# ── E7: low complexity ────────────────────────────────────────────

def test_low_complexity_info():
    # Two dominant bases (AU): "AUAUAUAUAUAUAUAUAUAUAU" — 22 nt, 100% A/U
    seq = "AUAUAUAUAUAUAUAUAUAUAU"
    assert "E7" in _codes(seq)
    assert _severities(seq).get("E7") == "info"


# ── E8: ambiguous base critical ───────────────────────────────────

def test_ambiguous_base_critical():
    seq = "UAGCUUANCAGACUGAGAUC"  # N in sequence
    result = detect_edge_cases(seq)
    assert "E8" in _codes(seq)
    e8 = next(e for e in result if e["code"] == "E8")
    assert e8["severity"] == "critical"
    assert "N" in str(e8["value"])


def test_e8_returns_immediately():
    """When E8 found, no other rules evaluated."""
    seq = "NNNNN"
    result = detect_edge_cases(seq)
    assert len(result) == 1
    assert result[0]["code"] == "E8"


# ── Normal miRNA → no edge cases ─────────────────────────────────

def test_normal_mirna_no_edge_cases():
    """hsa-miR-21-5p: 23 nt, GC ~52%, no runs — should return []."""
    seq = "UAGCUUAUCAGACUGAUGUUGA"  # 22 nt, realistic hsa-miR-21-5p
    result = detect_edge_cases(seq)
    assert result == [], f"Expected no edge cases, got: {result}"


def test_result_structure():
    """Each result has required keys."""
    seq = "UAGCUUAUCA"  # 10 nt → triggers E1
    result = detect_edge_cases(seq)
    assert result
    for e in result:
        for key in ("code", "severity", "message", "value"):
            assert key in e, f"Missing key {key} in {e}"


if __name__ == "__main__":
    test_short_mirna_critical()
    test_short_mirna_17_critical()
    test_borderline_short_warning()
    test_19nt_is_warning()
    test_long_mirna_info()
    test_26nt_no_e3()
    test_low_gc_warning()
    test_high_gc_warning()
    test_homopolymer_run()
    test_poly_g_4_triggers_e6()
    test_low_complexity_info()
    test_ambiguous_base_critical()
    test_e8_returns_immediately()
    test_normal_mirna_no_edge_cases()
    test_result_structure()
    print("\nAll edge_cases tests passed.")
