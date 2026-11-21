"""BLAST+ usage report off for every BLAST subprocess (speed plan 2, step 2).

BLAST+ reports each run to NCBI unless BLAST_USAGE_REPORT=false; that call added
~1 s per blastn / blastdbcmd and hung 30–35 s on a slow network
(docs/REVIEW_panel_4.0.0.md §10–11). A value the user set is kept.
"""
import os
import subprocess
import sys

import pytest

from algorithm.specificity_check import blast_offtarget as bo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_blast_db  # noqa: E402


def test_usage_report_off_when_unset(monkeypatch):
    monkeypatch.delenv("BLAST_USAGE_REPORT", raising=False)
    env, _ = bo._blast_env_and_name(bo._MIRBASE_DB)
    assert env["BLAST_USAGE_REPORT"] == "false"
    assert "BLAST_USAGE_REPORT" not in os.environ          # the process env is untouched


@pytest.mark.parametrize("value", ["true", "1", ""])
def test_user_value_kept(monkeypatch, value):
    monkeypatch.setenv("BLAST_USAGE_REPORT", value)
    env, _ = bo._blast_env_and_name(bo._MIRBASE_DB)
    assert env["BLAST_USAGE_REPORT"] == value


def test_blastdb_and_name_unchanged(monkeypatch, tmp_path):
    monkeypatch.delenv("BLAST_USAGE_REPORT", raising=False)
    db = str(tmp_path / "dir with space" / "mirbase_multi")
    env, name = bo._blast_env_and_name(db)
    assert env["BLASTDB"] == os.path.normpath(os.path.dirname(os.path.abspath(db)))
    assert name == "mirbase_multi"
    # everything else is the caller's environment, as before
    assert {k: v for k, v in env.items() if k not in ("BLASTDB", "BLAST_USAGE_REPORT")} == {
        k: v for k, v in os.environ.items() if k != "BLASTDB"}


def test_every_engine_blast_call_gets_the_env(monkeypatch):
    """run_blastn, run_blastn_multi (blastn) and fetch_sequences (blastdbcmd)."""
    monkeypatch.delenv("BLAST_USAGE_REPORT", raising=False)
    seen = []

    def fake_run(cmd, **kw):
        seen.append((cmd[0], kw.get("env", {}).get("BLAST_USAGE_REPORT")))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(bo.subprocess, "run", fake_run)
    bo.run_blastn("ACGTACGTACGTACGT", bo._MIRBASE_DB)
    bo.run_blastn_multi(["ACGTACGTACGTACGT", "TTGGCCAATTGGCCAA"], bo._MIRBASE_DB, processes=2)
    bo.fetch_sequences(["hsa-miR-21-5p"], bo._MIRBASE_DB)
    assert [c for c, _ in seen] == ["blastn", "blastn", "blastn", "blastdbcmd"]
    assert all(v == "false" for _, v in seen)


def test_build_script_env(monkeypatch):
    monkeypatch.delenv("BLAST_USAGE_REPORT", raising=False)
    assert build_blast_db._blast_env(BLASTDB="x") == {**os.environ, "BLASTDB": "x",
                                                     "BLAST_USAGE_REPORT": "false"}
    monkeypatch.setenv("BLAST_USAGE_REPORT", "true")
    assert build_blast_db._blast_env()["BLAST_USAGE_REPORT"] == "true"
