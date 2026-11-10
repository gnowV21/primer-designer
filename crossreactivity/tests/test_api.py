"""Matrix API (crossreactivity/api.py) on a small hand-made long table."""

import pandas as pd
import pytest

from crossreactivity.api import CrossReactivity, aggregate_expression

LONG = pd.DataFrame([
    # assay, target, R, level
    ("A", "A", 1.0, "HIGH"), ("A", "B", 0.5, "HIGH"),
    ("B", "B", 1.0, "HIGH"), ("B", "A", 0.02, "LOW"),
    ("C", "C", 1.0, "HIGH"), ("C", "B", 0.2, "HIGH"),
    ("D", "D", 1.0, "HIGH"), ("D", "A", 0.06, "MEDIUM"),
], columns=["assay_mirna", "target_mirna", "R", "level"])


@pytest.fixture
def xr():
    return CrossReactivity(LONG)


def test_get_risk_and_unstored_pairs(xr):
    assert xr.get_risk("A", "B")["R"] == 0.5
    assert xr.get_risk("A", "C") == {"assay_mirna": "A", "target_mirna": "C",
                                     "R": 0.0, "level": "NONE"}
    with pytest.raises(KeyError):
        xr.get_risk("Z", "A")


def test_submatrix_is_asymmetric_and_nan_for_missing_assays(xr):
    m = xr.submatrix(["A", "B", "Z"])
    assert m.loc["A", "B"] == 0.5 and m.loc["B", "A"] == 0.02
    assert m.loc["Z"].isna().all() and m.loc["A", "Z"] == 0.0


def test_groups_symmetrise_with_max_and_chain(xr):
    g = xr.assay_resolvable_groups(["A", "B", "C", "D"], threshold=0.1)
    # A–B (0.5) and B–C (0.2) chain A, B and C; D–A is 0.06 < 0.1
    assert g["A"] == g["B"] == g["C"] == "A/B/C"
    assert g["D"] == "D"
    rep = xr.group_report(g).set_index("unit")
    assert rep.loc["A/B/C", "min_link_R"] == 0.0          # A and C: chained, not linked
    assert rep.loc["A/B/C", "max_link_R"] == 0.5


def test_threshold_controls_grouping(xr):
    g = xr.assay_resolvable_groups(["A", "D"], threshold=0.05)
    assert g["A"] == g["D"] == "A/D"


def test_aggregate_expression_sum_and_layouts():
    groups = {"A": "A/B", "B": "A/B", "C": "C"}
    expr = pd.DataFrame({"A": [1.0, 2.0], "B": [3.0, 4.0], "C": [5.0, 6.0], "E": [7.0, 8.0]},
                        index=["s1", "s2"])
    out = aggregate_expression(expr, groups)
    assert list(out.columns) == ["A/B", "C", "E"]
    assert out.loc["s1", "A/B"] == 4.0 and out.loc["s2", "E"] == 8.0
    by_index = aggregate_expression(expr.T, groups, mirna_axis="index")
    pd.testing.assert_frame_equal(by_index, out.T)
    assert aggregate_expression(expr, groups, method="max").loc["s2", "A/B"] == 4.0


def test_aggregate_rejects_unknown_method():
    with pytest.raises(ValueError):
        aggregate_expression(pd.DataFrame(), {}, method="median")
