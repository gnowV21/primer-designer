# ================================================================
# tests/test_design_speed.py — perf/design-speed (docs/REVIEW_panel_4.0.0.md §8)
#
# Bước 2: the memoised duplex Tm and table-only forward ΔCq return exactly what the
# direct computation returns, and BLAST_CACHE_PATH moves the cache file only.
# Bước 3: hit classification of a batch in the process pool gives exactly the
# in-process result, in input order; no nested pool; a broken pool falls back.
# ================================================================

import json
import multiprocessing
import os
from concurrent.futures.process import BrokenProcessPool

import pytest

import algorithm.primer3_safe as primer3
from algorithm.constants import BLAST_CLASSIFY_MIN_PRIMERS, UNIVERSAL_REVERSE
from algorithm.forward_primer import generate_forward_candidates
from algorithm.specificity_check import blast_offtarget as bo
from algorithm.specificity_check import overhang_collision as oc
from algorithm.specificity_check.assay_model import fwd_axis
from algorithm.specificity_check.blast_cache import BlastCache
from algorithm.thermodynamics import _get_p3_params

_P3 = _get_p3_params({})
_PAIRS = [("TAGCTTATCAGACTG", "TAGCTTATCAGACTGA"), ("TGAGGTAGTAGGTTG", "AGAGGTAGTAGGTTGC"),
          ("TAATTTTATGTATAA", "TAATTTTATGTATAAG")]


def test_duplex_tm_memo_equals_direct():
    for region, window in _PAIRS:
        direct = float(primer3.calc_heterodimer(region, oc._revcomp(window), **_P3).tm)
        assert oc._duplex_tm(region, window, _P3) == direct
        assert oc._duplex_tm(region, window, dict(_P3)) == direct      # cached path


def test_fwd_table_memo_equals_direct():
    for region, other in _PAIRS:
        assert oc._fwd_table_dcq(region, other) == fwd_axis(region, other, None)["delta_cq"]
        assert oc._fwd_table_dcq(region, other) == fwd_axis(region, other, None)["delta_cq"]


def test_memo_is_bounded():
    assert oc._duplex_tm_memo.cache_info().maxsize == oc._MEMO_SIZE
    assert oc._fwd_table_dcq.cache_info().maxsize == oc._MEMO_SIZE


def test_blast_cache_path_env(monkeypatch, tmp_path):
    p = tmp_path / "other.sqlite"
    monkeypatch.setenv("BLAST_CACHE_PATH", str(p))
    bc = BlastCache()
    assert os.path.abspath(bc.db_path) == os.path.abspath(str(p))
    key = BlastCache._compute_key("ACGT", "CCAGT", "v", "hsa-miR-1", "ctx")
    monkeypatch.delenv("BLAST_CACHE_PATH")
    assert BlastCache._compute_key("ACGT", "CCAGT", "v", "hsa-miR-1", "ctx") == key   # key unchanged
    assert os.path.abspath(BlastCache().db_path) != os.path.abspath(str(p))


# ── Bước 3: hit classification in worker processes ──────────────────────────────

_LET7A = "UGAGGUAGUAGGUUGUAUAGUU"
_LET7A_DNA = "TGAGGTAGTAGGTTGTATAGTT"
# Hits with every kind of classification: identical copy, cross-species, name self-hit,
# 3'-anchored plus-strand off-targets with 1-3 mismatches (Tm gate, RT step).
_SUBJECTS = {
    "hsa-let-7a-2-5p": _LET7A_DNA,                     # self-hit (precursor copy)
    "hsa-let-7a-copy": _LET7A_DNA,                     # identical sequence
    "hsa-let-7c-5p": "TGAGGTAGTAGGTTGTATGGTT",
    "hsa-let-7b-5p": "TGAGGTAGTAGGTTGTGTGGTT",
    "hsa-let-7f-5p": "TGAGGTAGTAGATTGTATAGTT",
    "hsa-miR-98-5p": "TGAGGTAGTAAGTTGTATTGTT",
    "mmu-let-7a-5p": _LET7A_DNA,                       # other species
}


@pytest.fixture
def fresh_pool():
    bo._discard_pool()
    yield
    bo._discard_pool()


def _primers(n):
    cands, _ = generate_forward_candidates(_LET7A, {}, gc_prefilter=False)
    seqs = sorted({c["sequence"] for c in cands})
    assert len(seqs) >= n
    return seqs[:: max(1, len(seqs) // n)][:n]


def _stub_blast(monkeypatch):
    def hits(primer):
        out = []
        for sid, subj in _SUBJECTS.items():
            L = min(len(primer), len(subj)) - 4
            out.append({"subject_id": sid, "identity_pct": 90.0, "length": L, "mismatches": 1,
                        "gap_opens": 0, "q_start": len(primer) - L + 1, "q_end": len(primer),
                        "s_start": 1, "s_end": L, "evalue": 0.5, "bitscore": 20.0,
                        "subject_seq": subj[:L], "query_seq": primer[-L:]})
        return out
    monkeypatch.setattr(bo, "run_blastn_multi",
                        lambda primers, db, timeout=60, processes=None: {p: hits(p) for p in primers})
    monkeypatch.setattr(bo, "fetch_sequences",
                        lambda ids, db, timeout=60: {i: _SUBJECTS[i] for i in ids if i in _SUBJECTS})
    monkeypatch.setattr(bo, "_db_exists", lambda p: True)


def _batch(primers, rt="GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACAACTAT"):
    return bo.check_offtarget_batch(primers, UNIVERSAL_REVERSE, mirna_id="hsa-let-7a-5p",
                                    target_sequence=_LET7A_DNA, species="hsa", rt_primer=rt)


def _dump(out):
    return json.dumps(out, sort_keys=True)


def test_pool_equals_in_process(monkeypatch, fresh_pool):
    _stub_blast(monkeypatch)
    primers = _primers(BLAST_CLASSIFY_MIN_PRIMERS + 4)
    monkeypatch.setenv("BLAST_CLASSIFY_PROCESSES", "1")
    seq = _batch(primers)
    assert bo._POOL is None
    monkeypatch.setenv("BLAST_CLASSIFY_PROCESSES", "3")
    par = _batch(primers)
    assert bo._POOL is not None                       # the pool did the work
    assert list(par) == list(seq)                     # input order
    assert _dump(par) == _dump(seq)
    r = next(iter(seq.values()))
    assert r["identical_sequence_hits"] and r["summary"]["cross_species_excluded"] >= 1   # really classified
    assert any(x["forward_primer_hits"] for x in seq.values())
    pool = bo._POOL
    assert _dump(_batch(primers)) == _dump(seq) and bo._POOL is pool         # one pool per run


@pytest.mark.skipif(not bo.blast_available()[0], reason="BLAST+ or the miRBase DB missing")
def test_pool_equals_in_process_live(monkeypatch, fresh_pool):
    primers = _primers(BLAST_CLASSIFY_MIN_PRIMERS)
    monkeypatch.setenv("BLAST_CLASSIFY_PROCESSES", "1")
    seq = _batch(primers)
    monkeypatch.setenv("BLAST_CLASSIFY_PROCESSES", "4")
    assert _dump(_batch(primers)) == _dump(seq)


def test_small_batch_stays_in_process(monkeypatch, fresh_pool):
    _stub_blast(monkeypatch)
    monkeypatch.setenv("BLAST_CLASSIFY_PROCESSES", "4")
    _batch(_primers(3))
    assert bo._POOL is None


def test_no_nested_pool(monkeypatch):
    monkeypatch.setenv("BLAST_CLASSIFY_PROCESSES", "4")
    assert bo._classify_processes() == min(4, os.cpu_count() or 1)
    monkeypatch.setattr(multiprocessing, "parent_process", lambda: object())
    assert bo._classify_processes() == 1


def test_broken_pool_falls_back(monkeypatch, fresh_pool):
    _stub_blast(monkeypatch)
    primers = _primers(BLAST_CLASSIFY_MIN_PRIMERS)
    monkeypatch.setenv("BLAST_CLASSIFY_PROCESSES", "1")
    seq = _batch(primers)

    def broken(k):
        raise BrokenProcessPool("worker died")
    monkeypatch.setattr(bo, "_classify_pool", broken)
    monkeypatch.setenv("BLAST_CLASSIFY_PROCESSES", "3")
    assert _dump(_batch(primers)) == _dump(seq)


_OWNER = r'''
import os, sys, time
sys.path.insert(0, os.getcwd())
from algorithm.specificity_check import blast_offtarget as bo
pool = bo._classify_pool(3)
list(pool.map(abs, range(30)))          # start the workers
print(" ".join(str(p) for p in pool._processes), flush=True)
time.sleep(600)
'''


def test_workers_exit_when_owner_is_killed():
    """A process that owns the classify pool and is killed without shutting it down
    (a dev server stopped hard) must not leave its workers running."""
    import subprocess
    import sys
    import time
    psutil = pytest.importorskip("psutil")
    backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    owner = subprocess.Popen([sys.executable, "-c", _OWNER], cwd=backend, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             stdin=subprocess.DEVNULL)
    pids = []
    try:
        pids = [int(x) for x in owner.stdout.readline().split()]
        assert len(pids) == 3
        owner.kill()
        owner.wait(timeout=30)
        deadline = time.monotonic() + 15
        alive = pids
        while alive and time.monotonic() < deadline:
            time.sleep(0.2)
            alive = [p for p in pids if psutil.pid_exists(p)
                     and psutil.Process(p).status() != psutil.STATUS_ZOMBIE]
        assert alive == [], f"pool workers still running after the owner was killed: {alive}"
    finally:
        owner.kill()
        owner.stdout.close()
        for p in pids:
            try:
                psutil.Process(p).kill()
            except psutil.Error:
                pass
