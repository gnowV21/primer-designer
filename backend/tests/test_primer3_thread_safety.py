# ================================================================
# tests/test_primer3_thread_safety.py
#
# primer3-py's thermodynamic C code is not thread-safe (process-global state, GIL
# released): concurrent Flask requests crashed the server with an access
# violation (2026-10-28). All app code must go through algorithm/primer3_safe.py.
# ================================================================

import concurrent.futures as cf
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import algorithm.primer3_safe as p3s

_BACKEND = os.path.join(os.path.dirname(__file__), "..")


def test_no_direct_primer3_import_in_app_code():
    offenders = []
    for top in ("algorithm", "routes", "visualization", "app.py"):
        root = os.path.join(_BACKEND, top)
        files = [root] if root.endswith(".py") else [
            os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs if f.endswith(".py")]
        for path in files:
            if path.endswith("primer3_safe.py") or os.sep + "test_" in path:
                continue
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    if re.match(r"\s*(import primer3\b(?!_)|from primer3\b)", line):
                        offenders.append(f"{os.path.relpath(path, _BACKEND)}:{n}")
    assert not offenders, f"import algorithm.primer3_safe as primer3 instead: {offenders}"


def test_wrapped_calls_hold_the_lock(monkeypatch):
    seen = []
    real = p3s._primer3.calc_homodimer
    monkeypatch.setattr(p3s._primer3, "calc_homodimer",
                        lambda *a, **k: (seen.append(p3s._LOCK.locked()), real(*a, **k))[1])
    wrapped = p3s._locked(p3s._primer3.calc_homodimer)
    wrapped("ACGTACGTACGTACGTAC")
    assert seen == [True]


def test_concurrent_thermo_calls_complete():
    seqs = ["CGCTGCTCTAGCTTATCAGACTG", "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACTCAACA",
            "CCAGTGCAGGGTCCGAGGTA", "ACCGCCATTGAGGTAGTAGGT"]
    def work(i):
        a, b = seqs[i % 4], seqs[(i + 1) % 4]
        return (p3s.calc_homodimer(a).dg, p3s.calc_heterodimer(a, b).dg,
                p3s.calc_hairpin(b).dg, p3s.calc_tm(a))
    with cf.ThreadPoolExecutor(8) as ex:
        results = list(ex.map(work, range(200)))
    assert len(results) == 200
    assert results[0] == results[4]          # same inputs → same outputs under contention
