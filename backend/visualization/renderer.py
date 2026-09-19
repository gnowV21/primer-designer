# ================================================================
# visualization/renderer.py — SVG renderers for the 3 panels
# PART B: render_reaction. render_melting / render_gel added in PART C / PART D.
#
# Colours go through constants.color() → var(--token, #fallback) (SPEC §E.5);
# region fills use vertical gradients (g-<token>) built from the token + its -hi
# companion, plus a soft drop shadow for depth. Every panel embeds
# VIZ_SIMULATED_LABEL and a <title>/<desc> (SPEC §0.4, §E.6). Deterministic
# (no randomness, no timestamps — SPEC §0.5).
#
# Layout: each stage is measured into a scratch node then placed on a light card
# so stages read as distinct clusters; notes are word-wrapped; end labels sit in
# dedicated side gutters so 5'/3' never clip or overlap the sequence.
# ================================================================

import math

from .svg_builder import Svg, _Node, escape_xml
from .constants import (
    VIZ_CANVAS_WIDTH, VIZ_MARGIN, VIZ_CHAR_PITCH, VIZ_BAR_HEIGHT,
    VIZ_STAGE_GAP, VIZ_MAX_ZOOM_COLUMNS, VIZ_MONO_SIZE, VIZ_LABEL_SIZE,
    VIZ_TITLE_SIZE, VIZ_NOTE_SIZE, VIZ_SIMULATED_LABEL, color, VIZ_COLOR_FALLBACK,
    VIZ_MELT_T_START, VIZ_MELT_T_END,
    VIZ_GEL_BAND_HEIGHT, VIZ_GEL_AGAROSE_PCT,
    REGION_COLOR_TOKEN, REGION_TAIL, REGION_MIRNA, REGION_STEMLOOP, REGION_UNIVERSAL,
    VIZ_STEM_BP,
)

_W = 1000                      # widened canvas (SPEC §B.1 allows dynamic width)
_M = VIZ_MARGIN
_GUT = 34                      # side gutter reserved for 5'/3' end labels
_CONTENT_W = _W - 2 * _M
_OX = _M + _GUT               # overview drawing origin (leaves left gutter)
_OW = _W - 2 * _M - 2 * _GUT  # overview drawing width (leaves right gutter)
_CARD_PAD = 16
_PAIR_GAP = 30                # gap between paired strands (base-pair rungs)
_RUNG_GAP = 4                 # rungs stop this far short of each bar / frame
_TXT_PAD = 8                  # inner padding so end nucleotides never touch the bar edge
_BAR_RX = 8

_FG     = color("viz-fg")
_MUTED  = color("viz-muted")
_AXIS   = color("viz-axis")
_BG     = color("viz-bg")
_SURF   = color("viz-surface")
_BORDER = color("viz-border")
_SHADOW = "url(#viz-shadow)"

_REGION_TOKENS = ["viz-tail", "viz-mirna", "viz-stemloop", "viz-universal"]
_COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}


def _complement(seq: str) -> str:
    return "".join(_COMPLEMENT.get(b, "N") for b in seq)


def _revcomp(seq: str) -> str:
    return _complement(seq)[::-1]


def _grad(token: str) -> str:
    return f"url(#g-{token})"


def _defs() -> str:
    parts = ["<defs>"]
    for tok in _REGION_TOKENS:
        base = VIZ_COLOR_FALLBACK[tok]
        hi = VIZ_COLOR_FALLBACK[f"{tok}-hi"]
        parts.append(
            f'<linearGradient id="g-{tok}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="var(--{tok}-hi, {hi})"/>'
            f'<stop offset="1" stop-color="var(--{tok}, {base})"/>'
            f"</linearGradient>"
        )
    # neutral surface gradient for template/overview bars
    parts.append(
        '<linearGradient id="g-surface" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="var(--viz-bg, #FFFFFF)"/>'
        '<stop offset="1" stop-color="var(--viz-surface, #F7F9FC)"/></linearGradient>'
    )
    parts.append(
        '<filter id="viz-shadow" x="-6%" y="-40%" width="112%" height="180%">'
        '<feDropShadow dx="0" dy="1.5" stdDeviation="1.6" '
        'flood-color="#0F172A" flood-opacity="0.16"/></filter>'
    )
    parts.append("</defs>")
    return "".join(parts)


# ── text helpers ────────────────────────────────────────────────────────────────

def _wrap_note(node, x, y, text, max_px, *, size=VIZ_NOTE_SIZE, fill=None):
    fill = fill or _MUTED
    char_w = size * 0.6
    max_chars = max(8, int(max_px / char_w))
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = w if not cur else cur + " " + w
        if len(trial) <= max_chars:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    line_h = size * 1.4
    for i, line in enumerate(lines):
        node.text(x, y + size + i * line_h, line, size=size, fill=fill)
    return y + size + (len(lines) - 1) * line_h + 6


def _title(node, y, text):
    node.text(_M, y + VIZ_TITLE_SIZE, text, size=VIZ_TITLE_SIZE, fill=_FG, weight="700")
    return y + VIZ_TITLE_SIZE + 14


# ── bar helpers ─────────────────────────────────────────────────────────────────

def _end_labels(node, x, y, width, direction):
    left, right = ("5'", "3'") if direction == "5to3" else ("3'", "5'")
    cy = y + VIZ_BAR_HEIGHT / 2 + VIZ_LABEL_SIZE * 0.35
    node.text(x - 10, cy, left, size=VIZ_LABEL_SIZE, fill=_MUTED, anchor="end", weight="600")
    node.text(x + width + 10, cy, right, size=VIZ_LABEL_SIZE, fill=_MUTED, anchor="start", weight="600")


def _bar(node, x, y, seq, pitch, direction, *, fill, mono_size=None, dash=False,
         text_fill=None, show_ends=True, shadow=True, pad_l=_TXT_PAD, pad_r=_TXT_PAD):
    """Sequence bar. Columns start at x (pairing geometry unchanged); the rectangle
    extends pad_l/pad_r beyond them so end letters never touch the edge. Contiguous
    segments pass pad 0 on the shared side."""
    width = len(seq) * pitch
    mono_size = mono_size or min(VIZ_MONO_SIZE, pitch * 1.45)
    node.rect(x - pad_l, y, width + pad_l + pad_r, VIZ_BAR_HEIGHT, rx=_BAR_RX, fill=fill,
              stroke=_BORDER, stroke_width=1, dash="5 3" if dash else None,
              filter=_SHADOW if shadow else None)
    _bar_text(node, x, y, seq, pitch, direction, mono_size, text_fill)
    if show_ends:
        _end_labels(node, x - pad_l, y, width + pad_l + pad_r, direction)
    return width


def _bar_text(node, x, y, seq, pitch, direction, mono_size, text_fill=None):
    chars = seq if direction == "5to3" else seq[::-1]
    node.text_columns(x + pitch / 2, y + VIZ_BAR_HEIGHT / 2 + mono_size * 0.35,
                      chars, pitch, size=mono_size, fill=text_fill or _FG, weight="600")


def _rungs(node, x_start, count, pitch, y_top, y_bot):
    """Base-pair rungs: short rounded verticals in the gap between two aligned
    strands, stopping _RUNG_GAP short of each (never drawn over a bar or frame)."""
    for t in range(count):
        cx = x_start + t * pitch + pitch / 2
        node.line(cx, y_top + _RUNG_GAP, cx, y_bot - _RUNG_GAP, stroke=_AXIS,
                  stroke_width=2.4, linecap="round")


def _stemloop(node, x, y, S, o, pitch, mono_size):
    """Stem-loop RT primer drawn as one smooth hairpin.

    The whole primer is a single stroked path (same thickness as a sequence bar):
    row 1 (3' overhang + stem arm B, read 3'->5' left to right) -> Bezier neck ->
    circular loop -> Bezier neck -> row 2 (stem arm A, the 5' end). Tangents match
    at every joint, so there are no corners. Row 1's overhang sits exactly where it
    pairs with the miRNA in stage 1. Returns (right_x, bottom_y).
    """
    stem = VIZ_STEM_BP
    body = len(S) - o
    arm_b, loop, arm_a = S[body - stem:body], S[stem:body - stem], S[:stem]
    n1 = o + stem
    y2 = y + VIZ_BAR_HEIGHT + _PAIR_GAP
    xa = x + o * pitch                          # arm A's 5' nt sits under the last body nt
    half = VIZ_BAR_HEIGHT / 2
    y1c, y2c = y + half, y2 + half
    h = (y2c - y1c) / 2
    cy = y1c + h

    # loop radius: enough arc for the loop letters, and a visible hole in the ring
    need = (len(loop) + 1) * max(pitch, mono_size * 1.2)
    r = max(h + 1, half + 16)
    while (2 * math.pi - 2 * math.asin(h / r)) * r < need:
        r += 1
    alpha = math.asin(h / r)                    # the ring meets both arm centre-lines
    neck = 26
    xe = x + n1 * pitch + _TXT_PAD              # straight arms end past the last letter
    ex = xe + neck                              # ring entry / exit x
    cx = ex + r * math.cos(alpha)
    k = neck * 0.55
    sa, ca = math.sin(alpha), math.cos(alpha)
    d = (
        f"M {x - _TXT_PAD + half:.2f} {y1c:.2f} L {xe:.2f} {y1c:.2f} "
        # neck into the ring, tangent (sin a, -cos a) at entry (clockwise travel)
        f"C {xe + k:.2f} {y1c:.2f} {ex - k * sa:.2f} {y1c + k * ca:.2f} {ex:.2f} {y1c:.2f} "
        f"A {r:.2f} {r:.2f} 0 1 1 {ex:.2f} {y2c:.2f} "
        # neck out of the ring, tangent (-sin a, -cos a) at exit
        f"C {ex - k * sa:.2f} {y2c - k * ca:.2f} {xe + k:.2f} {y2c:.2f} {xe:.2f} {y2c:.2f} "
        f"L {xa - _TXT_PAD + half:.2f} {y2c:.2f}"
    )
    node.path(d, fill="none", stroke=color("viz-stemloop"), stroke_width=VIZ_BAR_HEIGHT,
              linecap="round", linejoin="round", filter=_SHADOW)

    _bar_text(node, x, y, S[body:], pitch, "3to5", mono_size, _BG)
    _bar_text(node, xa, y, arm_b, pitch, "3to5", mono_size, _BG)
    _bar_text(node, xa, y2, arm_a, pitch, "5to3", mono_size, _BG)
    _rungs(node, xa, stem, pitch, y + VIZ_BAR_HEIGHT, y2)
    lab = half + VIZ_LABEL_SIZE * 0.35
    node.text(x - _TXT_PAD - 10, y + lab, "3'", size=VIZ_LABEL_SIZE, fill=_MUTED,
              anchor="end", weight="600")
    node.text(xa - _TXT_PAD - 10, y2 + lab, "5'", size=VIZ_LABEL_SIZE, fill=_MUTED,
              anchor="end", weight="600")

    # loop letters on the ring centre-line, in sequence order from arm A (bottom)
    # round the right side to arm B (top)
    t_start, span = math.pi - alpha, -(2 * math.pi - 2 * alpha)   # counter-clockwise
    for i, ch in enumerate(loop):
        t = t_start + (i + 1) * span / (len(loop) + 1)
        node.text(round(cx + r * math.cos(t), 2),
                  round(cy + r * math.sin(t) + mono_size * 0.35, 2),
                  ch, size=mono_size, fill=_BG, anchor="middle", weight="600")
    return cx + r + half, y2 + VIZ_BAR_HEIGHT


def _arrow(node, x1, y, x2, *, label=None):
    node.line(x1, y, x2, y, stroke=_MUTED, stroke_width=2, linecap="round")
    head = 7 if x2 > x1 else -7
    node.path(f"M {x2} {y} L {x2 - head} {y - 4.5} L {x2 - head} {y + 4.5} Z", fill=_MUTED)
    if label:
        node.text((x1 + x2) / 2, y - 9, label, size=VIZ_LABEL_SIZE, fill=_MUTED, anchor="middle")


# ── per-stage draw functions (draw into scratch node, return end y) ───────────────

def _stage0(node, y, model, oscale):
    y = _title(node, y, "Stage 0 · Components")
    rows = [
        (model.mirna_dna, "miRNA"),
        (model.stemloop_rt, "Stem-loop RT (S)"),
        (model.forward, "Forward (F)"),
        (model.universal_reverse, "Universal reverse (U)"),
    ]
    # label column sized to the longest label, plus room for the 5' end label
    label_w = max(len(n) for _, n in rows) * (VIZ_LABEL_SIZE + 1) * 0.62 + 28
    bar_x = _M + label_w + _TXT_PAD
    avail = _W - _M - _GUT - _TXT_PAD - bar_x
    s = avail / max(len(r[0]) for r in rows)
    mono = min(VIZ_MONO_SIZE, s * 1.45)
    for seq, name in rows:
        node.text(_M, y + VIZ_BAR_HEIGHT / 2 + 4, name, size=VIZ_LABEL_SIZE + 1, fill=_FG, weight="600")
        if seq is model.stemloop_rt:
            _, y = _stemloop(node, bar_x, y, seq, len(model.overhang), s, mono)
            y += 22
            continue
        _bar(node, bar_x, y, seq, s, "5to3", fill="url(#g-surface)")
        y += VIZ_BAR_HEIGHT + 22
    return _wrap_note(node, _M, y, model.stages[0].annotation_en, _CONTENT_W)


def _stage1(node, y, model, oscale):
    y = _title(node, y, "Stage 1 · RT annealing")
    m = model.mirna_dna
    L = len(m)
    w = min(L, VIZ_MAX_ZOOM_COLUMNS)
    window = m[L - w:]
    truncated = w < L
    o = len(model.overhang)   # 5–7 nt, read from the RT primer
    x0 = _OX
    # Shrink the pitch only when the miRNA + hairpin would not fit the card.
    pitch = min(VIZ_CHAR_PITCH, (_W - _M - x0) / (w + VIZ_STEM_BP + 10))
    mono = min(VIZ_MONO_SIZE, pitch * 1.45)
    top_y = y
    _bar(node, x0, top_y, window, pitch, "5to3", fill="url(#g-surface)", mono_size=mono)
    if truncated:
        node.text(x0 - _TXT_PAD - 12, top_y + VIZ_BAR_HEIGHT / 2 + 4, "…", size=VIZ_MONO_SIZE,
                  fill=_MUTED, anchor="end")
    hl_x = x0 + (w - o) * pitch
    frame_pad = 4
    node.rect(hl_x - 3, top_y - frame_pad, o * pitch + 6, VIZ_BAR_HEIGHT + 2 * frame_pad,
              rx=_BAR_RX + 2, fill="none", stroke=color("viz-mirna"), stroke_width=2.5)
    bot_y = top_y + VIZ_BAR_HEIGHT + _PAIR_GAP
    # Hairpin RT primer; its overhang (row 1, drawn 3'->5') sits under the miRNA 3'
    # end. model.overhang = revcomp(miRNA 3' o nt) — see viz_strand_orientation_rule.
    _, bottom = _stemloop(node, hl_x, bot_y, model.stemloop_rt, o, pitch, mono)
    _rungs(node, hl_x, o, pitch, top_y + VIZ_BAR_HEIGHT + frame_pad + 1, bot_y)
    # RT extends the primer 3' end (left end of the overhang) leftward along the miRNA.
    _arrow(node, hl_x - _TXT_PAD, bottom + 18, x0 - 6, label="RT extension (5'→3')")
    y = bottom + 30
    return _wrap_note(node, _M, y, model.stages[1].annotation_en, _CONTENT_W)


def _stage2(node, y, model, oscale):
    y = _title(node, y, "Stage 2 · RT product (cDNA)")
    S = model.stemloop_rt
    ext = model.cdna[len(S):]
    _bar(node, _OX, y, S, oscale, "5to3", fill=_grad("viz-stemloop"), text_fill=_BG,
         show_ends=False, pad_r=0)
    _bar(node, _OX + len(S) * oscale, y, ext, oscale, "5to3", fill="url(#g-surface)",
         show_ends=False, pad_l=0)
    _end_labels(node, _OX - _TXT_PAD, y, len(model.cdna) * oscale + 2 * _TXT_PAD, "5to3")
    node.text(_OX + len(S) * oscale, y + VIZ_BAR_HEIGHT + 16, "↑ new RT extension",
              size=VIZ_LABEL_SIZE, fill=_MUTED, anchor="middle")
    y += VIZ_BAR_HEIGHT + 26
    return _wrap_note(node, _M, y, model.stages[2].annotation_en, _CONTENT_W)


def _stage3(node, y, model, oscale):
    y = _title(node, y, "Stage 3 · PCR cycle 1 (forward primer)")
    F = model.forward
    tail = model.tail
    k = model.forward_binding_length
    x0 = _OX
    # Same rule as stage 1: a "3to5" strand must be given in its own 5'->3' order.
    # The template for primer F is revcomp(F).
    template = _revcomp(F)
    top_y = y
    _bar(node, x0, top_y, template, VIZ_CHAR_PITCH, "3to5", fill="url(#g-surface)",
         mono_size=VIZ_MONO_SIZE)
    # placed after the bar's right end label ("5'"), not on top of it
    node.text(x0 + len(F) * VIZ_CHAR_PITCH + _TXT_PAD + 34, top_y + VIZ_BAR_HEIGHT / 2 + 4,
              "cDNA template", size=VIZ_LABEL_SIZE, fill=_MUTED, anchor="start")
    bot_y = top_y + VIZ_BAR_HEIGHT + _PAIR_GAP
    if tail:
        _bar(node, x0, bot_y, tail, VIZ_CHAR_PITCH, "5to3", fill=_grad("viz-tail"),
             mono_size=VIZ_MONO_SIZE, dash=True, text_fill=_BG, show_ends=False, pad_r=0)
    _bar(node, x0 + len(tail) * VIZ_CHAR_PITCH, bot_y, F[len(tail):], VIZ_CHAR_PITCH,
         "5to3", fill=_grad("viz-mirna"), mono_size=VIZ_MONO_SIZE, text_fill=_BG, show_ends=False,
         pad_l=0 if tail else _TXT_PAD)
    _rungs(node, x0 + len(tail) * VIZ_CHAR_PITCH, k, VIZ_CHAR_PITCH,
           top_y + VIZ_BAR_HEIGHT, bot_y)
    # captions BELOW the primer bar (no overlap)
    cap_y = bot_y + VIZ_BAR_HEIGHT + 15
    if tail:
        node.text(x0 + len(tail) * VIZ_CHAR_PITCH / 2, cap_y, "5' GC tail — no template",
                  size=VIZ_LABEL_SIZE, fill=_MUTED, anchor="middle")
    node.text(x0 + (len(tail) + k / 2) * VIZ_CHAR_PITCH, cap_y, "binds miRNA 5' end",
              size=VIZ_LABEL_SIZE, fill=_MUTED, anchor="middle")
    _arrow(node, x0 + len(F) * VIZ_CHAR_PITCH, cap_y + 18,
           x0 + (len(F) + 5) * VIZ_CHAR_PITCH, label="extension (5'→3')")
    y = cap_y + 34
    node.text(_M, y, "Resulting cycle-1 strand", size=VIZ_LABEL_SIZE + 1, fill=_FG, weight="600")
    y += 16
    _bar(node, _OX, y, model.sense_strand, oscale, "5to3", fill="url(#g-surface)")
    y += VIZ_BAR_HEIGHT + 16
    return _wrap_note(node, _M, y, model.stages[3].annotation_en, _CONTENT_W)


def _stage4(node, y, model, oscale):
    y = _title(node, y, "Stage 4 · PCR cycle 2+ (universal reverse) → amplicon")
    sense = model.sense_strand
    j = model.universal_offset
    U = model.universal_reverse
    _bar(node, _OX, y, sense, oscale, "5to3", fill="url(#g-surface)")
    ux = _OX + j * oscale
    node.rect(ux, y - 4, len(U) * oscale, VIZ_BAR_HEIGHT + 8, rx=_BAR_RX,
              fill="none", stroke=color("viz-universal"), stroke_width=2.5)
    cut = _OX + (j + len(U)) * oscale
    node.line(cut, y - 14, cut, y + VIZ_BAR_HEIGHT + 8, stroke=color("viz-universal"),
              stroke_width=1.5, dash="5 3")
    node.text(min(cut, _W - _M), y - 18, "product stop (primer 5' end)",
              size=VIZ_LABEL_SIZE, fill=color("viz-universal"), anchor="end", weight="600")
    y += VIZ_BAR_HEIGHT + 34
    node.text(_M, y, f"Amplicon · {len(model.amplicon)} bp · GC {model.gc_percent}%",
              size=VIZ_LABEL_SIZE + 2, fill=_FG, weight="700")
    y += 14
    for reg in model.regions:
        rx = _OX + reg.start * oscale
        rw = reg.length * oscale
        node.rect(rx, y, rw, VIZ_BAR_HEIGHT, rx=6, fill=_grad(reg.color_token),
                  stroke=_BG, stroke_width=1.5, filter=_SHADOW)
        node.text(rx + rw / 2, y + VIZ_BAR_HEIGHT + VIZ_LABEL_SIZE + 2,
                  f"{reg.length}", size=VIZ_LABEL_SIZE, fill=_MUTED, anchor="middle")
    _end_labels(node, _OX, y, len(model.amplicon) * oscale, "5to3")
    y += VIZ_BAR_HEIGHT + VIZ_LABEL_SIZE + 12
    if model.size_warning:
        node.text(_M, y + 10, "⚠ Amplicon size outside the qPCR range",
                  size=VIZ_LABEL_SIZE + 1, fill=color("viz-warn"), weight="600")
        y += 20
    return _wrap_note(node, _M, y, model.stages[4].annotation_en, _CONTENT_W)


_STAGE_FNS = [
    ("Stage 0: Components", _stage0),
    ("Stage 1: RT annealing", _stage1),
    ("Stage 2: RT product (cDNA)", _stage2),
    ("Stage 3: PCR cycle 1 (forward primer)", _stage3),
    ("Stage 4: PCR cycle 2+ (universal reverse)", _stage4),
]


# ── PART B: reaction panel ──────────────────────────────────────────────────────

def render_reaction(model, mirna_id: str = "") -> str:
    """Panel 1 — the 5-stage stem-loop RT-qPCR reaction (SPEC §B)."""
    longest = max(len(model.sense_strand), len(model.cdna), len(model.amplicon),
                  len(model.stemloop_rt), len(model.mirna_dna))
    oscale = _OW / longest

    svg = Svg(_W, 0, title=f"Reaction schematic — {mirna_id or 'miRNA'}",
              desc=(
                  "Schematic of the five-stage stem-loop RT-qPCR reaction: components, "
                  "RT annealing, cDNA synthesis, first PCR cycle with the forward primer, "
                  "and later cycles with the universal reverse primer forming the amplicon. "
                  "Sequence geometry is derived from the design output, not from experimental data."
              ))
    svg.raw(_defs())
    svg.rect(0, 0, _W, _W, fill=_BG)  # painted background (height fixed later)

    y = _M
    svg.text(_M, y + 20, "Reaction — stem-loop RT-qPCR", size=20, fill=_FG, weight="700")
    y += 26
    svg.text(_M, y + 12, VIZ_SIMULATED_LABEL, size=VIZ_LABEL_SIZE, fill=_MUTED)
    y += 30

    for aria, fn in _STAGE_FNS:
        scratch = _Node()
        end_y = fn(scratch, y, model, oscale)
        svg.rect(_M - _CARD_PAD, y - _CARD_PAD, _CONTENT_W + 2 * _CARD_PAD,
                 (end_y - y) + 2 * _CARD_PAD, rx=14, fill=_SURF, stroke=_BORDER,
                 stroke_width=1, opacity=0.55)
        svg.raw(f'<g role="img" aria-label="{escape_xml(aria)}">{scratch._inner()}</g>')
        y = end_y + _CARD_PAD + VIZ_STAGE_GAP

    # Legend (SPEC §B.3) — 2×2 grid so nothing overflows the content width
    with svg.group(aria_label="Legend") as g:
        g.line(_M, y, _W - _M, y, stroke=_BORDER, stroke_width=1)
        y += 22
        legend = [
            (REGION_TAIL, "F 5' tail", model.regions[0].length),
            (REGION_MIRNA, "miRNA — target-specific", model.regions[1].length),
            (REGION_STEMLOOP, "stem-loop body", model.regions[2].length),
            (REGION_UNIVERSAL, "universal site", model.regions[3].length),
        ]
        col_w = _CONTENT_W / 2
        for i, (name, label, n) in enumerate(legend):
            cx = _M + (i % 2) * col_w
            cy = y + (i // 2) * 28
            g.rect(cx, cy - 12, 16, 16, rx=4, fill=_grad(REGION_COLOR_TOKEN[name]), filter=_SHADOW)
            g.text(cx + 24, cy + 1, f"{label} ({n} nt)", size=VIZ_LABEL_SIZE + 1, fill=_FG, weight="600")
        y += 28 * 2 + 6
        y = _wrap_note(
            g, _M, y,
            "Only the miRNA region is target-specific; the tail, stem-loop body and universal "
            "site are shared across all assays.",
            _CONTENT_W, size=VIZ_LABEL_SIZE + 1,
        )

    total_h = round(y + _M, 2)
    svg.height = total_h
    svg.view_box = f"0 0 {_W} {total_h}"
    return svg.render()


# ── PART C: melting-curve panel ─────────────────────────────────────────────────

_MELT_W = 760
_MELT_H = 580
# Curves are drawn into this fraction of the plot height, leaving headroom at the
# top so the derivative peak (and the fluorescence plateau) never touch the frame.
_MELT_HEADROOM = 0.86


def _fmt(v):
    return f"{round(v, 2):g}"


def _polyline(points):
    if not points:
        return ""
    d = f"M {_fmt(points[0][0])} {_fmt(points[0][1])}"
    d += "".join(f" L {_fmt(x)} {_fmt(y)}" for x, y in points[1:])
    return d


def render_melting(melt, *, mirna_id="", amplicon_bp=None, gc_percent=None,
                   dimer_tm_warning=None) -> str:
    """Panel 2 — simulated melting curve + −dF/dT derivative (SPEC §C)."""
    x0, x1 = 66, _MELT_W - 70
    y0, y1 = 96, _MELT_H - 70          # plot area (top, bottom)
    t_lo, t_hi = VIZ_MELT_T_START, VIZ_MELT_T_END

    def tx(t):
        return x0 + (t - t_lo) / (t_hi - t_lo) * (x1 - x0)

    plot_h = (y1 - y0) * _MELT_HEADROOM   # leaves headroom above both curves

    def yL(f):                           # left axis: fluorescence [0,1]
        return y1 - f * plot_h

    peak = melt.peak_height or 1.0

    def yR(d):                           # right axis: −dF/dT scaled to its max
        return y1 - (d / peak) * plot_h

    svg = Svg(_MELT_W, _MELT_H,
              title=f"Simulated melting curve — {mirna_id or 'amplicon'}",
              desc=(
                  "Simulated SYBR Green melting curve and its negative first derivative, "
                  f"with a single product peak at {melt.peak_temperature} degrees Celsius. "
                  "Computed from the predicted Tm, not from experimental data."
              ))
    svg.raw(_defs())
    svg.rect(0, 0, _MELT_W, _MELT_H, fill=_BG)
    svg.rect(x0, y0, x1 - x0, y1 - y0, rx=8, fill="url(#g-surface)", stroke=_BORDER, stroke_width=1)

    # header
    svg.text(_M, 34, "Melting curve — simulated", size=19, fill=_FG, weight="700")
    svg.text(_M, 52, VIZ_SIMULATED_LABEL, size=VIZ_LABEL_SIZE, fill=_MUTED)
    sub = []
    if amplicon_bp is not None:
        sub.append(f"Amplicon: {amplicon_bp} bp")
    if gc_percent is not None:
        sub.append(f"GC {gc_percent}%")
    if sub:
        svg.text(_M, 70, " · ".join(sub), size=VIZ_LABEL_SIZE + 1, fill=_FG, weight="600")

    # grid + X ticks every 5 °C
    t = t_lo
    while t <= t_hi + 1e-6:
        gx = tx(t)
        svg.line(gx, y0, gx, y1, stroke=_BORDER, stroke_width=1)
        svg.text(gx, y1 + 18, f"{int(round(t))}", size=VIZ_LABEL_SIZE, fill=_MUTED, anchor="middle")
        t += 5
    svg.text((x0 + x1) / 2, y1 + 40, "Temperature (°C)", size=VIZ_LABEL_SIZE + 1,
             fill=_FG, anchor="middle", weight="600")

    # Y-left ticks (fluorescence)
    for f in (0, 0.25, 0.5, 0.75, 1.0):
        gy = yL(f)
        svg.line(x0 - 4, gy, x0, gy, stroke=_AXIS, stroke_width=1)
        svg.text(x0 - 8, gy + 4, f"{f:g}", size=VIZ_LABEL_SIZE, fill=_MUTED, anchor="end")
    # rotated axis labels (left: fluorescence, right: −dF/dT)
    svg.raw(f'<text transform="rotate(-90 20 {_fmt((y0 + y1) / 2)})" x="20" '
            f'y="{_fmt((y0 + y1) / 2)}" font-size="{VIZ_LABEL_SIZE + 1}" '
            f'fill="{color("viz-curve")}" text-anchor="middle" font-weight="600">'
            f'Normalized fluorescence</text>')
    svg.raw(f'<text transform="rotate(90 {_fmt(_MELT_W - 22)} {_fmt((y0 + y1) / 2)})" '
            f'x="{_fmt(_MELT_W - 22)}" y="{_fmt((y0 + y1) / 2)}" '
            f'font-size="{VIZ_LABEL_SIZE + 1}" fill="{color("viz-derivative")}" '
            f'text-anchor="middle" font-weight="600">−dF/dT</text>')

    # curves
    f_pts = [(tx(t), yL(f)) for t, f in zip(melt.temperatures, melt.f_norm)]
    d_pts = [(tx(t), yR(d)) for t, d in zip(melt.temperatures, melt.neg_dfdt)]
    svg.path(_polyline(f_pts), stroke=color("viz-curve"), fill="none", stroke_width=1.5)
    svg.path(_polyline(d_pts), stroke=color("viz-derivative"), fill="none", stroke_width=2.6)

    # Tm marker
    mx = tx(melt.peak_temperature)
    svg.line(mx, y0, mx, y1, stroke=_MUTED, stroke_width=1.4, dash="5 3")
    svg.text(mx, y0 - 8, f"Tm = {melt.peak_temperature} °C", size=VIZ_LABEL_SIZE + 1,
             fill=_FG, anchor="middle", weight="700")

    # legend (two curves)
    lx, ly = x0 + 8, y0 + 14
    svg.line(lx, ly, lx + 22, ly, stroke=color("viz-curve"), stroke_width=1.5)
    svg.text(lx + 28, ly + 4, "fluorescence", size=VIZ_LABEL_SIZE, fill=_FG)
    svg.line(lx, ly + 18, lx + 22, ly + 18, stroke=color("viz-derivative"), stroke_width=2.6)
    svg.text(lx + 28, ly + 22, "−dF/dT", size=VIZ_LABEL_SIZE, fill=_FG)

    # notes below the plot
    ny = y1 + 54
    if melt.dh_source == "approximate":
        svg.text(_M, ny, "ΔH approximated — peak width is indicative only",
                 size=VIZ_LABEL_SIZE, fill=_MUTED)
        ny += 16
    if dimer_tm_warning:
        delta = dimer_tm_warning.get("delta_c", "?")
        svg.text(_M, ny, f"Predicted dimer Tm is within {delta} °C of the product peak — "
                         "a single melt peak may not confirm specificity.",
                 size=VIZ_LABEL_SIZE, fill=color("viz-warn"))
        ny += 16

    total_h = round(max(_MELT_H, ny + 10), 2)
    svg.height = total_h
    svg.view_box = f"0 0 {_MELT_W} {total_h}"
    return svg.render()


# ── PART D: agarose-gel panel ───────────────────────────────────────────────────

def render_gel(gel, *, mirna_id="") -> str:
    """Panel 3 — simulated agarose gel: 25 bp ladder + single product band (SPEC §D)."""
    lane_w = 128
    x_lad = 92
    x_prod = x_lad + lane_w + 64
    gel_w = x_prod + lane_w + 96
    gel_h = gel.y_top + gel.lane_height + 78
    well_y = gel.y_top - 20

    n_min, n_max = gel.n_min, gel.n_max
    prod_bp, prod_y = gel.product_band

    svg = Svg(gel_w, gel_h,
              title=f"Simulated agarose gel — {mirna_id or 'amplicon'}",
              desc=(
                  f"Simulated {VIZ_GEL_AGAROSE_PCT:g}% agarose gel. Ladder lane with "
                  f"{len(gel.ladder_bands)} bands from {n_min} to {n_max} base pairs. "
                  f"Product lane with a single band at {prod_bp} base pairs. "
                  "Relative-size illustration, not experimental data."
              ))
    svg.raw(_defs())
    svg.rect(0, 0, gel_w, gel_h, fill=_BG)

    # header
    svg.text(_M, 34, "Agarose gel — simulated", size=19, fill=_FG, weight="700")
    svg.text(_M, 52, VIZ_SIMULATED_LABEL, size=VIZ_LABEL_SIZE, fill=_MUTED)

    def _lane(x, title):
        # lane slab + well. The caption sits 10 px above the well, which Y_TOP
        # keeps clear of the panel header (see VIZ_GEL_Y_TOP).
        svg.rect(x, gel.y_top - 4, lane_w, gel.lane_height + 12, rx=8,
                 fill="url(#g-surface)", stroke=_BORDER, stroke_width=1)
        svg.rect(x + 12, well_y, lane_w - 24, 12, rx=3, fill=color("viz-band"), opacity=0.85)
        svg.text(x + lane_w / 2, well_y - 10, title, size=VIZ_LABEL_SIZE + 1,
                 fill=_FG, anchor="middle", weight="700")

    # Size guide lines first so they sit BEHIND the lanes and bands.
    for bp, y, is_ref in gel.ladder_bands:
        if is_ref:
            svg.line(x_lad + lane_w - 16, y, x_prod + 8, y, stroke=_BORDER,
                     stroke_width=1, dash="3 4")

    with svg.group(aria_label="Ladder lane") as g:
        _lane(x_lad, "Ladder")
        for bp, y, is_ref in gel.ladder_bands:
            h = VIZ_GEL_BAND_HEIGHT + (3 if is_ref else 0)
            g.rect(x_lad + 8, y - h / 2, lane_w - 16, h, rx=3,
                   fill=color("viz-band-ref") if is_ref else color("viz-band"),
                   opacity=1 if is_ref else 0.8)
            g.text(x_lad - 10, y + 4, f"{bp}", size=VIZ_LABEL_SIZE,
                   fill=_FG if is_ref else _MUTED, anchor="end",
                   weight="700" if is_ref else None)
        g.text(x_lad - 10, gel.y_top + gel.lane_height + 22, "bp", size=VIZ_LABEL_SIZE,
               fill=_MUTED, anchor="end")

    with svg.group(aria_label="Product lane") as g:
        _lane(x_prod, "Product")
        h = VIZ_GEL_BAND_HEIGHT + 2
        g.rect(x_prod + 8, prod_y - h / 2, lane_w - 16, h, rx=3,
               fill=_grad("viz-mirna"), stroke=_BG, stroke_width=1, filter=_SHADOW)
        g.text(x_prod + lane_w + 10, prod_y + 4, f"{prod_bp} bp",
               size=VIZ_LABEL_SIZE + 1, fill=color("viz-mirna"), anchor="start", weight="700")
        if gel.out_of_range:
            g.text(x_prod + lane_w / 2, prod_y - h - 10, "Outside ladder range",
                   size=VIZ_LABEL_SIZE, fill=color("viz-warn"), anchor="middle", weight="600")

    svg.text(_M, gel_h - 30, f"{VIZ_GEL_AGAROSE_PCT:g}% agarose · simulated migration",
             size=VIZ_LABEL_SIZE, fill=_MUTED)
    return svg.render()
