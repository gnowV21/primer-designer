"""svg_builder tests (SPEC §E.4, §E.8)."""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from visualization.svg_builder import Svg, escape_xml  # noqa: E402


def test_escape_xml_all_five_metacharacters():
    assert escape_xml('&<>"\'') == "&amp;&lt;&gt;&quot;&apos;"


def test_escape_xml_ampersand_first():
    # & must be escaped before < > so entities are not double-escaped.
    assert escape_xml("a & b < c") == "a &amp; b &lt; c"


def test_numeric_attributes_rounded_to_two_decimals():
    svg = Svg(100, 50)
    svg.rect(10.123456, 20.0, 30.9999, 5, fill="var(--x, #000)")
    out = svg.render()
    assert 'x="10.12"' in out
    assert 'width="31"' in out       # 30.9999 rounds to 31
    assert 'y="20"' in out           # trailing .0 dropped


def test_output_parses_as_xml():
    svg = Svg(120, 60, title="t", desc="d")
    with svg.group(aria_label="grp") as g:
        g.rect(0, 0, 10, 10, fill="var(--viz-mirna, #2A9D8F)")
        g.text(5, 5, "hello")
        g.line(0, 0, 10, 10, stroke="var(--viz-axis, #64748B)")
        g.text_columns(0, 5, "ACGT", 20, size=13)
    root = ET.fromstring(svg.render())            # raises if malformed
    assert root.tag.endswith("svg")


def test_xss_payload_is_escaped_in_output():
    svg = Svg(100, 50, title='"><script>alert(1)</script>')
    out = svg.render()
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    ET.fromstring(out)                              # still well-formed


def test_text_columns_emits_one_tspan_per_char():
    svg = Svg(100, 50)
    svg.text_columns(0, 10, "ACG", 20)
    out = svg.render()
    assert out.count("<tspan") == 3
