"""
example.py — the matrix API end to end, on the real matrix and a toy RPM table.

    python -m crossreactivity.example
"""

import os

import numpy as np
import pandas as pd

from crossreactivity.api import CrossReactivity, aggregate_expression

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

xr = CrossReactivity.load(os.path.join(_ROOT, "outputs", "crossreactivity_long.parquet"))

# 1. One pair: how much signal does the let-7a assay get from let-7d?
print(xr.get_risk("hsa-let-7a-5p", "hsa-let-7d-5p"))

# 2. An N×N block (rows = assay, columns = miRNA measured); asymmetric.
let7 = ["hsa-let-7a-5p", "hsa-let-7b-5p", "hsa-let-7c-5p", "hsa-let-7d-5p", "hsa-let-7e-5p"]
print((100 * xr.submatrix(let7)).round(2))

# 3. Units the assays cannot resolve (symmetrised max R ≥ 10 % → same unit).
panel = let7 + ["hsa-miR-17-5p", "hsa-miR-20a-5p", "hsa-miR-106a-5p", "hsa-miR-21-5p"]
groups = xr.assay_resolvable_groups(panel)
print(xr.group_report(groups))

# 4. Collapse an expression matrix (samples × miRNAs, RPM) onto those units.
rng = np.random.default_rng(0)
rpm = pd.DataFrame(rng.lognormal(3, 1, size=(4, len(panel))), columns=panel,
                   index=[f"TCGA-sample-{i}" for i in range(4)])
features = aggregate_expression(rpm, groups, method="sum")
print(features.round(1))
