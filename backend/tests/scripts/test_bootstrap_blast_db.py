"""Tests for bootstrap_blast_db.py (Phase 7 PART A)."""

import os
import sys
from unittest.mock import patch

import pytest

# Ensure backend package importable
_BACKEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from scripts.bootstrap_blast_db import db_is_present, run, _REQUIRED, _DB_DIR, _METADATA


def _make_present(tmp_path, monkeypatch):
    """Patch _DB_DIR + _METADATA + _REQUIRED to point at tmp_path with all files present."""
    db_dir = str(tmp_path / "blast_db")
    os.makedirs(db_dir)
    for f in _REQUIRED:
        open(os.path.join(db_dir, f), "w").close()
    metadata = os.path.join(db_dir, "metadata.json")
    open(metadata, "w").write("{}")
    monkeypatch.setattr("scripts.bootstrap_blast_db._DB_DIR", db_dir)
    monkeypatch.setattr("scripts.bootstrap_blast_db._METADATA", metadata)
    monkeypatch.setattr("scripts.bootstrap_blast_db._REQUIRED", _REQUIRED)
    return db_dir, metadata


class TestDbIsPresent:
    def test_all_files_present(self, tmp_path, monkeypatch):
        _make_present(tmp_path, monkeypatch)
        assert db_is_present() is True

    def test_missing_file(self, tmp_path, monkeypatch):
        db_dir = str(tmp_path / "blast_db")
        os.makedirs(db_dir)
        # Only create 2 of 3 required files
        for f in list(_REQUIRED)[:2]:
            open(os.path.join(db_dir, f), "w").close()
        monkeypatch.setattr("scripts.bootstrap_blast_db._DB_DIR", db_dir)
        monkeypatch.setattr("scripts.bootstrap_blast_db._METADATA", os.path.join(db_dir, "metadata.json"))
        monkeypatch.setattr("scripts.bootstrap_blast_db._REQUIRED", _REQUIRED)
        assert db_is_present() is False

    def test_empty_dir(self, tmp_path, monkeypatch):
        db_dir = str(tmp_path / "blast_db_empty")
        os.makedirs(db_dir)
        monkeypatch.setattr("scripts.bootstrap_blast_db._DB_DIR", db_dir)
        monkeypatch.setattr("scripts.bootstrap_blast_db._METADATA", os.path.join(db_dir, "metadata.json"))
        monkeypatch.setattr("scripts.bootstrap_blast_db._REQUIRED", _REQUIRED)
        assert db_is_present() is False


class TestRun:
    """run() never raises; it returns False when a build fails. Release checks:
    tests/test_mirbase_pin.py."""

    def test_db_present_skip(self, tmp_path, monkeypatch):
        """BLAST DB and lookup DB on the pinned release → nothing is built."""
        with patch("scripts.bootstrap_blast_db.blast_db_ok", return_value=True),              patch("scripts.bootstrap_blast_db.lookup_db_ok", return_value=True),              patch("scripts.bootstrap_blast_db.db_is_present", return_value=True),              patch("scripts.bootstrap_blast_db.metadata_sha256",
                   return_value=__import__("scripts.mirbase_pin").mirbase_pin.pinned_sha256()),              patch("scripts.bootstrap_blast_db._build_blast") as b1,              patch("scripts.bootstrap_blast_db._build_lookup") as b2:
            result = run()
        assert result is True
        b1.assert_not_called()
        b2.assert_not_called()

    def test_build_failure_does_not_crash(self, tmp_path, monkeypatch):
        """Build failure must log error and return False — app should not crash."""
        with patch("scripts.bootstrap_blast_db.blast_db_ok", return_value=False),              patch("scripts.bootstrap_blast_db.db_is_present", return_value=False),              patch("scripts.bootstrap_blast_db.lookup_db_ok", return_value=True),              patch("scripts.bootstrap_blast_db._build_blast",
                   side_effect=RuntimeError("makeblastdb crashed")):
            result = run()
        assert result is False

    def test_build_exit_does_not_crash(self, tmp_path, monkeypatch):
        """build_blast_db exits (sha256 wrong / no makeblastdb) → False, no SystemExit."""
        with patch("scripts.bootstrap_blast_db.blast_db_ok", return_value=False),              patch("scripts.bootstrap_blast_db.db_is_present", return_value=False),              patch("scripts.bootstrap_blast_db.lookup_db_ok", return_value=True),              patch("scripts.bootstrap_blast_db._build_blast", side_effect=SystemExit(2)):
            result = run()
        assert result is False
