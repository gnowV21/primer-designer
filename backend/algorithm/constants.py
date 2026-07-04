# ================================================================
# algorithm/constants.py  —  v2.7
# ALL scientific constants centralised here.
# Every constant carries a source comment.
# ================================================================


# ----------------------------------------------------------------
# SECTION A: STEM-LOOP RT PRIMER
# [Chen05] Chen et al. 2005 | [K11] Kramer 2011 | [V07] Varkonyi-Gasic 2007
# ----------------------------------------------------------------

STEMLOOP_BODY = "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGAC"  # 44 nt [Chen05][K11]
STEMLOOP_BODY_LENGTH = 44

OVERHANG_LENGTH_DEFAULT = 6   # nt — optimal for steric hindrance vs pre-miRNA [Chen05]
OVERHANG_LENGTH_MIN = 4
OVERHANG_LENGTH_MAX = 8

MFE_STEMLOOP_MIN = -13.0      # kcal/mol — primer3-py DNA proxy calibrated [R2]
MFE_STEMLOOP_MAX = -10.0      # kcal/mol — primer3-py DNA proxy calibrated [R2]
MFE_STEMLOOP_OPTIMAL = -11.5  # kcal/mol — primer3-py DNA proxy calibrated [R2]

# ViennaRNA/RNAfold RNA-folding calibrated values.
# STEMLOOP_BODY alone folds to ≈ −25.7 kcal/mol (RNA.fold).
# Full RT primer (+ 6 nt overhang) ≈ −27.5 kcal/mol.
# Range −35 to −20 captures reasonable overhang length variation (4–8 nt).
MFE_STEMLOOP_MIN_RNA     = -35.0   # kcal/mol [RNA MFE calibrated]
MFE_STEMLOOP_MAX_RNA     = -20.0   # kcal/mol [RNA MFE calibrated]
MFE_STEMLOOP_OPTIMAL_RNA = -26.0   # kcal/mol [RNA MFE calibrated]

# RT primer concentration [K11]: 1 nM optimal (not 50 nM from Chen 2005)
RT_PRIMER_CONC_OPTIMAL = 1.0     # nM final [K11]
RT_PRIMER_CONC_CHEN_2005 = 50.0  # nM original [C05] — deprecated

# Refolding protocol [K11] p.10 — mineral oil overlay critical
REFOLDING_PROTOCOL = {
    "use_mineral_oil_overlay": True,  # [K11] critical — overlay 100 µL mineral oil
    "steps": [
        {"temp_c": 95, "duration_min": 10,  "note": "Complete denaturation"},
        {"temp_c": 75, "duration_min": 60,  "note": "Slow cool — mineral oil overlay"},
        {"temp_c": 68, "duration_min": 60,  "note": "Intermediate folding"},
        {"temp_c": 65, "duration_min": 60,  "note": "Near-final structure"},
        {"temp_c": 62, "duration_min": 60,  "note": "Final stabilization"},
        {"temp_c": 60, "duration_min": 240, "note": "Hold — complete hairpin lock-in"},
    ],
    "storage": "After refolding, store at -20°C. Never heat above room temperature again.",
    "working_stock": "Make 5× working stock at 5.0 nM. Store at -20°C.",
    "source": "Kramer 2011, Curr Protoc Mol Biol, Unit 15.10, p.10",
}


# ----------------------------------------------------------------
# SECTION B: UNIVERSAL REVERSE PRIMER
# ----------------------------------------------------------------

UNIVERSAL_REVERSE = "CCAGTGCAGGGTCCGAGGTA"           # 20 nt — improved [K11]
UNIVERSAL_REVERSE_PRIMER = UNIVERSAL_REVERSE          # alias for multiplex_check
UNIVERSAL_REVERSE_CHEN_2005 = "GTGCAGGGTCCGAGGT"     # 16 nt original [C05]
UNIVERSAL_REVERSE_TM_PRECALC = 60.4   # °C — pre-calculated
UNIVERSAL_REVERSE_GC_PRECALC = 65.0   # %

# [Bell17] Bell 2017 Methods Mol Biol — max panel size for multiplex stem-loop RT/preamp
MULTIPLEX_PANEL_MAX = 20   # >20 assays per tube: cross-dimer risk increases significantly


# ----------------------------------------------------------------
# SECTION C: FORWARD PRIMER DESIGN  [K11][V07][R2]
# ----------------------------------------------------------------

# v2.7 UPDATE: 12–17 nt per Kramer 2011 (not 10–12)
# [K11] p.3: "Take the first 12 to 17 nt of the 5′ end of the mature miRNA"
FORWARD_SPECIFIC_LENGTH_MIN = 12
FORWARD_SPECIFIC_LENGTH_MAX = 17
FORWARD_SPECIFIC_LENGTHS = [12, 13, 14, 15, 16, 17]

# [V07]: forward primers EXCLUDE the last 6 nt (used as stemloop overhang)
# "Forward primers are specific to the miRNA sequence but EXCLUDE the last six
#  nucleotides at the 3' end of the miRNA" [V07]
FORWARD_EXCLUDES_LAST_NT = 6

# 5' tail — GC-rich per [V07]: "relatively GC-rich"
FORWARD_TAIL_MIN = 3
FORWARD_TAIL_MAX = 12
FORWARD_TAIL_OPTIMAL_MAX = 7  # nt — Kramer recommends 3-7 [K11]
FORWARD_TAIL_GC_ENRICHED = True  # tails should be GC-rich [V07]

# Max consecutive identical bases allowed in the generated tail pool.
# Busk 2014 (DOI 10.1186/1471-2105-15-29) uses G,A,C,G,C tail order —
# avoiding poly(C)/poly(G) stretches that cause polymerase slippage.
# Value = minimum run length that triggers rejection (reject runs >= this number).
TAIL_MAX_HOMOPOLYMER_RUN = 3   # reject runs ≥ 3 identical bases in tail [Busk14 I4]

FORWARD_MIN_LENGTH = 18    # nt
FORWARD_MAX_LENGTH = 27    # nt [P3P General Settings Max:27]
FORWARD_OPTIMAL_LENGTH = 22  # nt — scoring target

MIN_CANDIDATE_3PRIME_DISTANCE = 2  # nt [P3P PRIMER_MIN_LEFT_THREE_PRIME_DISTANCE adjusted]


# ----------------------------------------------------------------
# SECTION D: THERMODYNAMICS
# ----------------------------------------------------------------

TM_FORWARD_TARGET = 60.0    # °C [R2][PAST24]
TM_FORWARD_TOLERANCE = 2.0  # °C → acceptable 58–62°C
TM_PAIR_DIFF_MAX = 2.0      # °C [PAST24]
TM_ANNEALING_TEMP_DEFAULT = 60.0   # °C
TM_BOUND_FRACTION_TARGET = 97.0    # % [SL04] SantaLucia & Hicks 2004 — Phase 3

# Binding-region Tm target (scoring criterion 2) — v2.8 FIX
# Old value 35°C was calibrated for probe oligos ≤10 nt, NOT for 12–17 nt regions.
# SantaLucia 1998 NN at 200 nM DNA / 50 mM Na+ / 1.5 mM Mg²⁺:
#   12 nt balanced GC miRNA region → Tm ≈ 40°C
#   17 nt balanced GC miRNA region → Tm ≈ 52°C
#   midpoint ≈ 45°C → use as scoring target
# Tolerance ±10°C covers the full 12-17 nt distribution without over-penalising.
TM_BINDING_TARGET    = 45.0  # °C — scoring target for specific binding region [SL98]
TM_BINDING_TOLERANCE = 10.0  # °C — ±10°C: score 100 at 45°C, 70 at 35°C or 55°C


# ----------------------------------------------------------------
# SECTION E: GC CONTENT
# ----------------------------------------------------------------

GC_MIN = 40.0
GC_MAX = 60.0
GC_OPTIMAL = 50.0

GC_STEMLOOP_MIN = 40.0
GC_STEMLOOP_MAX = 60.0

GC_CLAMP_3PRIME_WINDOW = 5
GC_CLAMP_MIN_COUNT = 1
GC_CLAMP_MAX_CONSECUTIVE = 3
GC_CLAMP_MIN_IN_LAST3 = 2     # [IDT PrimerQuest] 3' GC clamp = 2

# miRNA-specific GC clamp scoring (Busk 2014 DOI 10.1186/1471-2105-15-29)
# Two-tier logic: multi-source locked (a) vs single-source pending calibration (b).
# (a) LOCKED — multi-source [Busk14+IDT+Kang17 or theoretical]:
#   2 G/C: optimal anchor+specificity [Busk14+IDT]; CCC: severe extension penalty [Busk14].
# (b) PENDING — single-source [Busk14 heuristic, sampling bias acknowledged]:
#   1 G/C as optimal (GC_CLAMP_1GC_AS_OPTIMAL=True) vs conservative (False=default).
#   IDT prefers 2 G/C for PCR efficiency; Busk14 (miRNA-specific) accepts 1 G/C as optimal.
GC_CLAMP_SCORE_OPTIMAL          = 100  # 2 G/C in last 3 nt — anchor+specificity [Busk14+IDT]
GC_CLAMP_SCORE_1GC_CONSERVATIVE = 75   # 1 G/C — good specificity, weaker anchor (conservative)
GC_CLAMP_SCORE_WEAK             = 50   # 0 G/C (no anchor) OR 3 G/C (too rigid) [Busk14+IDT]
GC_CLAMP_SCORE_TRIPLE_C         = 25   # 3 consecutive C at 3' — extension penalty [Busk14]
GC_CLAMP_1GC_AS_OPTIMAL         = False  # [Busk14 single-source, heuristic] — enable after calibration

MAX_HOMOPOLYMER_RUN = 5       # [P3P Advanced Settings] Max Poly-X = 5
GC_MAX_IN_3PRIME_WINDOW = 5   # [P3P Advanced Settings] Max End GC = 5

# GC-skew [PAST24]
GC_SKEW_OPTIMAL_MAX = 0.0
GC_SKEW_WARNING_THRESHOLD = 0.2


# ----------------------------------------------------------------
# SECTION F: SECONDARY STRUCTURE THRESHOLDS
# ----------------------------------------------------------------

HAIRPIN_DG_MAX_INTERNAL = -3.0    # kcal/mol [ResearchGate qPCR]
HAIRPIN_DG_MAX_3PRIME = -2.0      # kcal/mol — 3' end stricter

SELF_DIMER_DG_MAX = -6.0           # kcal/mol [ResearchGate]
SELF_DIMER_DG_3PRIME_MAX = -5.0    # kcal/mol [Premier Biosoft]

HETERO_DIMER_DG_MAX = -6.0
HETERO_DIMER_DG_3PRIME_MAX = -5.0

END_DIMER_DG_CRITICAL = -5.0      # kcal/mol — polymerase can extend (3'-end) [Premier Biosoft]
END_STABILITY_MAX = 9.0            # kcal/mol [P3P PRIMER_MAX_END_STABILITY]

# Full-structure (global) dimer ΔG threshold (Kang 2017 DOI 10.1261/rna.061150.117)
# Distinct from END_DIMER_DG_CRITICAL (3'-end only).
# Kang: ΔG_total > -9 kcal/mol → OK for qPCR; < -9 → significant qPCR inhibition.
DIMER_FULL_DG_CRITICAL = -9.0     # kcal/mol — full-structure self/hetero-dimer [Kang17]


# ----------------------------------------------------------------
# SECTION G: AMPLICON SIZE
# ----------------------------------------------------------------

AMPLICON_MIN_QPCR = 60    # bp
AMPLICON_MAX_QPCR = 150   # bp [IDT: 70–150 bp]
AMPLICON_IDEAL = 80       # bp


# ----------------------------------------------------------------
# SECTION H: SCORING WEIGHTS (deprecated — use V3)
# ----------------------------------------------------------------

SCORING_WEIGHTS = {
    "tm_accuracy":          0.20,
    "tm_binding_accuracy":  0.10,
    "gc_content":           0.10,
    "mfe_stemloop":         0.20,
    "hairpin_penalty":      0.10,
    "dimer_penalty":        0.10,
    "end_stability":        0.10,
    "amplicon_size":        0.05,
    "tm_pair_match":        0.05,
}


# ----------------------------------------------------------------
# SECTION I: CANDIDATE GENERATION
# ----------------------------------------------------------------

CANDIDATES_TARGET = 50
CANDIDATES_TOP_N = 3

REJECTION_REASONS = [
    "tm_out_of_range",
    "tm_binding_too_low",
    "gc_out_of_range",
    "gc_clamp_fail",
    "gc_end_window_fail",
    "too_short",
    "too_long",
    "homopolymer_run",
    "amplicon_out_of_range",
    "candidate_too_similar",
    "hairpin_fail",
    "self_dimer_fail",
    "hetero_dimer_fail",
    "end_stability_fail",
    "t_at_3prime_warning",   # WARNING ONLY — does not block candidate
]


# ----------------------------------------------------------------
# SECTION J: PRIMER3-PY PARAMETERS
# ----------------------------------------------------------------

P3_DEFAULT_MV_CONC = 50.0     # mM Na+ [P3P]
P3_DEFAULT_DV_CONC = 1.5      # mM Mg2+ [P3P]
P3_DEFAULT_DNTP_CONC = 0.8    # mM total dNTP (4 × 0.2 mM) [P3P][IDT] — BUG FIX v2.1
P3_DEFAULT_DNA_CONC = 200.0   # nM — IDT PrimerQuest default
P3_DEFAULT_TEMP_C = 37.0      # °C for ΔG calculation

P3_TM_FORMULA = 1                          # SantaLucia 1998 [P3P Advanced Settings]
P3_SALT_CORRECTIONS = 1                    # SantaLucia 1998 [P3P Advanced Settings]
P3_THERMODYNAMIC_OLIGO_ALIGNMENT = True    # checkbox ✓ [P3P Advanced Settings]
P3_THERMODYNAMIC_TEMPLATE_ALIGNMENT = False  # checkbox ☐ — VERY SLOW + N/A for 66nt


# ----------------------------------------------------------------
# SECTION K: TAQMAN PROBE (Phase 4)
# ----------------------------------------------------------------

PROBE_TM_MIN_ABOVE_PRIMER = 6.0
PROBE_TM_IDEAL_ABOVE_PRIMER = 8.0
PROBE_TM_MIN = 66.0
PROBE_TM_OPT = 70.0
PROBE_TM_MAX = 74.0
PROBE_TM_TARGET = PROBE_TM_OPT   # alias for test compatibility

PROBE_MIN_LENGTH_SINGLE_Q = 18
PROBE_OPT_LENGTH_SINGLE_Q = 20
PROBE_MAX_LENGTH_SINGLE_Q = 27

PROBE_MIN_LENGTH_MGB = 13
PROBE_OPT_LENGTH_MGB = 16
PROBE_MAX_LENGTH_MGB = 20
PROBE_MGB_TM_BOOST = 15.0

PROBE_GC_MIN = 40.0
PROBE_GC_OPT = 50.0
PROBE_GC_MAX = 60.0

PROBE_NO_G_AT_5PRIME = True         # [IDT-TQ] golden rule
PROBE_G_NOT_EXCEED_C = True         # [patent 10036062]
PROBE_MAX_CONSECUTIVE_G = 3
PROBE_MIN_DIST_FROM_PRIMER = 1      # nt

PROBE_POSITION = "junction"
PROBE_JUNCTION_OVERLAP_MIRNA_SIDE = 7
PROBE_JUNCTION_OVERLAP_STEMLOOP_SIDE = 4

PROBE_MODE_CUSTOM = "custom"
PROBE_MODE_UNIVERSAL = "universal"
PROBE_MODE_DEFAULT = PROBE_MODE_CUSTOM

PROBE_HAIRPIN_DG_MAX = -3.0
PROBE_SELF_DIMER_DG_MAX = -6.0
PROBE_HETERO_DIMER_DG_MAX = -6.0
PROBE_MAX_POLY_X = 5
PROBE_DV_CONC_DEFAULT = 1.5
PROBE_DNA_CONC = 200.0
PROBE_MIN_END_DISTANCE = -1
PROBE_MAX_FAMILY_MISHYB_SCORE = 12.0


# ----------------------------------------------------------------
# SECTION L: BOUND FRACTION (Phase 3)
# ----------------------------------------------------------------

# Round 1 uses RT extension temperature; Round 2 uses qPCR annealing temperature.
# RT extension: 42°C from RT_REACTION_CONDITIONS (SuperScript III, [K11] protocol).
# qPCR Ta: 55°C (= Tm_target − 5°C). Evaluating at exactly Tm=60°C would always
# give ~50% bound fraction by thermodynamic definition of Tm (meaningless score).
# Evaluating at Tm−5°C represents actual primer binding during the annealing step
# and gives ~80–90% fraction for well-designed primers — scientifically actionable.
#
# Thresholds recalibrated for short oligonucleotides (12–24 nt):
#   Round 1 specific region (12–17 nt at 42°C): OPT 80%, floor 60%
#   Round 2 full primer   (~22–24 nt at 55°C):  OPT 80%, floor 60%
# These reflect achievable fractions. Original 97%/90% were set for long (~27 nt)
# symmetric-duplex hybridization assays, not short PCR primer conditions.
BOUND_FRACTION_RT_TEMP        = 42.0  # °C — Round 1: specific region binds cDNA during RT
BOUND_FRACTION_ANNEALING_TEMP = 55.0  # °C — Round 2: full primer binds amplicon at Ta=Tm−5°C
BOUND_FRACTION_MIN = 60.0
BOUND_FRACTION_OPT = 80.0
BOUND_FRACTION_MAX = 100.0


# ----------------------------------------------------------------
# SECTION M: PENALTY WEIGHTS (Primer3Plus Penalties tab)
# ----------------------------------------------------------------

PENALTY_WT_SIZE_LT = 1.0
PENALTY_WT_SIZE_GT = 1.0
PENALTY_WT_TM_LT = 1.0
PENALTY_WT_TM_GT = 1.0
PENALTY_WT_GC_LT = 0.5    # HG Lab departure from P3P default 0.0
PENALTY_WT_GC_GT = 0.5
PENALTY_WT_BOUND_LT = 1.0  # Phase 3 [SL04] SantaLucia & Hicks 2004
PENALTY_WT_BOUND_GT = 1.0
PENALTY_WT_END_STABILITY = 0.5
PENALTY_WT_SELF_COMP = 0.0
PENALTY_WT_END_SELF_COMP = 0.0
PENALTY_WT_HAIRPIN = 0.0
PENALTY_PRIMER_PAIR_WEIGHT = 1.0
PENALTY_HYB_OLIGO_WEIGHT = 0.0   # Phase 2; Phase 4: 1.0

# v2.5: 10-criterion weights
SCORING_WEIGHTS_V2 = {
    "tm_accuracy":          0.20,
    "tm_binding_accuracy":  0.10,
    "gc_content":           0.10,
    "mfe_stemloop":         0.15,
    "hairpin_penalty":      0.10,
    "dimer_penalty":        0.10,
    "end_stability":        0.10,
    "primer_size":          0.05,
    "amplicon_size":        0.05,
    "tm_pair_match":        0.05,
}


# ----------------------------------------------------------------
# SECTION N: ADVANCED SEQ. TAB
# ----------------------------------------------------------------

OUTPUT_BASE_INDEX = 1          # 1-based output [P3P PRIMER_FIRST_BASE_INDEX=1]
PRIMER_AVOID_T_AT_3PRIME = True
PRIMER_T_AT_3PRIME_SEVERITY = "warning"   # warn, not fail


# ----------------------------------------------------------------
# SECTION O: RT BUFFER CONDITIONS (heterodimer Module 1)
# Separate from PCR buffer — Mg2+/dNTP differ between RT and PCR steps.
# [K11] = Kramer 2011, Curr Protoc Mol Biol, Unit 15.10, Table 2
# ----------------------------------------------------------------

P3_RT_MV_CONC   = 75.0   # mM KCl  — RT reaction buffer [K11] Table 2
P3_RT_DV_CONC   = 3.0    # mM MgCl2 — RT reaction buffer [K11] Table 2
P3_RT_DNTP_CONC = 2.0    # mM total dNTP (4 × 0.5 mM per nt) — RT reaction [K11]
P3_RT_DNA_CONC  = 1.0    # nM — optimal RT primer concentration [K11]
# Note: PCR step conditions remain governed by P3_DEFAULT_* / user params


# ----------------------------------------------------------------
# SECTION P: HETERODIMER RISK THRESHOLDS (cross-primer dimers)
# Two-layer classification: HIGH = dG + 3' end complementarity; MODERATE = dG only.
# [IDT] = IDT OligoAnalyzer qPCR guidelines
# ----------------------------------------------------------------

HETERODIMER_HIGH_RISK_DG   = -9.0  # kcal/mol — strong interaction threshold [IDT]
HETERODIMER_LOW_RISK_DG    = -6.0  # kcal/mol — weak interaction threshold [IDT]
HETERODIMER_3PRIME_MIN_BP  = 3     # bp — min consecutive 3' end bp → extension risk


# ----------------------------------------------------------------
# SECTION (27): v2.7 — Literature insights
# ----------------------------------------------------------------

# B: Discrimination [Chen05]
DISCRIMINATION_CROSS_REACTION_MAX = 3.7    # % [C05] Figure 7
DISCRIMINATION_SINGLE_NT_THRESHOLD = 3.7   # %
DISCRIMINATION_MISMATCH_CUTOFF = 3         # mismatches → 100% specific [C05]
PRECURSOR_CT_OFFSET_MIN = 11.0             # cycles [C05] Table 2
PRECURSOR_SIGNAL_CONTRIBUTION = 0.05       # % maximum [C05]
STEMLOOP_VS_LINEAR_SENSITIVITY_FOLD = 100  # × [C05] Figure 9
STEMLOOP_VS_LINEAR_SPECIFICITY_FOLD = 100  # × [C05]
MISMATCH_GT_WOBBLE_PENALTY_WEIGHT = 0.7   # G-T wobble — main cross-reaction source [C05]
MISMATCH_TRUE_PENALTY_WEIGHT = 1.0

# D: qPCR reaction conditions [K11]
RT_REACTION_CONDITIONS = {
    "temperature_profile": [
        {"temp_c": 16, "duration_min": 30, "note": "Low temp annealing"},
        {"temp_c": 42, "duration_min": 30, "note": "Reverse transcription"},
        {"temp_c": 85, "duration_min": 5,  "note": "RT inactivation"},
    ],
    "rt_primer_final_conc_nM": 1.0,
    "source": "Kramer 2011 Table 2",
}

QPCR_CYCLING_CONDITIONS = {
    "initial_denaturation": {"temp_c": 95, "duration_min": 10, "cycles": 1},
    "amplification": {
        "cycles": 40,
        "denaturation": {"temp_c": 95, "duration_sec": 15},
        "annealing_extension": {"temp_c": 60, "duration_min": 1},
    },
    "note": "Standard TaqMan conditions.",
    "source": "Kramer 2011 Step 12",
}

PCR_PRIMER_CONCENTRATIONS = {
    "forward_primer_uM": 1.5,
    "reverse_primer_uM": 0.7,
    "probe_uM": 0.8,
    "source": "Kramer 2011 — optimized from Chen et al. 2005",
}

# E: IDT [IDT-G]
IDT_TYPICAL_MG_CONC = 3.0
IDT_TYPICAL_DNTP_TOTAL = 0.8
IDT_TM_PRIMER_OPTIMAL = 62.0
IDT_TM_PRIMER_RANGE = (60, 64)
IDT_PROBE_TM_ABOVE_PRIMER_MIN = 5.0
IDT_PROBE_TM_ABOVE_PRIMER_MAX = 10.0

# H: SYBR Green risk [V07]
SYBR_GREEN_NON_SPECIFIC_RISK = "HIGH"
SYBR_GREEN_WARNING_MESSAGE = (
    "SYBR Green detection for stem-loop RT-qPCR carries a higher risk of "
    "non-specific amplification. Melting curve analysis is MANDATORY after every "
    "run. Consider switching to TaqMan (hydrolysis probe) for definitive "
    "quantification. Source: Varkonyi-Gasic et al. 2007, Plant Methods."
)
UPL_PROBE_OPTION = True  # Phase 4

# v2.8.3: 12-criterion scoring weights [PAST24][IDT]
SCORING_WEIGHTS_V3 = {
    "tm_accuracy":          0.20,
    "tm_binding_accuracy":  0.10,
    "gc_content":           0.07,   # reduced from 0.09 to make room for gc_clamp
    "gc_skew":              0.02,   # reduced from 0.03
    "gc_clamp":             0.03,   # NEW — 3' anchor quality [IDT PrimerQuest]
    "mfe_stemloop":         0.15,
    "hairpin_penalty":      0.10,
    "dimer_penalty":        0.10,
    "end_stability":        0.10,
    "primer_size":          0.04,
    "amplicon_size":        0.04,
    "tm_pair_match":        0.05,
}
# Total: 0.20+0.10+0.07+0.02+0.03+0.15+0.10+0.10+0.10+0.04+0.04+0.05 = 1.00


# ----------------------------------------------------------------
# SECTION (28): v3.0 — Phase 3 additions
# ----------------------------------------------------------------

# v3.0: 15-criterion scoring weights (Phase 3). [PAST24][IDT][SL04]
# Changes from V3: +bound_fraction_binding (0.05), +bound_fraction_full (0.03),
#   +family_discrimination (0.05); reduced hairpin/dimer/end_stability by 0.02 each,
#   gc_content +0.01, tm_pair_match -0.02, gc_clamp -0.01, primer/amplicon_size -0.02 each,
#   gc_skew -0.01.
# v3.1 weight rebalance:
#   mfe_stemloop 0.15→0.14: body is fixed 44 nt; only 6-nt overhang varies → low inter-candidate variance
#   tm_pair_match 0.03→0.01: reverse is universal fixed (Tm≈60.4°C), redundant with tm_accuracy
#   gc_clamp 0.02→0.04: 3' end GC critical for polymerase extension; prior weight understated impact
#   gc_skew 0.01→0.02: marginal increase; still minor but measurable G-quadruplex risk signal
SCORING_WEIGHTS_V4 = {
    "tm_accuracy":             0.20,  # core — unchanged
    "mfe_stemloop":            0.14,  # -0.01 vs v3.0: body fixed, overhang-only variance
    "tm_binding_accuracy":     0.10,  # core — unchanged
    "hairpin_penalty":         0.08,  # -0.02 vs V3
    "dimer_penalty":           0.08,  # -0.02 vs V3
    "end_stability":           0.08,  # -0.02 vs V3
    "bound_fraction_binding":  0.05,  # NEW — round 1 (cDNA binding) [SL04]
    "bound_fraction_full":     0.03,  # NEW — round 2 (amplicon binding) [SL04]
    "gc_content":              0.08,  # +0.01 vs V3
    "family_discrimination":   0.05,  # NEW — miFam.dat risk [Chen05]
    "tm_pair_match":           0.01,  # -0.02 vs v3.0: reverse is fixed universal primer
    "gc_clamp":                0.04,  # +0.02 vs v3.0: 3' GC critical for extension initiation
    "primer_size":             0.02,  # -0.02 vs V3
    "amplicon_size":           0.02,  # -0.02 vs V3
    "gc_skew":                 0.02,  # +0.01 vs v3.0: G-quadruplex risk signal
}
# Total: 0.20+0.14+0.10+0.08+0.08+0.08+0.05+0.03+0.08+0.05+0.01+0.04+0.02+0.02+0.02 = 1.00
assert abs(sum(SCORING_WEIGHTS_V4.values()) - 1.00) < 0.001

# Family discrimination risk → score mapping [Chen05]
FAMILY_DISCRIMINATION_RISK_SCORE = {
    "SAFE":           100,
    "LOW":             70,
    "HIGH":            30,
    "IDENTICAL":        0,
    "no_family_data": 100,  # score 100 but explanation notes data absence
}

# BLAST off-target parameters [Ye12] Ye et al. 2012 BMC Bioinformatics 13:134
BLAST_WORD_SIZE        = 7       # [Ye12] — vs standard 11
BLAST_EVALUE_CUTOFF    = 30000   # [Ye12] — primer-only case (3000× standard)
BLAST_MAX_TARGET_SEQS  = 50000   # [Ye12] — vs standard 250
BLAST_REWARD           = 1       # [Ye12] — match reward
BLAST_PENALTY          = -1      # [Ye12] — mismatch penalty, ratio 1:1
BLAST_TASK             = "blastn-short"  # for queries <30 nt

# [Ye12] Primer-BLAST default specificity thresholds
PRIMER_BLAST_MIN_TOTAL_MISMATCHES    = 2   # ≥2 total mm required for "specific enough"
PRIMER_BLAST_3PRIME_WINDOW           = 5   # last 5 bases at 3' end
PRIMER_BLAST_3PRIME_MIN_MISMATCHES   = 2   # ≥2 mm in 3' window
PRIMER_BLAST_IGNORE_ABOVE_MISMATCHES = 6   # ≥6 mm → treat target as SAFE
BLAST_MAX_HITS_RETURNED = 200               # cap non-SAFE hits per primer in API response
MIRBASE_HUMAN_PREFIX = "hsa-"              # Homo sapiens species prefix in miRBase FASTA IDs

# Hard-filter gate (PROMPT 3 — A/B toggle)
# Set False to disable hard-filter layer and fall back to soft-scoring only (for comparison).
HARD_FILTER_ENABLED = True

# primer_size scoring mode (PROMPT 6 — A/B toggle)
# "specific" (Busk14): score by specific_length only; tail length does not penalize.
#   score = min(100, (specific_len / FORWARD_SPECIFIC_LEN_REF)^2 * 100)
# "full" (legacy): penalize by |full_primer_len - FORWARD_OPTIMAL_LENGTH| * 10.
PRIMER_SIZE_MODE = "specific"     # [Busk14 I6] DOI 10.1186/1471-2105-15-29

# Reference specific_length for Busk14 primer_size scoring (= FORWARD_SPECIFIC_LENGTH_MAX)
# Score = 100 at 17 nt, decreasing for shorter specific regions (lower specificity).
FORWARD_SPECIFIC_LEN_REF = 17    # nt — max specific_length; score 100 at this length [Busk14]

# Template secondary structure (PROMPT 7 — Fan19 I9)
# Fan 2019 (DOI 10.1080/07391102.2018.1498804): stable hairpin within amplicon
# inhibits PCR (stem ≥20 bp → loss of product). Recommend analyzing ≥60 bp context.
TEMPLATE_FOLD_WINDOW       = 60   # nt — folding window around binding site [Fan19]
TEMPLATE_STRUCTURE_MFE_WARN = -5.0  # kcal/mol — folding stability threshold for warning [Fan19]
TEMPLATE_BINDING_PAIRED_MAX = 3   # bases — max paired bases in binding region (soft limit)

# [Kwok90] Kwok et al. 1990 NAR 18(4):999-1005 — 3'-terminal mismatch categories
# Primer:Template → PCR yield relative to perfect match
KWOK_BLOCKING_PAIRS  = {("A","G"), ("G","A"), ("C","C")}   # ~1% yield
KWOK_REDUCING_PAIRS  = {("A","A")}                          # ~5% yield
# All other pairs → TOLERANT (~100% yield or context-dependent)

# [Kwok90] Position-weighted distance for family cross-reactivity discrimination.
# Weight[i] = contribution of a mismatch at position i from the 3' end (0 = 3'-terminal).
# 3'-proximal mismatches block extension far more than 5'-proximal ones [Kwok90 Fig.3].
# Used in check_family_crossreactivity() to reclassify 1-mismatch siblings whose mismatch
# sits at the 3' end — such siblings are much less likely to be co-amplified.
KWOK_POSITION_WEIGHTS    = [4.0, 2.0, 1.5, 1.0, 1.0, 1.0]  # positions 0–5 from 3' end
KWOK_DIST_DISCRIMINATING = 3.0   # weighted dist ≥ this → 3'-proximal mismatch; classify as LOW

# BLAST cache / infra
BLAST_CACHE_TTL_DAYS       = 30   # days before cache entry expires [spec §9.1]
BLAST_CB_FAILURE_THRESHOLD = 3    # consecutive failures to open circuit [spec §9.2]
BLAST_CB_RECOVERY_TIMEOUT  = 60   # seconds before HALF_OPEN probe [spec §9.2]
BLAST_DB_STALE_WARN_DAYS   = 90   # days before database staleness warning [spec §9.4]


# ----------------------------------------------------------------
# SECTION Q: EDGE-CASE THRESHOLDS (Phase 4)
# [Chen05] mature miRNA canonical ~22 nt; [IDT] GC 40-60%, poly-G ≥4;
# [MIQE09] reporting requirements; [R2] forward specific = 10-12 nt from 5'
# Thresholds marked [convention] are engineering conventions —
# review with lab data if available.
# ----------------------------------------------------------------

MIRNA_LEN_CRITICAL_SHORT = 18    # nt — < this → critical [Chen05][R2]: 6-nt overhang
                                  # + 12 nt specific = 18 nt minimum
MIRNA_LEN_WARN_SHORT     = 20    # nt — < this → warning  [convention]
MIRNA_LEN_INFO_LONG      = 26    # nt — > this → info     [Chen05] ~22 nt typical

MIRNA_GC_LOW             = 30.0  # % — below → warning: low Tm  [IDT][MIQE09]
MIRNA_GC_HIGH            = 70.0  # % — above → warning: secondary structure [IDT]

HOMOPOLYMER_RUN_MIN      = 5     # nt — run ≥ this → warning (any base) [IDT Max Poly-X=5]
POLY_G_RUN_MIN           = 4     # nt — G run ≥ this → warning (G-quadruplex) [IDT]

LOW_COMPLEXITY_TOP2_PCT  = 70.0  # % — top-2 bases ≥ this → low complexity [convention]
                                 # 60% was too sensitive: normal AT-rich miRNAs (e.g. hsa-miR-21-5p
                                 # T:36%+A:27%=63.6%) triggered spuriously. 70% captures genuine
                                 # low-complexity sequences (e.g. AAAAAA... or ATATAT...) only.
LOW_COMPLEXITY_DINUC_REP = 5     # × — dinucleotide repeat ≥ this → low complexity [convention]
