"""miRBase 22.1 pinned for every build (deploy/vercel, step 1).

The BLAST DB, db/mirbase.db and the overhang / family indexes must come from the
same mature.fa (Release 22.1, sha256 3c521fc9…, 48,885 mature). The file is
committed (backend/data/mirbase_22.1/mature.fa.gz); every build checks its sha256
and refuses another file; the server reports BLAST unavailable for a DB built from
another file.
"""
import gzip
import json
import shutil
import sqlite3

import pytest

from scripts import mirbase_pin as pin
from scripts import build_blast_db, build_db, bootstrap_blast_db
from algorithm.specificity_check import blast_offtarget as bo

SHA_22_1 = "3c521fc9bea3c7993e71cf188b11caf73e2d40ac83454e32876455317cc6d342"


@pytest.fixture(scope="module")
def pinned_bytes():
    data, sha = pin.load_mature_fa()
    return data


# ── the pinned file ───────────────────────────────────────────────

def test_pinned_file_is_22_1(pinned_bytes):
    assert pin.pinned_sha256() == SHA_22_1
    assert pin.sha256_hex(pinned_bytes) == SHA_22_1
    assert pin.count_entries(pinned_bytes) == pin.PINNED_ENTRIES == 48885


def test_pinned_file_is_the_overhang_index_file():
    assert pin.index_sha256() == SHA_22_1


def test_wrong_expected_sha_is_refused():
    with pytest.raises(pin.PinMismatch, match="sha256 mismatch"):
        pin.load_mature_fa(expected_sha256="0" * 64)


def test_tampered_file_is_refused(tmp_path, pinned_bytes):
    bad = tmp_path / "mature.fa.gz"
    bad.write_bytes(gzip.compress(pinned_bytes.replace(b"UAGCUUAUCAGACUGAUGUUGA",
                                                       b"UAGCUUAUCAGACUGAUGUUGG", 1)))
    with pytest.raises(pin.PinMismatch):
        pin.load_mature_fa(str(bad))


def test_plain_and_gzip_copies_both_accepted(tmp_path, pinned_bytes):
    plain = tmp_path / "mature.fa"
    plain.write_bytes(pinned_bytes)
    assert pin.load_mature_fa(str(plain))[1] == SHA_22_1


# ── build scripts refuse a wrong file before building anything ───

def _no_subprocess(monkeypatch):
    def boom(*a, **k):
        raise AssertionError(f"nothing may run before the sha256 check: {a[0]!r}")
    monkeypatch.setattr(build_blast_db.subprocess, "run", boom)


def test_build_blast_db_wrong_sha_exits_nonzero(tmp_path, monkeypatch, capsys):
    _no_subprocess(monkeypatch)
    out = tmp_path / "blast_db"
    with pytest.raises(SystemExit) as e:
        build_blast_db.main(["--out-dir", str(out), "--sha256", "0" * 64])
    assert e.value.code == 2
    assert "sha256 mismatch" in capsys.readouterr().err
    assert not out.exists()


def test_build_blast_db_tampered_fasta_exits_nonzero(tmp_path, monkeypatch, pinned_bytes):
    _no_subprocess(monkeypatch)
    bad = tmp_path / "mature.fa"
    bad.write_bytes(pinned_bytes + b">extra MIMAT9999999 x y\nACGU\n")
    with pytest.raises(SystemExit) as e:
        build_blast_db.main(["--out-dir", str(tmp_path / "db"), "--fasta", str(bad)])
    assert e.value.code == 2


def test_build_blast_db_never_downloads_without_flag(tmp_path, monkeypatch):
    _no_subprocess(monkeypatch)
    monkeypatch.setattr(pin, "download", lambda *a, **k: pytest.fail("downloaded"))
    with pytest.raises(SystemExit):
        build_blast_db.main(["--out-dir", str(tmp_path / "db"), "--sha256", "0" * 64])


def test_build_db_wrong_sha_exits_nonzero(tmp_path, capsys):
    out = tmp_path / "mirbase.db"
    assert build_db.main(["--out", str(out), "--sha256", "0" * 64]) == 2
    assert "sha256 mismatch" in capsys.readouterr().err
    assert not out.exists()


def test_build_db_has_all_48885_mature(tmp_path):
    out = tmp_path / "mirbase.db"
    assert build_db.main(["--out", str(out)]) == 0
    src = build_db.read_source(str(out))
    assert src["rows"] == 48885 and src["entries"] == "48885"
    assert src["mature_fa_sha256"] == SHA_22_1 and src["mirbase_release"] == "22.1"
    c = sqlite3.connect(str(out))
    row = c.execute("SELECT accession, sequence FROM mirna WHERE name='hsa-miR-21-5p'").fetchone()
    assert row == ("MIMAT0000076", "UAGCUUAUCAGACUGAUGUUGA")
    # the same indexes as db/local_db.py, so the app adds none at startup
    idx = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"idx_accession", "idx_sequence"} <= idx


def test_build_db_replaces_old_rows(tmp_path):
    """A rebuild keeps no row of the previous file (e.g. an online lookup cached
    before 3.8.2)."""
    out = tmp_path / "mirbase.db"
    c = sqlite3.connect(str(out))
    c.executescript(build_db.SCHEMA)
    c.execute("INSERT INTO mirna VALUES ('xxx-miR-online','','ACGU','','',4)")
    c.commit()
    c.close()
    assert build_db.main(["--out", str(out)]) == 0
    c = sqlite3.connect(str(out))
    assert c.execute("SELECT COUNT(*) FROM mirna WHERE name='xxx-miR-online'").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM mirna").fetchone()[0] == 48885


@pytest.mark.skipif(shutil.which("makeblastdb") is None, reason="makeblastdb not installed")
def test_build_blast_db_records_sha(tmp_path):
    out = tmp_path / "blast_db"
    assert build_blast_db.main(["--out-dir", str(out)]) == 0
    meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    assert meta["mature_fa_sha256"] == SHA_22_1 and meta["mirbase_version"] == "22.1"
    assert meta["sequences_count"]["mirbase_multi"] == 48885
    assert sorted(p.name for p in out.iterdir())[0] == "metadata.json"


# ── bootstrap ────────────────────────────────────────────────────

@pytest.fixture
def boot_dirs(tmp_path, monkeypatch):
    db_dir = tmp_path / "blast_db"
    db_dir.mkdir()
    monkeypatch.setattr(bootstrap_blast_db, "_DB_DIR", str(db_dir))
    monkeypatch.setattr(bootstrap_blast_db, "_METADATA", str(db_dir / "metadata.json"))
    monkeypatch.setattr(bootstrap_blast_db, "_LOOKUP_DB", str(tmp_path / "mirbase.db"))
    return db_dir


def _fake_blast_build(db_dir, sha):
    def build():
        for f in bootstrap_blast_db._REQUIRED:
            (db_dir / f).write_text("")
        (db_dir / "metadata.json").write_text(json.dumps({"mature_fa_sha256": sha}))
    return build


def test_bootstrap_refuses_when_index_is_another_release(boot_dirs, monkeypatch):
    monkeypatch.setattr(pin, "index_sha256", lambda: "f" * 64)
    monkeypatch.setattr(bootstrap_blast_db, "_build_blast", lambda: pytest.fail("built"))
    monkeypatch.setattr(bootstrap_blast_db, "_build_lookup", lambda: pytest.fail("built"))
    assert bootstrap_blast_db.run() is False


def test_bootstrap_blast_unavailable_when_db_sha_differs(boot_dirs, monkeypatch, caplog):
    monkeypatch.setattr(bootstrap_blast_db, "_build_blast", _fake_blast_build(boot_dirs, "e" * 64))
    monkeypatch.setattr(bootstrap_blast_db, "lookup_db_ok", lambda sha: True)
    assert bootstrap_blast_db.run() is False
    assert any("BLAST unavailable" in r.message and r.levelname == "ERROR" for r in caplog.records)


def test_bootstrap_builds_both_from_pinned(boot_dirs, monkeypatch):
    monkeypatch.setattr(bootstrap_blast_db, "_build_blast", _fake_blast_build(boot_dirs, SHA_22_1))
    assert bootstrap_blast_db.run() is True
    assert build_db.read_source(bootstrap_blast_db._LOOKUP_DB)["rows"] == 48885
    # second run: both kept
    monkeypatch.setattr(bootstrap_blast_db, "_build_blast", lambda: pytest.fail("rebuilt"))
    monkeypatch.setattr(bootstrap_blast_db, "_build_lookup", lambda: pytest.fail("rebuilt"))
    assert bootstrap_blast_db.run() is True


def test_bootstrap_rebuilds_db_without_recorded_sha(boot_dirs, monkeypatch):
    _fake_blast_build(boot_dirs, None)()          # legacy metadata: no sha256
    built = []
    monkeypatch.setattr(bootstrap_blast_db, "_build_blast",
                        lambda: (built.append(1), _fake_blast_build(boot_dirs, SHA_22_1)()))
    monkeypatch.setattr(bootstrap_blast_db, "lookup_db_ok", lambda sha: True)
    assert bootstrap_blast_db.run() is True and built == [1]


# ── the server: BLAST unavailable for a DB of another release ───

@pytest.fixture
def fake_db(tmp_path, monkeypatch):
    meta = tmp_path / "metadata.json"
    monkeypatch.setattr(bo, "_METADATA", str(meta))
    monkeypatch.setattr(bo, "_RELEASE_CHECK", {"key": None, "problem": None})
    monkeypatch.setattr(bo, "_db_exists", lambda p: True)
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/bin/{b}")
    return meta


def test_release_match_available(fake_db):
    fake_db.write_text(json.dumps({"mature_fa_sha256": SHA_22_1}))
    assert bo.blast_db_release_problem() is None
    assert bo.blast_available() == (True, None)


def test_release_mismatch_unavailable(fake_db):
    fake_db.write_text(json.dumps({"mature_fa_sha256": "a" * 64}))
    ok, why = bo.blast_available()
    assert ok is False and "another miRBase file" in why


def test_release_unknown_unavailable(fake_db):
    fake_db.write_text(json.dumps({"build_date": "2026-07-01"}))
    ok, why = bo.blast_available()
    assert ok is False and "no mature_fa_sha256" in why


def test_committed_metadata_matches_index():
    with open(bo._METADATA, encoding="utf-8") as f:
        assert json.load(f)["mature_fa_sha256"] == pin.index_sha256() == SHA_22_1


# ── /api/mirbase answers from the local DB, never the network ───

def test_api_mirbase_local_no_network(tmp_path, monkeypatch):
    from app import app
    from db import local_db
    import routes.mirbase as rm
    db = tmp_path / "mirbase.db"
    assert build_db.main(["--out", str(db)]) == 0
    monkeypatch.setattr(local_db, "DB_PATH", str(db))

    def no_net(*a, **k):
        raise AssertionError("network call")
    monkeypatch.setattr(rm.requests, "get", no_net)
    r = app.test_client().get("/api/mirbase/hsa-miR-21-5p")
    assert r.status_code == 200
    body = r.get_json()
    assert body["source"] == "local" and body["sequence"] == "UAGCUUAUCAGACUGAUGUUGA"
    assert body["accession"] == "MIMAT0000076"
    assert body["mirbase_release"] == "22.1" and body["mature_fa_sha256"] == SHA_22_1
