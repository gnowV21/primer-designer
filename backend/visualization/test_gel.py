"""PART D tests — agarose gel (SPEC §D.4, §F PART D)."""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from visualization.gel import simulate_gel                       # noqa: E402
from visualization.renderer import render_gel                    # noqa: E402
from visualization.constants import VIZ_GEL_LADDER_BP, VIZ_SIMULATED_LABEL  # noqa: E402


def test_y_monotonic_decreasing_with_bp():
    g = simulate_gel(100)
    ys = [y for _, y, _ in g.ladder_bands]
    bps = [bp for bp, _, _ in g.ladder_bands]
    # sorted by bp ascending → y should strictly decrease (larger fragment nearer well)
    order = sorted(zip(bps, ys))
    for (_, y1), (_, y2) in zip(order, order[1:]):
        assert y2 < y1


def test_product_63_between_50_and_75():
    g = simulate_gel(63)
    y_by_bp = {bp: y for bp, y, _ in g.ladder_bands}
    _, prod_y = g.product_band
    assert y_by_bp[75] < prod_y < y_by_bp[50]


def test_product_equal_to_ladder_matches_that_band():
    g = simulate_gel(100)
    y_by_bp = {bp: y for bp, y, _ in g.ladder_bands}
    _, prod_y = g.product_band
    assert abs(prod_y - y_by_bp[100]) <= 0.5


def test_out_of_range_low_is_clamped():
    g = simulate_gel(20)
    assert g.out_of_range is True
    _, prod_y = g.product_band
    ys = [y for _, y, _ in g.ladder_bands]
    assert min(ys) - 0.5 <= prod_y <= max(ys) + 0.5   # clamped within the lane


def test_out_of_range_high_is_clamped():
    g = simulate_gel(800)
    assert g.out_of_range is True
    _, prod_y = g.product_band
    ys = [y for _, y, _ in g.ladder_bands]
    assert min(ys) - 0.5 <= prod_y <= max(ys) + 0.5


def test_in_range_not_flagged():
    assert simulate_gel(120).out_of_range is False


def test_reference_bands_flagged():
    g = simulate_gel(100)
    refs = {bp for bp, _, is_ref in g.ladder_bands if is_ref}
    assert refs == {100, 200, 300, 400, 500}


def test_ladder_count():
    g = simulate_gel(100)
    assert [bp for bp, _, _ in g.ladder_bands] == VIZ_GEL_LADDER_BP


def test_determinism():
    assert simulate_gel(63) == simulate_gel(63)


# ── render_gel ───────────────────────────────────────────────────────────────────

def test_render_wellformed_and_labels():
    svg = render_gel(simulate_gel(63), mirna_id="hsa-miR-16-5p")
    ET.fromstring(svg)
    assert VIZ_SIMULATED_LABEL in svg
    assert "63 bp" in svg
    assert "agarose" in svg


def test_render_out_of_range_label():
    svg = render_gel(simulate_gel(800))
    assert "Outside ladder range" in svg


def test_render_deterministic():
    g = simulate_gel(63)
    assert render_gel(g) == render_gel(g)
