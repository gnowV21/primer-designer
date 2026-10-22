# ================================================================
# algorithm/constants.py  —  v2.7
# ALL scientific constants centralised here.
# Every constant carries a source comment.
# ================================================================


# ----------------------------------------------------------------
# SECTION A: STEM-LOOP RT PRIMER
# [Chen05] Chen et al. 2005 | [K11] Kramer 2011 | [V07] Varkonyi-Gasic 2007
# ----------------------------------------------------------------

# Bump on ANY change that alters design output (primers, scores, warnings),
# so two different results never carry the same version label (audit ENG-01).
#   3.1.0 (2026-09-18) — audit fixes: overhang 5–7 nt, DNA-parameter stem-loop
#   MFE, cycle-1 occupancy at Ta (unscored), renormalised total.
#   3.1.1 (2026-10-22) — isomiRdb 3' isomiR index rebuilt on all 42,494 samples
#   (was 20,635); informational 3' flag levels change, no scoring change.
ALGORITHM_VERSION = "3.1.1"

STEMLOOP_BODY = "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGAC"  # 44 nt [Chen05][K11]
STEMLOOP_BODY_LENGTH = 44

OVERHANG_LENGTH_DEFAULT = 6   # nt — standard, the only length validated in [Chen05]
# Supported range (project decision 2026-09-18): 5–7 nt. 5 and 7 nt are used in
# published assays but not validated in [Chen05], so they always carry a warning.
OVERHANG_LENGTH_MIN = 5
OVERHANG_LENGTH_MAX = 7

MFE_STEMLOOP_MIN = -13.0      # kcal/mol — primer3-py DNA proxy calibrated [R2]
MFE_STEMLOOP_MAX = -10.0      # kcal/mol — primer3-py DNA proxy calibrated [R2]
MFE_STEMLOOP_OPTIMAL = -11.5  # kcal/mol — primer3-py DNA proxy calibrated [R2]

# ViennaRNA DNA-parameter window (audit SCI-04, 2026-09-18). The RT primer is a
# DNA oligo, so it is folded with the DNA energy set (Mathews 2004, 37 °C) —
# the previous RNA (Turner 2004) values (−35/−20/−26) were for the wrong nucleic acid.
# Derived the same way as the old RNA window: the old window was the typical
# full-primer value (RNA −27.5) × 1.273 / 0.727 / 0.945. DNA typical value =
# median over 2000 random 5–7-nt overhangs on STEMLOOP_BODY = −15.3 kcal/mol
# (range −15.6 … −14.9; body alone −14.5) → −19.5 / −11.1 / −14.5.
# Not calibrated on wet-lab data; the body is fixed, so this criterion barely
# varies between candidates of one miRNA (audit SCI-14).
MFE_STEMLOOP_MIN_DNA     = -19.5   # kcal/mol [ViennaRNA DNA Mathews2004, derived as above]
MFE_STEMLOOP_MAX_DNA     = -11.1   # kcal/mol
MFE_STEMLOOP_OPTIMAL_DNA = -14.5   # kcal/mol

# RT primer concentration [K11]: 1 nM optimal (not 50 nM from Chen 2005)

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
FORWARD_SPECIFIC_LENGTH_MAX = 17
FORWARD_SPECIFIC_LENGTHS = [12, 13, 14, 15, 16, 17]

# [V07]: forward primers EXCLUDE the last 6 nt (used as stemloop overhang)
# "Forward primers are specific to the miRNA sequence but EXCLUDE the last six
#  nucleotides at the 3' end of the miRNA" [V07]
FORWARD_EXCLUDES_LAST_NT = 6

# 5' tail — GC-rich per [V07]: "relatively GC-rich"
FORWARD_TAIL_MIN = 3
FORWARD_TAIL_MAX = 12

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
TM_ANNEALING_TEMP_DEFAULT = TM_FORWARD_TARGET  # alias — same optimum; update TM_FORWARD_TARGET only

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

# primer3 thermodynamic-alignment hard limit: at least one strand must be <= 60 bp,
# so amplicon NN ΔH via calc_heterodimer is only available up to this length.
P3_HETERODIMER_MAX_BP = 60           # bp [primer3-py thermoanalysis limit]
# SYBR: product and primer-dimer melt peaks closer than this may be mistaken for
# one another on a single melt curve (P3 discrimination rule). [Lagatie17]
AMPLICON_DIMER_TM_GAP_WARN = 10.0    # °C [Lagatie17] DOI 10.1371/journal.pone.0163435


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

CANDIDATES_TOP_N = 3



# ----------------------------------------------------------------
# SECTION J: PRIMER3-PY PARAMETERS
# ----------------------------------------------------------------

P3_DEFAULT_MV_CONC = 50.0     # mM Na+ [P3P]
P3_DEFAULT_DV_CONC = 1.5      # mM Mg2+ [P3P]
P3_DEFAULT_DNTP_CONC = 0.8    # mM total dNTP (4 × 0.2 mM) [P3P][IDT] — BUG FIX v2.1
P3_DEFAULT_DNA_CONC = 200.0   # nM — IDT PrimerQuest default
P3_DEFAULT_TEMP_C = 37.0      # °C for ΔG calculation

# Monovalent-cation model for the Tm salt correction. Na+ and K+ are both
# monovalent and stabilize the duplex equivalently, so the effective monovalent
# concentration = [Na+] + [K+] + protonated Tris (Tris+). primer3 then applies
# the SantaLucia 1998 monovalent correction + von Ahsen 2001 divalent (Mg2+).
# NOTE: K+ has NO backend default — effective_monovalent_mM() uses params.get(
# "kPlusConc", 0.0), i.e. absent K+ contributes 0 ("do not invent ions"). The
# design form always sends kPlusConc; validator/API callers that omit it stay on
# the Na+-only baseline by design. (Deliberately no P3_DEFAULT_KPLUS_CONC.)
TRIS_PKA_25C          = 8.06  # Tris pKa at 25 °C (Good buffers); Tris+ = protonated fraction
# Assumption (audit ENG-06): the 25 °C pKa is used at every temperature although
# Tris pKa falls as temperature rises (coefficient not verified here). Effect is
# bounded: 10 mM Tris adds at most 10 mM to the ~50–100 mM monovalent total.
TRIS_CONC_DEFAULT_MM  = 10.0  # mM total Tris — standard 1× PCR buffer (10 mM Tris-HCl)

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

PROBE_MIN_LENGTH_SINGLE_Q = 18
PROBE_MAX_LENGTH_SINGLE_Q = 27

PROBE_MIN_LENGTH_MGB = 13
PROBE_MAX_LENGTH_MGB = 20
PROBE_MGB_TM_BOOST = 15.0
# [RESEARCH_INSIGHTS_probe §2.2] +15°C is too imprecise to filter/reject candidates;
# use for display only, flag with warning. Set False = skip Tm filter for MGB.
PROBE_MGB_FILTER_BY_BOOSTED_TM = False

PROBE_MIN_LENGTH_LNA = 13        # [Liu25] LNA probe: shorter + higher Tm per nt
PROBE_MAX_LENGTH_LNA = 18

PROBE_GC_MIN = 40.0
PROBE_GC_MAX = 60.0

PROBE_NO_G_AT_5PRIME = True         # [IDT-TQ] golden rule
PROBE_G_NOT_EXCEED_C = True         # [patent 10036062]
PROBE_MAX_CONSECUTIVE_G = 3
PROBE_MIN_DIST_FROM_PRIMER = 1      # nt

PROBE_JUNCTION_OVERLAP_MIRNA_SIDE = 7
PROBE_JUNCTION_OVERLAP_STEMLOOP_SIDE = 4

PROBE_MODE_CUSTOM = "custom"
PROBE_MODE_UNIVERSAL = "universal"
PROBE_MODE_DEFAULT = PROBE_MODE_CUSTOM

PROBE_HAIRPIN_DG_MAX = -3.0
PROBE_SELF_DIMER_DG_MAX = -6.0
PROBE_HETERO_DIMER_DG_MAX = -6.0
PROBE_DV_CONC_DEFAULT = 1.5
PROBE_DNA_CONC = 200.0


# ----------------------------------------------------------------
# SECTION L: BOUND FRACTION (Phase 3)
# ----------------------------------------------------------------

# Round 1 (specific region vs first-strand cDNA, PCR cycle 1) is evaluated at the
# user's Ta and is informational only — see UNSCORED_CRITERIA_V4 (audit SCI-02).
# Round 2 (scored) uses qPCR Ta: 55°C (= Tm_target − 5°C). Evaluating at exactly Tm=60°C would always
# give ~50% bound fraction by thermodynamic definition of Tm (meaningless score).
# Evaluating at Tm−5°C represents actual primer binding during the annealing step
# and gives ~80–90% fraction for well-designed primers — scientifically actionable.
#
# Thresholds recalibrated for short oligonucleotides (12–24 nt):
#   Round 2 full primer   (~22–24 nt at 55°C):  OPT 80%, floor 60%
# These reflect achievable fractions. Original 97%/90% were set for long (~27 nt)
# symmetric-duplex hybridization assays, not short PCR primer conditions.
# 3' isomiR tiers on isomiRdb's median 3'-isoform read fraction (audit SCI-10).
# Project convention, not a published cut-off: HIGH = the canonical 3' form is a
# minority of the miRNA's molecules, so a stem-loop assay measures a minority.
ISOMIR_3P_FRACTION_HIGH     = 0.50
ISOMIR_3P_FRACTION_MODERATE = 0.20

# Controls & contamination (audit SCI-11) — lab policy, not literature values.
NTC_DELTA_CQ_MIN          = 10   # cycles: NTC must be ≥10 Cq later than the latest sample (HG Lab, 2026-09-19)
ABUNDANCE_PERCENTILE_HIGH = 95   # miRNA in the top 5 % by median isomiRdb RPM → elevated contamination risk

# Amplicon Tm is reported with its Mg2+ sensitivity (audit SCI-07): the same
# product melts ~3 °C apart across this Mg2+ span, and the user's master-mix Mg2+
# is often unknown. Display span only — not a claim about any specific mix.
AMPLICON_TM_MG_SPAN_MM = (1.5, 3.0)

# (Removed BOUND_FRACTION_RT_TEMP = 42 °C — audit SCI-02, 2026-09-18. The forward
#  primer is absent from the RT step; round 1 is PCR cycle 1 at the user's Ta.)
BOUND_FRACTION_ANNEALING_TEMP = 55.0  # °C — Round 2: full primer binds amplicon at Ta=Tm−5°C
BOUND_FRACTION_MIN = 60.0
BOUND_FRACTION_OPT = 80.0


# ----------------------------------------------------------------
# SECTION M: PENALTY WEIGHTS (Primer3Plus Penalties tab)
# ----------------------------------------------------------------


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

# D: qPCR reaction conditions [K11]



# E: IDT [IDT-G]

# H: SYBR Green risk [V07]
SYBR_GREEN_NON_SPECIFIC_RISK = "HIGH"
SYBR_GREEN_WARNING_MESSAGE = (
    "SYBR Green detection for stem-loop RT-qPCR carries a higher risk of "
    "non-specific amplification. Melting curve analysis is MANDATORY after every "
    "run. Consider switching to TaqMan (hydrolysis probe) for definitive "
    "quantification. Source: Varkonyi-Gasic et al. 2007, Plant Methods."
)

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

# Criteria kept in SCORING_WEIGHTS_V4 (weights are locked) but NOT scored.
# The total is renormalised over the criteria actually scored, so the other
# weights keep their relative proportions.
#   bound_fraction_binding — audit SCI-02 (project decision 2026-09-18): the
#   specific region alone binds cDNA only in PCR cycle 1, at Ta (≈2–10 % for
#   12–17 nt at 60 °C). No published threshold exists for that number, so it
#   is reported as information, not scored.
UNSCORED_CRITERIA_V4 = frozenset({"bound_fraction_binding"})

# (Removed FAMILY_DISCRIMINATION_RISK_SCORE — legacy seed-axis mapping. Family
# discrimination is scored on the primer-binding axis via COMBINED_RISK_SCORE
# (Week2 C5); the seed axis is biological context only, never scored.)

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
# Off-target priming requires the primer's 3' terminus to anneal so the polymerase
# can extend. BLAST reports the local alignment only, so the number of primer 3' nt
# left OUTSIDE that alignment (dangling) tells us whether the 3' end is annealed.
BLAST_3PRIME_DANGLE_SAFE = 2   # ≥2 primer 3' nt unaligned → 3' end cannot prime → SAFE
# Even a perfectly-matched 3' anchor cannot seed extension if it is too short: a
# <10 bp duplex has a Tm far below a typical qPCR annealing temperature (≈60°C),
# so it never anneals during cycling. Guards against a short 3'-terminal k-mer
# match to an unrelated miRNA being scored as a critical off-target.
PRIMER_BLAST_MIN_3PRIME_ANCHOR = 10   # nt — shorter 3'-anchored match → SAFE
BLAST_MAX_HITS_RETURNED = 200               # cap non-SAFE hits per primer in API response
MIRBASE_HUMAN_PREFIX = "hsa-"              # Homo sapiens species prefix in miRBase FASTA IDs

# Hard-filter gate (PROMPT 3 — A/B toggle)
# Set False to disable hard-filter layer and fall back to soft-scoring only (for comparison).
HARD_FILTER_ENABLED = True

# [RESEARCH_QUESTIONS_UX A2] DNA:RNA hybrid Tm via Sugimoto 1995 (A/B toggle)
# True  → compute overhang hybrid Tm using algorithm/hybrid_tm.py (pure Python, no dependency)
# False → fall back to "approximate" label only (DNA:DNA primer3 Tm displayed, no hybrid Tm)
# Informational only — NOT used in scoring/hard-filter logic.
USE_HYBRID_TM = True

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

# [Kwok90] Position-weighted mismatch distance, indexed from the PRIMER 3' TERMINUS.
# Weight[i] = contribution of a mismatch i positions away from the primer 3' end
# (0 = the 3'-terminal base pair). A 3'-terminal mismatch blocks extension [Kwok90 Fig.3].
# WARNING: for the stem-loop RT primer the primer 3' terminus pairs with the 5'-MOST
# nucleotide of the miRNA 3' overhang window (the RT primer is the reverse complement).
# Always go through specificity_check.kwok.kwok_weighted_distance() — never index this
# list directly.
KWOK_POSITION_WEIGHTS    = [4.0, 2.0, 1.5, 1.0, 1.0, 1.0]
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


# ----------------------------------------------------------------
# SECTION U: LNA (Phase 8) — informational only, NOT scored
# [McTigue04] McTigue 2004, Biochemistry 43(18):5388-5405
# [Owczarzy11] Owczarzy 2011, Biochemistry 50(43):9352-9367
# ----------------------------------------------------------------

LNA_MAX_SUBSTITUTIONS     = 4       # max LNA positions to suggest per primer
LNA_TARGET_TM_DEFAULT     = 60.0    # °C — default Tm target (mode="tm")
LNA_AVOID_3PRIME_TERMINAL = True    # True → warning (NOT hard-skip) when LNA at 3' terminal
LNA_EXHAUSTIVE_LIMIT      = 5000    # max combinations for exhaustive search; > → greedy
USE_LNA_SUGGESTIONS       = True    # A/B toggle (Phase 8). ON: NN tables are the VERIFIED
                                    # Owczarzy 2011 Table 2 values (McTigue 2004 32NN), and
                                    # tests/test_lna_benchmark.py passes the empirical
                                    # McTigue Table 1 benchmark (ΔTm RMSD 0.78 °C, absolute
                                    # Tm RMSD 1.54 °C, ≤ 2 °C). [A2]

# ----------------------------------------------------------------
# SECTION V: Batch design (Phase 8) — REMOVED
# Batch design was deliberately dropped when the project refocused on
# single primer design (branch feat/design-focus). The A1 batch constants
# (BATCH_ASYNC_THRESHOLD / BATCH_MAX_SIZE / BATCH_JOB_TTL_SEC) were removed
# with it. Restore from commit 269a4c9 if batch is ever reinstated.
# ----------------------------------------------------------------


# ================================================================
# Primer-axis collision analysis (Week 2 P1)
# Specificity of stem-loop RT-qPCR = RT capture (3' overhang) x forward
# discrimination (5' prefix). An off-target co-amplifies only when BOTH axes
# fail. See specificity_check/overhang_collision.py.
# ================================================================
RT_MM_REPORT_MAX        = 2      # report RT-axis colliders with <= 2 mismatches in the window
FWD_MM_REPORT_MAX       = 2      # report FWD-axis colliders with <= 2 mismatches in the prefix
FWD_PREFIX_LEN_FALLBACK = 12     # used when forward specific_length is unavailable (lower bound of [12..17])
COLLISION_MAX_REPORT    = 25     # cap rows returned to the client
# The recommender's RT-overhang ceiling reuses OVERHANG_LENGTH_MAX (=7) from Section A.

# Combined risk keyed by (rt_risk, fwd_risk). CRITICAL only when the RT primer
# fails to discriminate (IDENTICAL/HIGH) AND the forward primer also fails.
COMBINED_RISK_MATRIX = {
    ("IDENTICAL", "IDENTICAL"): "CRITICAL",
    ("IDENTICAL", "HIGH"):      "CRITICAL",
    ("IDENTICAL", "LOW"):       "LOW",
    ("IDENTICAL", "SAFE"):      "SAFE",
    ("HIGH", "IDENTICAL"):      "CRITICAL",
    ("HIGH", "HIGH"):           "CRITICAL",
    ("HIGH", "LOW"):            "LOW",
    ("HIGH", "SAFE"):           "SAFE",
    ("LOW", "IDENTICAL"):       "LOW",
    ("LOW", "HIGH"):            "LOW",
    ("LOW", "LOW"):             "SAFE",
    ("LOW", "SAFE"):            "SAFE",
    ("SAFE", "IDENTICAL"):      "SAFE",
    ("SAFE", "HIGH"):           "SAFE",
    ("SAFE", "LOW"):            "SAFE",
    ("SAFE", "SAFE"):           "SAFE",
}

# Score contribution of the worst combined risk (used by scoring.py, Week 2 C5).
# no_index_data → 100 (criterion cannot contribute; must be stated in the explanation).
COMBINED_RISK_SCORE = {"SAFE": 100, "LOW": 70, "CRITICAL": 0, "no_index_data": 100}

# ---- Short-duplex reporting (Week 2 P4) --------------------------
# NN parameters are calibrated on longer duplexes; below this length the initiation
# term and terminal fraying dominate, so a point Tm is not a defensible display value.
SHORT_DUPLEX_NT_THRESHOLD     = 8     # nt — report dG37 + a Tm band below this, not a point Tm
TM_SHORT_DUPLEX_UNCERTAINTY_C = 5.0   # +/- °C indicative band (conservative; NOT a statistical CI)
