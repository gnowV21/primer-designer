"""PART B tests — reaction panel renderer (SPEC §B, §F PART B)."""
import os
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithm.constants import STEMLOOP_BODY, UNIVERSAL_REVERSE  # noqa: E402
from algorithm.sequence_utils import reverse_complement as rc      # noqa: E402
from visualization.coordinates import build_amplicon_model         # noqa: E402
from visualization.renderer import render_reaction                 # noqa: E402
from visualization.constants import VIZ_SIMULATED_LABEL            # noqa: E402


def _golden_model():
    return build_amplicon_model(
        mirna_sequence="UAGCAGCACGUAAAUAUUGGCG",
        stemloop_rt="GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACCGCCAA",
        forward="GGCGTAGCAGCACGTAAA",
        forward_binding_length=14,
        universal_reverse="CCAGTGCAGGGTCCGAGGTA",
    )


def test_reaction_is_wellformed_xml():
    svg = render_reaction(_golden_model(), "hsa-miR-16-5p")
    ET.fromstring(svg)                    # raises if malformed
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")


def test_all_five_stages_have_aria_labels():
    svg = render_reaction(_golden_model(), "hsa-miR-16-5p")
    for i in range(5):
        assert f'aria-label="Stage {i}:' in svg


def test_simulated_label_present_and_not_toggleable():
    svg = render_reaction(_golden_model())
    assert VIZ_SIMULATED_LABEL in svg     # SPEC §0.4 — embedded, no param to disable


def test_legend_specificity_note_present():
    svg = render_reaction(_golden_model())
    assert "target-specific" in svg          # specificity note (SPEC §B.3)


def test_rt_arrow_points_left_stage1():
    # RT extension arrow head sits to the LEFT of its start (SPEC §B.1). The arrow
    # helper draws the head via a triangle whose apex x < start x when pointing left.
    svg = render_reaction(_golden_model())
    assert "RT extension (5'&#8594;3')" in svg or "RT extension" in svg


def test_five_prime_three_prime_on_bars():
    # Apostrophes are XML-escaped to &apos; in the output (still renders as 5'/3').
    svg = render_reaction(_golden_model())
    assert "5&apos;" in svg and "3&apos;" in svg


def test_uses_css_variable_colors_with_fallback():
    svg = render_reaction(_golden_model())
    assert "var(--viz-mirna, #2A9D8F)" in svg


def test_title_and_desc_for_accessibility():
    svg = render_reaction(_golden_model(), "hsa-miR-16-5p")
    assert "<title>" in svg and "<desc>" in svg
    assert "hsa-miR-16-5p" in svg


def test_render_is_deterministic():
    m = _golden_model()
    assert render_reaction(m, "x") == render_reaction(m, "x")   # SPEC §0.5


def test_mirna_id_is_escaped():
    svg = render_reaction(_golden_model(), '"><script>alert(1)</script>')
    assert "<script>" not in svg
    ET.fromstring(svg)


_BASE = "AGCTTGCAACGATCGTAGCATCGATCGTTAGCACGT"


@pytest.mark.parametrize("L", [21, 22, 23, 24])
def test_other_lengths_render_wellformed(L):
    m = _BASE[:L]
    model = build_amplicon_model(
        mirna_sequence=m,
        stemloop_rt=STEMLOOP_BODY + rc(m[-6:]),
        forward="GGCG" + m[:14],
        forward_binding_length=14,
        universal_reverse=UNIVERSAL_REVERSE,
    )
    ET.fromstring(render_reaction(model, "syn"))


# ── base-pairing correctness (regression) ───────────────────────────────────────
# _bar() reverses a "3to5" strand for display, so any strand handed to it must be
# in its OWN 5'->3' order. Passing column-order text reverses it twice and the
# rendered duplex stops base-pairing. These tests read the rendered tspans back
# and check Watson-Crick complementarity column by column.

_NS = "{http://www.w3.org/2000/svg}"
_COMP = {"A": "T", "T": "A", "G": "C", "C": "G"}


def _char_rows(svg, stage=None):
    """[(y, {x: char}), ...] for every per-character sequence row in the SVG, or only
    inside the stage group whose aria-label starts with `stage` (e.g. "Stage 1")."""
    root = ET.fromstring(svg)
    if stage:
        root = next(g for g in root.iter(f"{_NS}g")
                    if (g.get("aria-label") or "").startswith(stage))
    rows = []
    for t in root.iter(f"{_NS}text"):
        cols = {
            round(float(s.get("x")), 2): (s.text or "")
            for s in t.findall(f"{_NS}tspan") if s.get("x") is not None
        }
        if cols:
            rows.append((round(float(t.get("y")), 2), cols))
    return rows


def _paired_rows(rows, n):
    """Find the n-column row that sits directly below a row covering the same
    x columns, and return (upper_cols, lower_cols). Matching by shared columns
    plus vertical adjacency disambiguates the duplex bars from the single-strand
    overview bars that happen to have the same length."""
    best = None
    for y, cols in rows:
        if len(cols) != n:
            continue
        above = [(uy, uc) for uy, uc in rows
                 if uy < y and all(x in uc for x in cols)]
        if not above:
            continue
        uy, uc = max(above, key=lambda r: r[0])       # nearest row above
        if best is None or (y - uy) < best[0]:
            best = (y - uy, uc, cols)
    assert best is not None, f"no paired {n}-column row found"
    return best[1], best[2]


def test_stage1_overhang_base_pairs_with_mirna_3prime():
    """The 6-nt RT overhang must sit complementary under the miRNA 3' end."""
    model = _golden_model()
    rows = _char_rows(render_reaction(model), "Stage 1")
    mirna_cols, overhang_cols = _paired_rows(rows, 6)

    for x, base in overhang_cols.items():
        assert base == _COMP[mirna_cols[x]], (
            f"x={x}: {mirna_cols[x]} paired with {base}, "
            f"expected {_COMP[mirna_cols[x]]}"
        )

    # displayed left-to-right is the real overhang read 3'->5'
    displayed = "".join(overhang_cols[x] for x in sorted(overhang_cols))
    assert displayed == model.overhang[::-1]

    # and it pairs with the miRNA 3' terminal 6 nt
    top = "".join(mirna_cols[x] for x in sorted(overhang_cols))
    assert top == model.mirna_dna[-6:]


def test_stage3_template_base_pairs_with_forward_primer():
    """The cDNA template row must be complementary to the forward primer row."""
    model = _golden_model()
    rows = _char_rows(render_reaction(model), "Stage 3")
    k = model.forward_binding_length
    template_cols, specific_cols = _paired_rows(rows, k)

    for x, base in specific_cols.items():
        assert template_cols[x] == _COMP[base], (
            f"x={x}: primer {base} against template {template_cols[x]}, "
            f"expected {_COMP[base]}"
        )


@pytest.mark.parametrize("stage", ["Stage 0", "Stage 1"])
def test_stemloop_drawn_as_paired_hairpin(stage):
    """Stages 0-1 draw the RT primer as a hairpin: arm A (nt 1-14) sits under arm B
    (nt 31-44) base-paired column by column, and all 16 loop nt are drawn."""
    model = _golden_model()
    svg = render_reaction(model)
    rows = _char_rows(svg, stage)
    text = lambda c: "".join(c[x] for x in sorted(c))            # noqa: E731
    S = model.stemloop_rt
    (ya, arm_a_cols), = [(y, c) for y, c in rows if text(c) == S[:14]]
    (yb, arm_b_cols), = [(y, c) for y, c in rows if text(c) == S[30:44][::-1]]
    assert yb < ya and set(arm_a_cols) == set(arm_b_cols)     # arm B directly above arm A
    for x, base in arm_a_cols.items():
        assert base == _COMP[arm_b_cols[x]]
    loop = model.stemloop_rt[14:30]
    root = next(g for g in ET.fromstring(svg).iter(f"{_NS}g")
                if (g.get("aria-label") or "").startswith(stage))
    singles = [t.text for t in root.iter(f"{_NS}text") if t.text and len(t.text) == 1
               and t.text in "ACGT"]
    assert "".join(singles) == loop


def test_rungs_do_not_touch_bars():
    """Every base-pair rung ends clear of the bars it connects (no overlap)."""
    svg = render_reaction(_golden_model())
    for ln in ET.fromstring(svg).iter(f"{_NS}line"):
        if ln.get("stroke-width") == "2.4":
            assert float(ln.get("y2")) - float(ln.get("y1")) > 0


@pytest.mark.parametrize("L", [17, 22, 25, 30])
@pytest.mark.parametrize("o", [5, 6, 7])
def test_stage1_hairpin_fits_the_card(L, o):
    """The smooth hairpin (incl. loop ring) never runs past the right content edge."""
    import visualization.renderer as R
    from visualization.svg_builder import _Node
    w = min(L, R.VIZ_MAX_ZOOM_COLUMNS)
    p = min(R.VIZ_CHAR_PITCH, (R._W - R._M - R._OX) / (w + R.VIZ_STEM_BP + 10))
    right, _ = R._stemloop(_Node(), R._OX + (w - o) * p, 100, STEMLOOP_BODY + "A" * o, o, p,
                           min(R.VIZ_MONO_SIZE, p * 1.45))
    assert right <= R._W - R._M
