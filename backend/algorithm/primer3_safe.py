# ================================================================
# primer3_safe.py — thread-safe access to primer3-py
#
# primer3-py 2.x releases the GIL inside its C thermodynamic code (thal: hairpin,
# homo-/hetero-dimer) and that code keeps process-global state. Two Flask request
# threads computing at once crash the whole server with an access violation —
# reproduced 2026-10-28 by Playwright's parallel workers, faulthandler trace:
# calc_homodimer in one thread while calc_heterodimer ran in another. v3.2.0 scores
# ~40x more candidates per design, which turned a rare race into a frequent one.
#
# Every primer3 call goes through one process-wide lock. Import this module in
# place of primer3 (`import algorithm.primer3_safe as primer3`) so call sites stay
# unchanged. Calls are serialized; within one request they already were.
# ================================================================

import functools
import threading

import primer3 as _primer3

_LOCK = threading.Lock()


def _locked(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _LOCK:
            return fn(*args, **kwargs)
    return wrapper


calc_tm          = _locked(_primer3.calc_tm)
calc_hairpin     = _locked(_primer3.calc_hairpin)
calc_homodimer   = _locked(_primer3.calc_homodimer)
calc_heterodimer = _locked(_primer3.calc_heterodimer)

__version__ = _primer3.__version__
