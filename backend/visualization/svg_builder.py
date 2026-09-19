# ================================================================
# visualization/svg_builder.py — pure-Python SVG serializer (SPEC §E.3, §E.4)
#
# No dependencies. Deterministic: numeric attributes are rounded to 2 decimals so
# output is byte-identical across platforms (SPEC §0.5). Every text string passes
# through escape_xml() — the SVG is injected via dangerouslySetInnerHTML (§E.4).
# ================================================================


def escape_xml(text: str) -> str:
    """Escape the 5 XML metacharacters. Applied to EVERY string put into the SVG."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _num(value) -> str:
    """Format a coordinate deterministically: ints stay ints, floats round to 2 dp."""
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    return f"{round(float(value), 2):g}"


def _attrs(pairs: dict) -> str:
    """Serialize attributes in insertion order; None values dropped."""
    out = []
    for key, val in pairs.items():
        if val is None:
            continue
        name = key.rstrip("_").replace("_", "-")
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            out.append(f'{name}="{_num(val)}"')
        else:
            out.append(f'{name}="{escape_xml(val)}"')
    return " ".join(out)


class _Node:
    """Base drawable — accumulates child element strings."""

    def __init__(self):
        self._children: list[str] = []

    # ── primitives ──────────────────────────────────────────────────────────
    def rect(self, x, y, width, height, *, fill=None, stroke=None,
             stroke_width=None, rx=None, ry=None, opacity=None,
             dash=None, class_=None, filter=None):
        self._children.append(
            f"<rect {_attrs({'x': x, 'y': y, 'width': width, 'height': height, 'rx': rx, 'ry': ry, 'fill': fill, 'stroke': stroke, 'stroke-width': stroke_width, 'stroke-dasharray': dash, 'opacity': opacity, 'filter': filter, 'class': class_})} />"
        )

    def line(self, x1, y1, x2, y2, *, stroke=None, stroke_width=None,
             dash=None, class_=None, linecap=None):
        self._children.append(
            f"<line {_attrs({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'stroke': stroke, 'stroke-width': stroke_width, 'stroke-dasharray': dash, 'stroke-linecap': linecap, 'class': class_})} />"
        )

    def path(self, d, *, stroke=None, fill=None, stroke_width=None,
             dash=None, class_=None, opacity=None, linecap=None, linejoin=None,
             filter=None):
        # `d` is built from numeric coords by the caller; treated as trusted geometry.
        self._children.append(
            f'<path d="{d}" {_attrs({"stroke": stroke, "fill": fill, "stroke-width": stroke_width, "stroke-dasharray": dash, "class": class_, "opacity": opacity, "stroke-linecap": linecap, "stroke-linejoin": linejoin, "filter": filter})} />'
        )

    def text(self, x, y, content, *, size=None, fill=None, anchor=None,
             weight=None, family=None, class_=None):
        self._children.append(
            f"<text {_attrs({'x': x, 'y': y, 'font-size': size, 'fill': fill, 'text-anchor': anchor, 'font-weight': weight, 'font-family': family, 'class': class_})}>{escape_xml(content)}</text>"
        )

    def text_columns(self, x, y, chars, pitch, *, size=None, fill=None,
                     family=None, weight=None, anchor="middle"):
        """Monospace-aligned text: one <tspan x=...> per character (SPEC §B.2 —
        never rely on letter-spacing, font metrics differ across OSes)."""
        tspans = "".join(
            f'<tspan {_attrs({"x": x + i * pitch})}>{escape_xml(ch)}</tspan>'
            for i, ch in enumerate(chars)
        )
        self._children.append(
            f"<text {_attrs({'y': y, 'font-size': size, 'fill': fill, 'text-anchor': anchor, 'font-weight': weight, 'font-family': family})}>{tspans}</text>"
        )

    def raw(self, markup: str):
        """Append pre-built trusted markup (already escaped by the caller)."""
        self._children.append(markup)

    def group(self, *, aria_label=None, class_=None, transform=None):
        return _GroupContext(self, aria_label=aria_label, class_=class_, transform=transform)

    def _inner(self) -> str:
        return "".join(self._children)


class _Group(_Node):
    def __init__(self, aria_label=None, class_=None, transform=None):
        super().__init__()
        self._aria = aria_label
        self._class = class_
        self._transform = transform

    def render(self) -> str:
        role = "img" if self._aria else None
        return (
            f"<g {_attrs({'role': role, 'aria-label': self._aria, 'class': self._class, 'transform': self._transform})}>"
            f"{self._inner()}</g>"
        )


class _GroupContext:
    def __init__(self, parent, **kwargs):
        self._parent = parent
        self._group = _Group(**kwargs)

    def __enter__(self):
        return self._group

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._parent.raw(self._group.render())
        return False


class Svg(_Node):
    """Root SVG. Colours use CSS custom properties with hex fallback (SPEC §E.5).
    Emits role/img + <title>/<desc> for accessibility (SPEC §E.6)."""

    def __init__(self, width, height, view_box=None, *, title=None, desc=None):
        super().__init__()
        self.width = width
        self.height = height
        self.view_box = view_box or f"0 0 {_num(width)} {_num(height)}"
        self.title = title
        self.desc = desc

    def render(self) -> str:
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="{escape_xml(self.view_box)}" '
            f'width="{_num(self.width)}" height="{_num(self.height)}" '
            f'role="img" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">'
        )
        meta = ""
        if self.title is not None:
            meta += f"<title>{escape_xml(self.title)}</title>"
        if self.desc is not None:
            meta += f"<desc>{escape_xml(self.desc)}</desc>"
        return f"{head}{meta}{self._inner()}</svg>"
