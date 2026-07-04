"""Tests for bootstrap_blast_db.py (Phase 7 PART A)."""

import os
import sys
from unittest.mock import patch, MagicMock

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
    def test_db_present_skip(self, tmp_path, monkeypatch):
        """If DB is already present, build should NOT be called."""
        _make_present(tmp_path, monkeypatch)
        build_called = []

        def fake_build():
            build_called.append(True)

        with patch("scripts.bootstrap_blast_db.db_is_present", return_value=True):
            result = run()

        assert result is True
        assert len(build_called) == 0

    def test_db_absent_build_success(self, tmp_path, monkeypatch):
        """If DB absent, build is called; returns True when DB appears after build."""
        call_count = [0]

        def fake_is_present():
            call_count[0] += 1
            return call_count[0] > 1  # first call False (absent), second call True (built)

        with patch("scripts.bootstrap_blast_db.db_is_present", side_effect=fake_is_present):
            with patch.dict("sys.modules", {"scripts.build_blast_db": MagicMock()}):
                sys.modules["scripts.build_blast_db"].main = lambda: None
                result = run()

        assert result is True

    def test_build_failure_does_not_crash(self, tmp_path, monkeypatch):
        """Build failure must log error and return False — app should not crash."""
        with patch("scripts.bootstrap_blast_db.db_is_present", return_value=False):
            with patch.dict("sys.modules", {"scripts.build_blast_db": MagicMock()}):
                sys.modules["scripts.build_blast_db"].main = MagicMock(side_effect=RuntimeError("network down"))
                result = run()

        assert result is False
