"""
api.py — read the cross-reactivity matrix and turn it into measurable units.

    from crossreactivity.api import CrossReactivity
    xr = CrossReactivity.load("outputs/crossreactivity_long.parquet")
    xr.get_risk("hsa-let-7a-5p", "hsa-let-7d-5p")          # → R, level, …
    xr.submatrix(["hsa-let-7a-5p", "hsa-let-7d-5p"])       # N×N DataFrame of R
    groups = xr.assay_resolvable_groups(mirnas, threshold=0.1)
    features = aggregate_expression(rpm, groups)            # samples × units

R(i, j) is the signal the assay designed for miRNA i (primer set #1) gets from
miRNA j, relative to its own target (R(i, i) = 1). Pairs not stored are NONE
(R < 2^-10 ≈ 0.1 %) and read as 0. The matrix is asymmetric.

Module-level functions load_matrix / get_risk / submatrix / assay_resolvable_groups
mirror the methods for callers that prefer plain functions.
"""

from __future__ import annotations

import json
import os
from typing import Iterable

import numpy as np
import pandas as pd

# CO-AMPLIFIED cut-off of the assay model: ΔCq < 3.3 ⇔ R > 2^-3.3 ≈ 0.10.
HIGH_R = 2.0 ** -3.3


class CrossReactivity:
    def __init__(self, long: pd.DataFrame, metadata: dict | None = None):
        self.long = long
        self.metadata = metadata or {}
        self._r = {(a, t): r for a, t, r in zip(long["assay_mirna"], long["target_mirna"], long["R"])}
        self._rows = long.set_index(["assay_mirna", "target_mirna"])
        self.assays = frozenset(long["assay_mirna"])

    @classmethod
    def load(cls, path: str) -> "CrossReactivity":
        """Read the long table (.parquet or .csv); the metadata JSON next to it, if any."""
        long = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)
        meta_path = os.path.join(os.path.dirname(path), "crossreactivity_metadata.json")
        meta = None
        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
        return cls(long, meta)

    def r(self, assay_mirna: str, target_mirna: str) -> float:
        """R(assay, target); 0 for unstored (NONE) pairs. KeyError when the assay was
        never designed — 0 would wrongly read as 'specific'."""
        if assay_mirna not in self.assays:
            raise KeyError(f"no assay for {assay_mirna!r} (not designed or not in the matrix)")
        return float(self._r.get((assay_mirna, target_mirna), 0.0))

    def get_risk(self, assay_mirna: str, target_mirna: str) -> dict:
        """Full record of one pair, or a NONE record when it is not stored."""
        r = self.r(assay_mirna, target_mirna)
        if r == 0.0:
            return {"assay_mirna": assay_mirna, "target_mirna": target_mirna,
                    "R": 0.0, "level": "NONE"}
        row = self._rows.loc[(assay_mirna, target_mirna)]
        return {"assay_mirna": assay_mirna, "target_mirna": target_mirna, **row.to_dict()}

    def submatrix(self, mirna_list: Iterable[str]) -> pd.DataFrame:
        """N×N DataFrame of R: rows = assay, columns = target. A miRNA with no assay
        gets a row of NaN (it can still appear as a target)."""
        names = list(dict.fromkeys(mirna_list))
        m = np.full((len(names), len(names)), np.nan)
        for i, a in enumerate(names):
            if a not in self.assays:
                continue
            for j, t in enumerate(names):
                m[i, j] = self._r.get((a, t), 0.0)
        return pd.DataFrame(m, index=pd.Index(names, name="assay"),
                            columns=pd.Index(names, name="target"))

    def assay_resolvable_groups(self, mirna_list: Iterable[str],
                                threshold: float = HIGH_R) -> dict[str, str]:
        """Group miRNAs the assays cannot tell apart into measurable units.

        Symmetrised as S(i, j) = max(R(i, j), R(j, i)): if either assay picks up the
        other miRNA, their measurements are entangled. Units are the connected
        components of the graph S ≥ threshold (default: the CO-AMPLIFIED cut-off,
        R > ~10 %). Components can chain — A~B and B~C put A and C together even if
        A and C are resolved; see group_report() for the weakest link of each unit.

        Returns {miRNA: unit name}; the unit name joins the sorted members with '/'.
        A miRNA without an assay is placed by the assays of the others only.
        """
        names = list(dict.fromkeys(mirna_list))
        parent = {n: n for n in names}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for i, a in enumerate(names):
            for b in names[i + 1:]:
                s = max(self._r.get((a, b), 0.0), self._r.get((b, a), 0.0))
                if s >= threshold:
                    ra, rb = find(a), find(b)
                    if ra != rb:
                        parent[rb] = ra
        members: dict[str, list[str]] = {}
        for n in names:
            members.setdefault(find(n), []).append(n)
        return {n: "/".join(sorted(members[find(n)])) for n in names}

    def group_report(self, groups: dict[str, str]) -> pd.DataFrame:
        """One row per unit: size, members, and the weakest and strongest symmetrised
        link inside it (a low min_link_R flags a chained component)."""
        out = []
        for unit in sorted(set(groups.values())):
            ms = unit.split("/")
            links = [max(self._r.get((a, b), 0.0), self._r.get((b, a), 0.0))
                     for i, a in enumerate(ms) for b in ms[i + 1:]]
            out.append({"unit": unit, "size": len(ms),
                        "min_link_R": min(links) if links else None,
                        "max_link_R": max(links) if links else None})
        return pd.DataFrame(out)


def aggregate_expression(expr_df: pd.DataFrame, groups: dict[str, str],
                         method: str = "sum", mirna_axis: str = "columns") -> pd.DataFrame:
    """Collapse a miRNA expression matrix onto measurable units (ML features).

    expr_df: expression in RPM (e.g. TCGA-BRCA miRNA-seq), miRNAs on `mirna_axis`
        ('columns': samples × miRNAs, the usual ML layout; 'index': miRNAs × samples,
        the TCGA file layout). Names must be miRBase 22.1 mature names, as in the
        matrix — map MIMAT accessions or older names first.
    groups: assay_resolvable_groups() output. miRNAs absent from `groups` stay as
        their own feature.
    method: 'sum' (default — the qPCR signal of a unit is the sum of what its assay
        detects), 'mean' or 'max'.
    Returns samples × units (or units × samples for mirna_axis='index').
    """
    if method not in ("sum", "mean", "max"):
        raise ValueError("method must be 'sum', 'mean' or 'max'")
    if mirna_axis not in ("columns", "index"):
        raise ValueError("mirna_axis must be 'columns' or 'index'")
    df = expr_df if mirna_axis == "columns" else expr_df.T
    labels = [groups.get(c, c) for c in df.columns]
    agg = df.T.groupby(labels, sort=True).agg(method).T
    return agg if mirna_axis == "columns" else agg.T


# ── plain-function facade ─────────────────────────────────────────

_loaded: dict[str, CrossReactivity] = {}


def load_matrix(path: str) -> CrossReactivity:
    if path not in _loaded:
        _loaded[path] = CrossReactivity.load(path)
    return _loaded[path]


def _current() -> CrossReactivity:
    if not _loaded:
        raise RuntimeError("call load_matrix(path) first")
    return next(reversed(_loaded.values()))


def get_risk(assay_mirna: str, target_mirna: str) -> dict:
    return _current().get_risk(assay_mirna, target_mirna)


def submatrix(mirna_list: Iterable[str]) -> pd.DataFrame:
    return _current().submatrix(mirna_list)


def assay_resolvable_groups(mirna_list: Iterable[str], threshold: float = HIGH_R) -> dict[str, str]:
    return _current().assay_resolvable_groups(mirna_list, threshold)
