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


_HP_FILL, _HP_EDGE = color("viz-hairpin"), color("viz-hairpin-edge")   # stem-loop primer
_CD_FILL, _CD_EDGE = color("viz-cdna"), color("viz-cdna-edge")         # new RT-made cDNA
_LOOP_N = 16          # loop nt of STEMLOOP_BODY (44 - 2 * VIZ_STEM_BP)
_NECK = 16            # short fillet from the straight arms into the loop circle
_ENTRY_EXTRA = math.radians(14)   # entry point sits this far above/below the arm line


def _mono(p):
    return min(VIZ_MONO_SIZE, p * 1.45)


def _loop_geom(mono):
    """(radius, entry angle phi) of the loop circle. The circle is sized so the 16
    loop letters sit ~1.2 glyphs apart on the arc between the two entries; the
    entries sit a little outside the arm lines so each fillet rises monotonically
    (no inward pinch)."""
    h = (VIZ_BAR_HEIGHT + _PAIR_GAP) / 2
    need = (_LOOP_N + 1) * mono * 1.2
    r = h + 4
    while True:
        phi = min(math.asin(h / r) + _ENTRY_EXTRA, math.radians(80))
        if (2 * math.pi - 2 * phi) * r >= need:
            return r, phi
        r += 0.5


def _loop_extent(mono):
    """px from the last stem column's right edge to the loop's outer right edge."""
    r, phi = _loop_geom(mono)
    return _TXT_PAD + _NECK + r * math.cos(phi) + r + VIZ_BAR_HEIGHT / 2 + 2


def _hp_margin(mono):
    """Height the loop needs above the top row / below the bottom row."""
    r, _ = _loop_geom(mono)
    return max(0.0, r - (VIZ_BAR_HEIGHT + _PAIR_GAP) / 2)


def _fit_pitch(x_left, cols):
    """Largest pitch (≤ VIZ_CHAR_PITCH) keeping `cols` columns from x_left plus the
    loop inside the content width."""
    p = float(VIZ_CHAR_PITCH)
    while p > 8 and x_left + cols * p + _loop_extent(_mono(p)) > _W - _M:
        p -= 0.25
    return p


def _disk(cx, cy, r):
    return (f"M {cx - r:.2f} {cy:.2f} a {r:.2f} {r:.2f} 0 1 0 {2 * r:.2f} 0 "
            f"a {r:.2f} {r:.2f} 0 1 0 {-2 * r:.2f} 0 Z")


def _stemloop(node, x_ov, y_top, S, o, pitch, mono, ext="", a_round=True, a_label="left"):
    """The stem-loop RT primer (or its cDNA) as one smooth hairpin on TWO rows.

    Top row: stem arm A (the primer 5' end), read 5'->3'. In stages 1-2 the miRNA
    shares this row, ending right where arm A starts (its 3' end stacks on the stem).
    Bottom row: [ext] + 3' overhang + stem arm B, read 3'->5' left to right — the
    overhang lies directly under the miRNA 3' end, ext under the rest of the miRNA.
    The arms run straight to just past their last letter, then a short monotonic
    fillet enters a near-full loop circle whose letters follow the ring.
    a_round: round (True) or flat (False, abutting the miRNA) left end of arm A.
    a_label: "left" (5' label beside arm A) or "above" (over its first column).
    Returns (right_x, bottom_row_y).
    """
    stem, half = VIZ_STEM_BP, VIZ_BAR_HEIGHT / 2
    body = len(S) - o
    arm_b, loop, arm_a = S[body - stem:body], S[stem:body - stem], S[:stem]
    y_bot = y_top + VIZ_BAR_HEIGHT + _PAIR_GAP
    y1c, y2c = y_top + half, y_bot + half
    cy = (y1c + y2c) / 2
    r, phi = _loop_geom(mono)
    xa = x_ov + o * pitch                               # arm A column 0
    xe = xa + stem * pitch + _TXT_PAD                   # straight arms end here
    ex = xe + _NECK                                     # loop entry x
    xc = ex + r * math.cos(phi)
    e1y, e2y = cy - r * math.sin(phi), cy + r * math.sin(phi)
    t1 = (math.sin(phi), -math.cos(phi))                # clockwise tangent at the top entry
    k = _NECK * 0.6
    a_start = xa - _TXT_PAD + half if a_round else xa + 1.5
    main = (
        f"M {a_start:.2f} {y1c:.2f} L {xe:.2f} {y1c:.2f} "
        f"C {xe + k:.2f} {y1c:.2f} {ex - k * t1[0]:.2f} {e1y - k * t1[1]:.2f} {ex:.2f} {e1y:.2f} "
        f"A {r:.2f} {r:.2f} 0 1 1 {ex:.2f} {e2y:.2f} "
        f"C {ex - k * t1[0]:.2f} {e2y + k * t1[1]:.2f} {xe + k:.2f} {y2c:.2f} {xe:.2f} {y2c:.2f} "
        f"L {(x_ov if ext else x_ov - _TXT_PAD + half):.2f} {y2c:.2f}"
    )
    x_ext = x_ov - len(ext) * pitch
    pieces = [(main, _HP_EDGE, _HP_FILL)]
    if ext:
        pieces.append((f"M {x_ext - _TXT_PAD + half:.2f} {y2c:.2f} L {x_ov:.2f} {y2c:.2f}",
                       _CD_EDGE, _CD_FILL))
    ends = [((x_ext if ext else x_ov) - _TXT_PAD + half, y2c,
             _CD_EDGE if ext else _HP_EDGE, _CD_FILL if ext else _HP_FILL)]
    if a_round:
        ends.append((a_start, y1c, _HP_EDGE, _HP_FILL))
    # outline pass, then fill pass, so neighbouring pieces never cover each other's rim
    for d, edge, _ in pieces:
        node.path(d, fill="none", stroke=edge, stroke_width=VIZ_BAR_HEIGHT + 2)
    for cx_, cy_, edge, _ in ends:
        node.path(_disk(cx_, cy_, half + 1), fill=edge)
    for d, _, fill in pieces:
        node.path(d, fill="none", stroke=fill, stroke_width=VIZ_BAR_HEIGHT)
    for cx_, cy_, _, fill in ends:
        node.path(_disk(cx_, cy_, half), fill=fill)

    _bar_text(node, xa, y_top, arm_a, pitch, "5to3", mono)
    if ext:
        _bar_text(node, x_ext, y_bot, ext, pitch, "3to5", mono)
    _bar_text(node, x_ov, y_bot, S[body:], pitch, "3to5", mono)
    _bar_text(node, xa, y_bot, arm_b, pitch, "3to5", mono)
    _rungs(node, xa, stem, pitch, y_top + VIZ_BAR_HEIGHT, y_bot)
    lab = half + VIZ_LABEL_SIZE * 0.35
    if a_label == "left":
        node.text(xa - _TXT_PAD - 10, y_top + lab, "5'", size=VIZ_LABEL_SIZE, fill=_MUTED,
                  anchor="end", weight="600")
    else:
        node.text(xa + pitch / 2, y_top - 9, "5'", size=VIZ_LABEL_SIZE, fill=_MUTED,
                  anchor="middle", weight="600")
    node.text((x_ext if ext else x_ov) - _TXT_PAD - 10, y_bot + lab, "3'", size=VIZ_LABEL_SIZE,
              fill=_MUTED, anchor="end", weight="600")
    # loop letters in sequence order: from arm A's 3' end (top entry) clockwise to arm B
    t0, span = math.pi + phi, 2 * math.pi - 2 * phi
    for i, ch in enumerate(loop):
        t = t0 + (i + 1) * span / (len(loop) + 1)
        node.text(round(xc + r * math.cos(t), 2), round(cy + r * math.sin(t) + mono * 0.35, 2),
                  ch, size=mono, fill=_FG, anchor="middle", weight="600")
    return xc + r + half, y_bot


def _arrow(node, x1, y, x2, *, label=None):
    node.line(x1, y, x2, y, stroke=_MUTED, stroke_width=2, linecap="round")
    head = 7 if x2 > x1 else -7
    node.path(f"M {x2} {y} L {x2 - head} {y - 4.5} L {x2 - head} {y + 4.5} Z", fill=_MUTED)
    if label:
        node.text((x1 + x2) / 2, y - 9, label, size=VIZ_LABEL_SIZE, fill=_MUTED, anchor="middle")


def _roles(node, y, items):
    """'Roles' block: a colour chip + bold name + what that molecule does in this step."""
    y += 4
    node.text(_M, y + VIZ_LABEL_SIZE, "Roles", size=VIZ_LABEL_SIZE, fill=_FG, weight="700")
    y += VIZ_LABEL_SIZE + 8
    for token, name, text in items:
        node.rect(_M, y + 1, 11, 11, rx=3, fill=color(token))
        node.text(_M + 18, y + 10, name, size=VIZ_LABEL_SIZE, fill=_FG, weight="700")
        y = _wrap_note(node, _M + 18 + len(name) * VIZ_LABEL_SIZE * 0.62 + 8, y - 2, text,
                       _CONTENT_W - 30 - len(name) * VIZ_LABEL_SIZE * 0.62,
                       size=VIZ_LABEL_SIZE) + 2
    return y


# ── per-stage draw functions (draw into scratch node, return end y) ───────────────

def _stage0(node, y, model, oscale):
    y = _title(node, y, "Stage 0 · Components")
    rows = [
        (model.mirna_dna, "miRNA"),
        (model.stemloop_rt, "Stem-loop RT (S)"),
        (model.forward, "Forward (F)"),
        (model.universal_reverse, "Universal reverse (R)"),
    ]
    # label column sized to the longest label, plus room for the 5' end label
    label_w = max(len(n) for _, n in rows) * (VIZ_LABEL_SIZE + 1) * 0.62 + 28
    bar_x = _M + label_w + _TXT_PAD
    avail = _W - _M - _GUT - _TXT_PAD - bar_x
    s = min(avail / max(len(r[0]) for r in rows if r[0] is not model.stemloop_rt),
            _fit_pitch(bar_x, len(model.overhang) + VIZ_STEM_BP))
    mono = _mono(s)
    for seq, name in rows:
        if seq is model.stemloop_rt:
            y += _hp_margin(mono)
            node.text(_M, y + VIZ_BAR_HEIGHT + _PAIR_GAP / 2 + 4, name, size=VIZ_LABEL_SIZE + 1,
                      fill=_FG, weight="600")
            _, yb = _stemloop(node, bar_x, y, seq, len(model.overhang), s, mono)
            y = yb + VIZ_BAR_HEIGHT + _hp_margin(mono) + 22
            continue
        node.text(_M, y + VIZ_BAR_HEIGHT / 2 + 4, name, size=VIZ_LABEL_SIZE + 1, fill=_FG, weight="600")
        _bar(node, bar_x, y, seq, s, "5to3", fill="url(#g-surface)", mono_size=mono)
        y += VIZ_BAR_HEIGHT + 22
    y = _wrap_note(node, _M, y, model.stages[0].annotation_en, _CONTENT_W)
    return _roles(node, y, [
        ("viz-mirna", "miRNA", "the target — the only sequence the assay is specific for."),
        ("viz-hairpin-edge", "S", "hairpin RT primer: its single-stranded 3' overhang recognises the "
                                  "miRNA 3' end; the stem-loop carries the universal site."),
        ("viz-tail", "F", "forward primer: a copy of the miRNA 5' end plus a GC tail that raises Tm."),
        ("viz-universal", "R", "universal reverse primer: binds the site inside the stem-loop, "
                               "the same for every miRNA."),
    ])


def _duplex_rows(model, extra_left_cols=0):
    """Shared geometry for stages 1-2: pitch, mono, miRNA column 0 x, overhang x."""
    L, o = len(model.mirna_dna), len(model.overhang)
    p = _fit_pitch(_OX, extra_left_cols + L + VIZ_STEM_BP)
    x0 = _OX + extra_left_cols * p
    return p, _mono(p), x0, x0 + (L - o) * p


def _mirna_top_row(node, x0, y_top, m, p, mono, *, caption):
    """miRNA in the TOP row, its 3' end stacked against the primer's arm A."""
    _bar(node, x0, y_top, m, p, "5to3", fill="url(#g-surface)", mono_size=mono,
         show_ends=False, pad_r=-2)
    lab = VIZ_BAR_HEIGHT / 2 + VIZ_LABEL_SIZE * 0.35
    node.text(x0 - _TXT_PAD - 10, y_top + lab, "5'", size=VIZ_LABEL_SIZE, fill=_MUTED,
              anchor="end", weight="600")
    node.text(x0 + (len(m) - 0.5) * p, y_top - 9, "3'", size=VIZ_LABEL_SIZE, fill=_MUTED,
              anchor="middle", weight="600")
    node.text(x0, y_top - 9, caption, size=VIZ_LABEL_SIZE, fill=_MUTED)


def _stage1(node, y, model, oscale):
    y = _title(node, y, "Stage 1 · RT annealing")
    m, o = model.mirna_dna, len(model.overhang)
    p, mono, x0, x_ov = _duplex_rows(model)
    y_top = y + max(_hp_margin(mono), 18)
    _mirna_top_row(node, x0, y_top, m, p, mono, caption="miRNA (RNA)")
    frame = 4
    node.rect(x_ov - 3, y_top - frame, o * p + 1, VIZ_BAR_HEIGHT + 2 * frame, rx=_BAR_RX + 2,
              fill="none", stroke=color("viz-mirna"), stroke_width=2.5)
    _, y_bot = _stemloop(node, x_ov, y_top, model.stemloop_rt, o, p, mono,
                         a_round=False, a_label="above")
    _rungs(node, x_ov, o, p, y_top + VIZ_BAR_HEIGHT + frame + 1, y_bot)
    # RT will extend the primer 3' end leftward, in the empty lane under the miRNA
    _arrow(node, x_ov - _TXT_PAD - 36, y_bot + VIZ_BAR_HEIGHT / 2, x0 + 6,
           label="RT extension (5'→3')")
    y = y_bot + VIZ_BAR_HEIGHT + max(_hp_margin(mono), 0) + 14
    y = _wrap_note(node, _M, y, model.stages[1].annotation_en, _CONTENT_W)
    return _roles(node, y, [
        ("viz-mirna", "miRNA", "the RT template; its 3' end stacks against the primer stem."),
        ("viz-hairpin-edge", "S", f"its {o}-nt 3' overhang pairs with the miRNA 3' end and primes "
                                  "reverse transcription; the stem stays folded."),
    ])


def _stage2(node, y, model, oscale):
    y = _title(node, y, "Stage 2 · RT product (cDNA)")
    m, o = model.mirna_dna, len(model.overhang)
    S = model.stemloop_rt
    ext = model.cdna[len(S):]
    p, mono, x0, x_ov = _duplex_rows(model)
    y_top = y + max(_hp_margin(mono), 18)
    _mirna_top_row(node, x0, y_top, m, p, mono, caption="miRNA (RNA) — read 3'→5' by the RT")
    _, y_bot = _stemloop(node, x_ov, y_top, S, o, p, mono, ext=ext,
                         a_round=False, a_label="above")
    _rungs(node, x0, len(m), p, y_top + VIZ_BAR_HEIGHT, y_bot)
    node.text(x0 + len(ext) * p / 2, y_bot + VIZ_BAR_HEIGHT + 16,
              f"new cDNA ({len(ext)} nt) — RT copy of the miRNA",
              size=VIZ_LABEL_SIZE, fill=color("viz-cdna-edge"), anchor="middle", weight="700")
    y = y_bot + VIZ_BAR_HEIGHT + max(_hp_margin(mono), 22) + 12
    y = _wrap_note(node, _M, y, model.stages[2].annotation_en, _CONTENT_W)
    return _roles(node, y, [
        ("viz-mirna", "miRNA", "was read end to end; still paired to the cDNA until the first "
                               "PCR denaturation."),
        ("viz-hairpin-edge", "S", "is now the 5' part of the cDNA, so every cDNA carries the "
                                  "stem-loop and its universal site."),
        ("viz-cdna-edge", "cDNA", f"{len(S)} nt primer + {len(ext)} nt copied from the miRNA."),
    ])


def _stage3(node, y, model, oscale):
    """PCR on the linearised strands: F on the cDNA (rows 1-2), R on the strand F
    made (rows 3-4), then the amplicon both primer 5' ends define. Column c is
    cycle-1-strand index c throughout, so every row and the amplicon line up."""
    y = _title(node, y, "Stage 3 · PCR — stem-loop unfolded, F + R → amplicon")
    F, tail, k = model.forward, model.tail, model.forward_binding_length
    S, U, j = model.stemloop_rt, model.universal_reverse, model.universal_offset
    ext = model.cdna[len(S):]
    t, p = len(tail), oscale
    mono = _mono(p)
    col = lambda c: _OX + c * p                              # noqa: E731
    mid = VIZ_BAR_HEIGHT / 2

    # rows 1-2: F anneals to the 3' end of the linear cDNA
    y_f = y + 18
    if tail:
        _bar(node, col(0), y_f, tail, p, "5to3", fill=_grad("viz-tail"), mono_size=mono,
             dash=True, text_fill=_BG, show_ends=False, pad_r=0)
    _bar(node, col(t), y_f, F[t:], p, "5to3", fill=_grad("viz-mirna"), mono_size=mono,
         text_fill=_BG, show_ends=False, pad_l=0 if tail else _TXT_PAD)
    _end_labels(node, col(0) - _TXT_PAD, y_f, len(F) * p + 2 * _TXT_PAD, "5to3")
    xf = col(len(F)) + _TXT_PAD + 30
    _arrow(node, xf, y_f + mid, xf + 80, label="F extends")
    if tail:
        node.text(col(t / 2), y_f - 9, "GC tail", size=VIZ_LABEL_SIZE, fill=_MUTED,
                  anchor="middle")
    node.text(col(len(model.sense_strand)), y_f + mid + 4,
              "cDNA — stem-loop unfolded at 95 °C", size=VIZ_LABEL_SIZE,
              fill=_MUTED, anchor="end", weight="600")
    y_c = y_f + VIZ_BAR_HEIGHT + _PAIR_GAP
    _bar(node, col(t), y_c, ext, p, "3to5", fill=_CD_FILL, mono_size=mono,
         show_ends=False, pad_r=0)
    _bar(node, col(t + len(ext)), y_c, S, p, "3to5", fill=_HP_FILL, mono_size=mono,
         show_ends=False, pad_l=0)
    _end_labels(node, col(t) - _TXT_PAD, y_c, len(model.cdna) * p + 2 * _TXT_PAD, "3to5")
    _rungs(node, col(t), k, p, y_f + VIZ_BAR_HEIGHT, y_c)

    # rows 3-4: R anneals to the universal site of the strand F made
    y_s = y_c + VIZ_BAR_HEIGHT + 30
    # coloured like the cDNA it copies (mint under the RT copy, lavender under S), plus the tail
    sense, n_ext = model.sense_strand, len(ext)
    if tail:
        _bar(node, col(0), y_s, tail, p, "5to3", fill=_grad("viz-tail"), mono_size=mono,
             text_fill=_BG, show_ends=False, pad_r=0)
    _bar(node, col(t), y_s, sense[t:t + n_ext], p, "5to3", fill=_CD_FILL, mono_size=mono,
         show_ends=False, pad_l=0 if tail else _TXT_PAD, pad_r=0)
    _bar(node, col(t + n_ext), y_s, sense[t + n_ext:], p, "5to3", fill=_HP_FILL,
         mono_size=mono, show_ends=False, pad_l=0)
    _end_labels(node, col(0) - _TXT_PAD, y_s, len(sense) * p + 2 * _TXT_PAD, "5to3")
    y_u = y_s + VIZ_BAR_HEIGHT + _PAIR_GAP
    _bar(node, col(j), y_u, U, p, "3to5", fill=_grad("viz-universal"), mono_size=mono,
         text_fill=_BG)
    _rungs(node, col(j), len(U), p, y_s + VIZ_BAR_HEIGHT, y_u)
    xr = col(j) - _TXT_PAD - 40                              # clear of R's 3' label
    _arrow(node, xr, y_u + mid, xr - 80, label="R extends")
    node.text(col(0), y_u + mid + 4, "cycle-1 strand, made by F", size=VIZ_LABEL_SIZE,
              fill=_MUTED, weight="600")
    cut = col(j + len(U))                                    # R 5' end = amplicon end
    node.line(cut, y_s - 6, cut, y_s + VIZ_BAR_HEIGHT + 6, stroke=color("viz-universal"),
              stroke_width=1.5, dash="5 3")

    # final product
    y = y_u + VIZ_BAR_HEIGHT + 30
    node.text(_M, y, f"Final product · amplicon {len(model.amplicon)} bp · GC {model.gc_percent}% "
              "(F 5' end → R 5' end)", size=VIZ_LABEL_SIZE + 2, fill=_FG, weight="700")
    y += 14
    for reg in model.regions:
        rw = reg.length * p
        node.rect(col(reg.start), y, rw, VIZ_BAR_HEIGHT, rx=6, fill=_grad(reg.color_token),
                  stroke=_BG, stroke_width=1.5, filter=_SHADOW)
        node.text(col(reg.start) + rw / 2, y + VIZ_BAR_HEIGHT + VIZ_LABEL_SIZE + 2,
                  f"{reg.length}", size=VIZ_LABEL_SIZE, fill=_MUTED, anchor="middle")
    _end_labels(node, _OX, y, len(model.amplicon) * p, "5to3")
    y += VIZ_BAR_HEIGHT + VIZ_LABEL_SIZE + 12
    if model.size_warning:
        node.text(_M, y + 10, "⚠ Amplicon size outside the qPCR range",
                  size=VIZ_LABEL_SIZE + 1, fill=color("viz-warn"), weight="600")
        y += 20
    y = _wrap_note(node, _M, y, model.stages[3].annotation_en, _CONTENT_W)
    return _roles(node, y, [
        ("viz-cdna-edge", "cDNA", "linear template once the miRNA is gone and the stem-loop "
                                  "has melted."),
        ("viz-tail", "F", f"its {k}-nt specific region pairs where the miRNA 5' end was (the "
                          "miRNA-specific step); extends to make the cycle-1 strand."),
        ("viz-universal", "R", "binds the universal site that strand copied from S; the "
                               "product stops at its 5' end."),
        ("viz-hairpin-edge", "S", "no longer a hairpin — its sequence is now the stem-loop and "
                                  "universal part of every amplicon."),
    ])


_STAGE_FNS = [
    ("Stage 0: Components", _stage0),
    ("Stage 1: RT annealing", _stage1),
    ("Stage 2: RT product (cDNA)", _stage2),
    ("Stage 3: PCR (forward + universal reverse) → amplicon", _stage3),
]


# ── PART B: reaction panel ──────────────────────────────────────────────────────

def render_reaction(model, mirna_id: str = "") -> str:
    """Panel 1 — the 4-stage stem-loop RT-qPCR reaction (SPEC §B)."""
    longest = max(len(model.sense_strand), len(model.cdna), len(model.amplicon),
                  len(model.stemloop_rt), len(model.mirna_dna))
    oscale = _OW / longest

    svg = Svg(_W, 0, title=f"Reaction schematic — {mirna_id or 'miRNA'}",
              desc=(
                  "Schematic of the four-stage stem-loop RT-qPCR reaction: components, "
                  "RT annealing, cDNA synthesis, and PCR in which the forward and universal "
                  "reverse primers bind the linearised strands to form the amplicon. "
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
