# ================================================================
# visualization/constants.py — module-local constants for SPEC_visualization
# Every constant carries a [SOURCE] tag; no magic numbers (SPEC §0.7).
# Shared biology constants (STEMLOOP_BODY, UNIVERSAL_REVERSE, AMPLICON_*)
# are imported from algorithm.constants — NOT duplicated here.
# ================================================================

# Stem of STEMLOOP_BODY: nt 1–14 pair with nt 31–44 around a 16-nt loop (ViennaRNA
# DNA MFE fold ((((((((((((((................)))))))))))))) and exact reverse-
# complementarity of the arms). Used only to DRAW the hairpin.
VIZ_STEM_BP = 14

# --- PART A: coordinate model --------------------------------------------------
# RT overhang length is NOT a constant here: it is read from the RT primer
# (len(S) − 44) and must lie in algorithm.constants OVERHANG_LENGTH_MIN..MAX
# (5–7 nt, project decision 2026-09-18; 6 nt is the Chen05 standard).

# Region names + colour tokens — the single colour contract shared by all 3 panels
# (SPEC §A.5). `name` is what appears in meta.regions; `token` is the CSS custom
# property the SVG fills with (SPEC §E.5).
REGION_TAIL      = "F_tail"      # R1 — forward-primer 5' GC tail (not on the miRNA)
REGION_MIRNA     = "miRNA"       # R2 — mature miRNA (the only target-specific region)
REGION_STEMLOOP  = "stemloop"    # R3 — stem-loop primer body, outside the universal site
REGION_UNIVERSAL = "universal"   # R4 — universal-reverse binding site

REGION_COLOR_TOKEN = {
    REGION_TAIL:      "viz-tail",
    REGION_MIRNA:     "viz-mirna",
    REGION_STEMLOOP:  "viz-stemloop",
    REGION_UNIVERSAL: "viz-universal",
}

# --- PART B: Reaction panel layout (SPEC §B.4) ---------------------------------
VIZ_CANVAS_WIDTH     = 900   # px [SPEC §B.4]
VIZ_MARGIN           = 40    # px [SPEC §B.4]
VIZ_CHAR_PITCH       = 20    # px — column pitch in zoomed windows [SPEC §B.4]
VIZ_BAR_HEIGHT       = 44    # px — sequence-bar height [SPEC §B.4]
VIZ_STAGE_GAP        = 36    # px — vertical gap between stages [SPEC §B.4]
VIZ_MAX_ZOOM_COLUMNS = 34    # max columns in one zoomed window [SPEC §B.4]
VIZ_MONO_SIZE        = 13    # px — monospace glyph size [SPEC §B.4]
VIZ_LABEL_SIZE       = 12    # px — small label size [SPEC §B.4]
VIZ_TITLE_SIZE       = 15    # px — stage title
VIZ_NOTE_SIZE        = 14    # px — per-stage explanatory note (larger, readable)

# --- PART C: melting curve (SPEC §C.2, §C.1.3) --------------------------------
VIZ_MELT_T_START = 60.0    # °C — typical ramp start [Ririe97]
VIZ_MELT_T_END   = 95.0    # °C — ramp end [Ririe97]
VIZ_MELT_T_STEP  = 0.1     # °C — 351 points, matches qPCR instrument resolution
VIZ_DH_PER_BP    = 8000    # cal/mol/bp — mean melting ΔH per bp [SL04], fallback only
VIZ_NN_MAX_LENGTH = 60     # bp — above this, NN ΔH unavailable → per-bp fallback [primer3 limit]

# --- PART D: agarose gel (SPEC §D.2) ------------------------------------------
VIZ_GEL_LADDER_BP   = [25, 50, 75, 100, 125, 150, 200, 300, 400, 500]  # 25 bp ladder
VIZ_GEL_REFERENCE_BP = {100, 200, 300, 400, 500}    # bold reference bands (maker convention)
VIZ_GEL_AGAROSE_PCT = 3.0     # % — resolves 50–150 bp (stem-loop amplicon range)
VIZ_GEL_LANE_HEIGHT = 420     # px [SPEC §D.2]
VIZ_GEL_BAND_HEIGHT = 7       # px [SPEC §D.2]
# px — migration start (just below the wells). Must clear the panel header:
# the title sits at y=34 and the "simulated" label at y=52, and the lane captions
# are drawn at (Y_TOP - 30), so anything below ~110 makes them collide.
VIZ_GEL_Y_TOP       = 124

# --- Honesty label (SPEC §0.4) — embedded in every panel, cannot be disabled ---
VIZ_SIMULATED_LABEL = "Simulated from predicted values — not experimental data"

# --- Theme colour tokens + hex fallbacks (SPEC §E.5) ---------------------------
# The SVG fills with var(--token, #fallback); the frontend defines --viz-* per
# theme. Fallbacks keep the SVG legible when opened standalone (no CSS host).
VIZ_COLOR_FALLBACK = {
    # region tokens (SPEC §A.5) — cohesive jewel tones; `-hi` = gradient top stop
    "viz-tail":       "#B07A2E",  # amber — non-specific 5' tail
    "viz-tail-hi":    "#D6A155",
    "viz-mirna":      "#2A9D8F",  # teal — target-specific miRNA region [SPEC §E.5]
    "viz-mirna-hi":   "#5AC7B7",
    "viz-stemloop":   "#5B6FC9",  # indigo — stem-loop body
    "viz-stemloop-hi": "#8A99EA",
    "viz-universal":  "#9059C0",  # violet — universal-reverse site
    "viz-universal-hi": "#B78BDC",
    # soft fills for the hairpin schematic (stages 0-3): light tint + mid edge, dark text
    "viz-hairpin":      "#E7EAFB",  # stem-loop RT primer
    "viz-hairpin-edge": "#8F9DE3",
    "viz-cdna":         "#DDF2EE",  # cDNA made by RT
    "viz-cdna-edge":    "#4FB3A5",
    # chart/structure tokens (used by PART C/D)
    "viz-axis":       "#94A3B8",
    "viz-curve":      "#2563EB",
    "viz-derivative": "#0F766E",
    "viz-band":       "#334155",
    "viz-band-ref":   "#0F172A",
    # text/background (theme-aware; not region colours)
    "viz-fg":       "#243244",
    "viz-muted":    "#6B7A90",
    "viz-bg":       "#FFFFFF",
    "viz-surface":  "#F7F9FC",   # very light card background
    "viz-border":   "#E3E9F2",   # card border
    "viz-warn":     "#DC2626",
}


def color(token: str) -> str:
    """Return a CSS `var(--token, #fallback)` string for a colour token (SPEC §E.5)."""
    fallback = VIZ_COLOR_FALLBACK.get(token)
    return f"var(--{token}, {fallback})" if fallback else f"var(--{token})"
