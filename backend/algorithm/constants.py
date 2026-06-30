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
UNIVERSAL_REVERSE_CHEN_2005 = "GTGCAGGGTCCGAGGT"     # 16 nt original [C05]
UNIVERSAL_REVERSE_TM_PRECALC = 60.4   # °C — pre-calculated
UNIVERSAL_REVERSE_GC_PRECALC = 65.0   # %


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
TM_BOUND_FRACTION_TARGET = 97.0    # % [SL07] — Phase 3

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

END_DIMER_DG_CRITICAL = -5.0      # kcal/mol — polymerase can extend
END_STABILITY_MAX = 9.0            # kcal/mol [P3P PRIMER_MAX_END_STABILITY]


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

BOUND_FRACTION_ANNEALING_TEMP = 60.0
BOUND_FRACTION_MIN = 90.0
BOUND_FRACTION_OPT = 97.0
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
PENALTY_WT_BOUND_LT = 1.0  # Phase 3 [SL07]
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

# v2.7: 11-criterion scoring weights [PAST24]
SCORING_WEIGHTS_V3 = {
    "tm_accuracy":          0.20,
    "tm_binding_accuracy":  0.10,
    "gc_content":           0.09,   # slightly reduced to make room for gc_skew
    "gc_skew":              0.03,   # NEW — PrimerAST 2026 [PAST24]
    "mfe_stemloop":         0.15,
    "hairpin_penalty":      0.10,
    "dimer_penalty":        0.10,
    "end_stability":        0.10,
    "primer_size":          0.04,
    "amplicon_size":        0.04,
    "tm_pair_match":        0.05,
}
# Total: 0.20+0.10+0.09+0.03+0.15+0.10+0.10+0.10+0.04+0.04+0.05 = 1.00
