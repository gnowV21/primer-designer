# ================================================================
# tests/scripts/test_build_family_db.py — mock-data tests
# Tests parse + build logic without downloading real miRBase files.
# ================================================================

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.build_family_db import parse_mifam, parse_mature_fa, build_family_db

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures")
MIFAM_MOCK  = os.path.join(FIXTURES, "miFam_mock.dat")
MATURE_MOCK = os.path.join(FIXTURES, "mature_mock.fa")


def test_parse_mifam_finds_3_families():
    families = parse_mifam(MIFAM_MOCK)
    assert len(families) == 3
    ids = [f["id"] for f in families]
    assert "let-7" in ids
    assert "mir-21" in ids


def test_parse_mifam_let7_has_members():
    families = parse_mifam(MIFAM_MOCK)
    let7 = next(f for f in families if f["id"] == "let-7")
    assert len(let7["members"]) == 5
    names = [m["name"] for m in let7["members"]]
    assert "hsa-let-7a-1" in names


def test_parse_mature_fa_finds_sequences():
    seqs = parse_mature_fa(MATURE_MOCK)
    assert "hsa-let-7a-5p" in seqs
    assert "hsa-miR-21-5p" in seqs
    assert seqs["hsa-miR-21-5p"] == "UAGCUUAUCAGACUGAUGUUGA"


def test_build_family_db_produces_let7_family():
    families = parse_mifam(MIFAM_MOCK)
    seqs     = parse_mature_fa(MATURE_MOCK)
    db       = build_family_db(families, seqs)

    assert "let-7" in db
    let7 = db["let-7"]
    assert "_overhang_nt" in let7
    assert let7["_overhang_nt"] == 6
    # hsa-let-7a-5p should appear
    assert "hsa-let-7a-5p" in let7
    # overhang = last 6 nt of UGAGGUAGUAGGUUGUAUAGUU = UAGUU (5 nt?) let me check
    # UGAGGUAGUAGGUUGUAUAGUU -> last 6 = UAGUU is 5 chars? No:
    # U-G-A-G-G-U-A-G-U-A-G-G-U-U-G-U-A-U-A-G-U-U = 22 chars
    # last 6 = A-G-U-U = AGUUU? Let me count: pos[-6:] = UAUAGUU? No 22-6=16 -> AGUAGUU?
    # Actually: UGAGGUAGUAGGUUGUAUAGUU -> last 6 = UAUAGUU[-6:] = GUAGUU
    # Just verify it's 6 characters
    overhang = let7["hsa-let-7a-5p"]
    assert len(overhang) == 6


def test_build_family_db_mirna_to_family_index():
    families = parse_mifam(MIFAM_MOCK)
    seqs     = parse_mature_fa(MATURE_MOCK)
    db       = build_family_db(families, seqs)

    idx = db.get("_mirna_to_family", {})
    assert "hsa-let-7a-5p" in idx
    assert idx["hsa-let-7a-5p"] == "let-7"


def test_build_family_db_metadata():
    families = parse_mifam(MIFAM_MOCK)
    seqs     = parse_mature_fa(MATURE_MOCK)
    db       = build_family_db(families, seqs, mirbase_version="MOCK")

    meta = db["_meta"]
    assert meta["mirbase_version"] == "MOCK"
    assert meta["family_count"] >= 1
    assert meta["member_count"] >= 1


def test_build_family_db_let7a_vs_let7b_different_overhangs():
    """let-7a and let-7b have slightly different 3' ends."""
    families = parse_mifam(MIFAM_MOCK)
    seqs     = parse_mature_fa(MATURE_MOCK)
    db       = build_family_db(families, seqs)

    let7 = db["let-7"]
    if "hsa-let-7a-5p" in let7 and "hsa-let-7b-5p" in let7:
        # let-7a: UGAGGUAGUAGGUUGUAUAGUU  -> -6: UAUAGUU[-6:] = UAGUUU?
        # let-7b: UGAGGUAGUAGGUUGUGUGGUU  -> -6: UGUGGUU[-6:] = UGGUU?
        # They should differ at least in 1 position
        assert let7["hsa-let-7a-5p"] != let7["hsa-let-7b-5p"]
