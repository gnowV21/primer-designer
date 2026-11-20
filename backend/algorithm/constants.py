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
#   3.1.2 (2026-10-26) — each forward tail pool (len 7–12) seeds its own RNG from
#   (sequence, tail_len, max_pool) instead of sharing one per-design RNG across
#   pools; some sampled tails, hence some forward primers, change. No scoring change.
#   3.2.0 (2026-10-28) — forward selection: score first, diversify after. The old
#   pre-score diversity filter kept ONE candidate per 3' end chosen by |Tm−60| (ties
#   broken by generation order) and dropped 3' ends 1 nt apart, so the 15-criterion
#   score often never saw the best primer and 45 % of miRNAs got a single set. Now the
#   best FORWARD_TAILS_PER_LENGTH tails per 3' end are all scored, and the top
#   CANDIDATES_TOP_N are picked by score with relaxing diversity (3' ends ≥2 nt apart →
#   1 nt apart → same binding region, other tail; each pick labelled). GC clamp: only
#   0 G/C in the last 3 nt is rejected; 1 G/C passes with a warning and the existing
#   gc_clamp criterion (75 vs 100) scores it. Weights unchanged.
#   3.3.0 (2026-10-29) — assay-level specificity: family_discrimination now scores the
#   worst OTHER miRNA on a ΔCq model (ΔCq_RT + ΔCq_FWD, offset-aware, lower bounds of
#   Chen05/Czimmerer13/Schamberger14/Stadhouders10) instead of the RT x FWD risk matrix
#   with fixed-position windows; isomiRs / identical copies reported, not scored.
#   tm_accuracy targets the user's annealing temperature (same as the pool and the
#   tie-break); the overhang fixpoint ranks with the final key. 3' isomiR warning text
#   follows Schamberger14 (±1 nt captured alike). Weights unchanged.
#   3.4.0 (2026-10-29) — the overhang index covers every miRBase 22.1 species (271,
#   48,885 mature; same mature.fa as the BLAST DB, count checked at build time), so
#   the assay-level screen and family_discrimination now run for non-hsa/mmu/rno
#   targets (were neutral no_index_data); a viral target is screened with its
#   host's miRNAs; species prefixes of 3–5 chars (kshv, mdv1) are recognised.
#   3.5.0 (2026-10-30) — isomiR handling reviewed. (a) 3'-end-shift ΔCq values now
#   travel with the measured range and n (0–4 Ct at ±1 nt, n = 2 miRNAs): one study,
#   two sequences differing by up to 4 Ct, so the point value is a lower bound, not a
#   correction factor. (b) Terminology: miRBase entries with the same or an end-shifted
#   sequence are synonyms/renamed entries/paralogues, NOT isomiRs (which have no
#   miRBase entries) — categories renamed same_sequence / shifted_5p / shifted_3p.
#   (c) New qualitative fold-change-bias warning when a large 3'-isoform pool also
#   varies widely between samples [Nejad18]. No scoring change.
#   3.6.0 (2026-11-11) — the full-structure dimer ΔG behind hard-filter rule 1 and
#   the dimer_penalty full-structure check is computed by RNAcofold with DNA
#   parameters (37 °C, ViennaRNA defaults), Kang 2017's own method, instead of
#   primer3 thal at Ta. primer3 was ~5.4 kcal/mol less negative, so the −9 limit
#   was much looser than Kang's (AUDIT REV-19). Primers that now fail are
#   replaced by the next-ranked candidate.
#   3.7.0 (2026-11-11) — hard-filter rule 3 (forward-primer hairpin) rejects on the
#   hairpin's melting temperature, Tm ≥ HAIRPIN_TM_HARD_MAX (47 °C, the Primer3
#   default PRIMER_MAX_HAIRPIN_TH), instead of ΔG at Ta ≤ −6 kcal/mol. The ΔG rule
#   never fired (0 of 9268 candidates for 150 hsa miRNAs; the lowest ΔG at 60 °C was
#   −2.36), while 9.1 % of those candidates had a hairpin Tm > 47 °C (AUDIT REV-20).
#   3.8.0 (2026-11-16) — gc_skew removed from SCORING_WEIGHTS_V4; its 0.02 goes to
#   gc_clamp (0.04 → 0.06). GC skew stood for G-quadruplex risk with unsourced cut-offs
#   (0 / 0.1 / 0.2): among all candidates of the 2253 designable hsa miRNAs one carried a
#   G-quadruplex motif (four G≥3 tracts), never ranked #1 either way, while the skew
#   term pulled #1 away from the Tm target (tm_accuracy < 100 at #1: 233 → 139).
#   gc_clamp is the scored criterion that varies between candidates and has a literature
#   rule (3'-terminal composition, Busk14/IDT): #1 primers with 0 G/C, 3 G/C or CCC in
#   the last 3 nt fall from 85 to 49. #1 changes for 863 / 2253 hsa miRNAs, mostly near-
#   ties (median #1−#2 margin 0.0). GC skew is still reported by /api/analyze (AUDIT REV-22).
#   3.8.1 (2026-11-17) — bound fraction (bound_fraction.py) uses the mass-action
#   occupancy of a two-state duplex with the primer in excess, θ = K·C_P/(1 + K·C_P),
#   instead of 1/(1 + √(1/((C_T/4)·K))), which matches a two-state solution only at
#   50 % (AUDIT REV-24). Display values change; scores, ranking and primers do not:
#   the full-primer criterion is 100 for all 131,039 hsa candidates under both
#   formulas (new θ at 55 °C: 99.66–99.99 %), and the cycle-1 value is unscored
#   (new median 0.31 % vs 2.71 % before; 12 nt 0.08 %, 17 nt 7.8 %).
#   3.8.2 (2026-11-17) — V4 baseline for the 4.0.0 tiered system (SPEC_scoring_tiered
#   QD 14); measured beforehand on 2656 hsa (benchmark/thesis_freeze_impact.json).
#   (a) REV-23: family_discrimination is scored on each candidate's own forward
#   specific length (one check_overhang_collision per length, cached), not once on the
#   winner's length — the label differs between lengths in 78/2253 designs; #1 changes
#   in 13, top 3 in 28; #1 CO-AMPLIFIED 52 → 45. (b) REV-21: hard-filter rule 2 is the
#   Primer3 3'-anchored dimer Tm ≥ 47 °C (END_DIMER_TM_HARD_MAX) instead of ΔG(last
#   8 nt) ≤ −5; neither rejects a candidate the other rules keep (no output change).
#   (c) end_stability is computed as Primer3 defines it (ΔG of the last 5 nt as a
#   perfect duplex, SantaLucia 1998) instead of a hairpin fold of a 5-mer (always 0);
#   still scored, still 100 for every candidate (max possible 6.86 < 9.0) — display
#   values change. (d) miRBase source: results and exports carry the release + sha256
#   of the mature.fa behind the BLAST DB and overhang index; sequences outside it get
#   a `sequence_not_in_mirbase_release` warning; online lookups are labelled and no
#   longer cached.
# 4.0.0 (docs/SPEC_scoring_tiered_4.0.0.md): tiered, specificity-first ranking of the
#   forward candidates (algorithm/tiered_pipeline.py) is the default; V4 stays
#   available (scoringSystem = "v4") and unchanged. Tiered: no GC % / G-C clamp
#   pre-filter and no structural hard filters (scored F1/F2/F5 + soft veto instead);
#   BLAST (batched: one multi-FASTA blastn split over parallel processes + one
#   blastdbcmd per design) scores every candidate S2 does not eliminate; each set
#   lists the V4 rules it breaks (v4_rule_violations).
ALGORITHM_VERSION = "4.0.0"

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
UNIVERSAL_REVERSE_CHEN_2005 = "GTGCAGGGTCCGAGGT"     # 16 nt original [C05]
UNIVERSAL_REVERSE_TM_PRECALC = 60.4   # °C — pre-calculated
UNIVERSAL_REVERSE_GC_PRECALC = 65.0   # %


# ----------------------------------------------------------------
# SECTION C: FORWARD PRIMER DESIGN  [K11][V07][R2]
# ----------------------------------------------------------------

# v2.7 UPDATE: 12–17 nt per Kramer 2011 (not 10–12)
# [K11] p.3: "Take the first 12 to 17 nt of the 5′ end of the mature miRNA"
FORWARD_SPECIFIC_LENGTH_MAX = 17
FORWARD_SPECIFIC_LENGTHS = [12, 13, 14, 15, 16, 17]

# [V07]: forward primers EXCLUDE the last 6 nt (used as stemloop overhang).
# DEFAULT ONLY — forward_primer.py reads params["bindingRegion3prime"] (5-7 nt)
# and falls back to this, so the exclusion always tracks the real overhang.
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
# — preferred spacing between the 3' ends of the returned sets; relaxed to 1 nt, then
#   to tail variants (same 3' end), only when fewer than CANDIDATES_TOP_N would remain.
# Tails kept per specific length (= per 3' end) for scoring, chosen by |Tm_full − Ta|.
# Measured on 165 designable validation miRNAs against scoring EVERY prefiltered
# candidate: K=3 picked a different #1 binding region in 19/165; K=20 matches it to
# within 0.05 score points on average (#1 gain +0.37 vs +0.42) at ~0.45 s per design
# instead of ~3.3 s. (2026-10-28)
FORWARD_TAILS_PER_LENGTH = 20


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

GC_CLAMP_MIN_IN_LAST3 = 2     # [IDT PrimerQuest] 3' GC clamp = 2 — preferred (else warning)
# Hard floor for the forward primer. Its 3' end is fixed by the miRNA sequence, not
# chosen by the tool, so a 1-G/C end is allowed (Busk 2014 accepts it) and left to the
# gc_clamp score criterion (75 vs 100); an all-A/T end is still rejected. (v3.2.0)
GC_CLAMP_HARD_MIN_IN_LAST3 = 1

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

# GC-skew [PAST24] — cut-off without a published source; used only by the legacy V3
# score (use_v4=False). Not scored in V4 since 3.8.0; /api/analyze still reports the value.
GC_SKEW_WARNING_THRESHOLD = 0.2


# ----------------------------------------------------------------
# SECTION F: SECONDARY STRUCTURE THRESHOLDS
# ----------------------------------------------------------------

HAIRPIN_DG_MAX_INTERNAL = -3.0    # kcal/mol [ResearchGate qPCR]
# Hard-filter rule 3 (since 3.7.0): reject a forward primer whose most stable hairpin
# has Tm ≥ 47 °C. Primer3 manual (primer3.org/manual.html), PRIMER_MAX_HAIRPIN_TH,
# default 47.0: "The default value is 10 degrees lower than the default value of
# PRIMER_MIN_TM" (57.0). A fixed value, as Primer3's default is — it does not follow
# the user's Ta. The Tm comes from primer3 calc_hairpin (thermodynamic alignment) at
# the design's salts; a hairpin is unimolecular, so primer concentration does not
# change it. [Untergasser 2012, DOI 10.1093/nar/gks596]
HAIRPIN_TM_HARD_MAX = 47.0        # °C
HAIRPIN_DG_MAX_3PRIME = -2.0      # kcal/mol — 3' end stricter

SELF_DIMER_DG_MAX = -6.0           # kcal/mol [ResearchGate]
SELF_DIMER_DG_3PRIME_MAX = -5.0    # kcal/mol [Premier Biosoft]

HETERO_DIMER_DG_MAX = -6.0
HETERO_DIMER_DG_3PRIME_MAX = -5.0

# Hard-filter rule 2 (3'-end dimer), since algorithm 3.8.2 (AUDIT REV-21): reject a
# forward candidate whose 3'-anchored dimer has Tm ≥ 47 °C — with itself, or with the
# universal reverse primer in either orientation. Primer3 manual
# (primer3.org/manual.html): PRIMER_MAX_SELF_END_TH and PRIMER_PAIR_MAX_COMPL_END_TH,
# default 47.0 ("10 degrees lower than the default value of PRIMER_MIN_TM", 57.0).
# The Tm comes from primer3 calc_end_stability (thermodynamic alignment with the
# 3' end of the first sequence anchored, as Primer3 computes *_END_TH) at the design's
# salts and primer concentration. Before 3.8.2 the rule was ΔG(last 8 nt) ≤ −5
# kcal/mol (Premier Biosoft web page, not a paper; it did not check that the 3'
# terminal base pairs) — it rejected no candidate in 168,929 hsa gate candidates.
END_DIMER_TM_HARD_MAX = 47.0      # °C [P3] PRIMER_MAX_SELF_END_TH / PRIMER_PAIR_MAX_COMPL_END_TH
END_STABILITY_MAX = 9.0            # kcal/mol [P3P PRIMER_MAX_END_STABILITY]

# Full-structure (global) dimer ΔG threshold (Kang 2017 DOI 10.1261/rna.061150.117)
# Distinct from END_DIMER_TM_HARD_MAX (3'-end only).
# Kang 2017 (Methods, checked 2026-11-11): the self-dimer and the forward ×
# universal-reverse hetero-dimer are judged by ΔG (after Shen et al. 2010); above
# "−9.0 ± 1 kcal/mol" no change is needed, below it the 5' tail is swapped for
# another IUPAC alternative or the dimer-forming bases are removed, iterated until
# it passes. Kang redesigns the primer — it does not state a qPCR-inhibition
# outcome. Kang computes ΔG with RNAcofold, DNA parameters (Gruber 2008), and
# confirms borderline cases in OligoAnalyzer 3.1. Since 3.6.0 this tool does the
# same (algorithm/vienna_dna.cofold_dg, 37 °C, 1.021 M Na⁺; no OligoAnalyzer
# step). Before, it used primer3 thal at Ta (60 °C): on the 2253 hsa forward
# primers of 3.5.0 that let through 534 that RNAcofold puts below −9 (median
# shift −5.4 kcal/mol; benchmark/dimer_dg_method_compare.json; AUDIT REV-19).
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
# Fold-change bias warning: a miRNA with a sizeable 3'-isoform pool whose size also
# varies a lot between samples. If a stimulus shifts the isoform mix, stem-loop
# RT-qPCR reads the shift as a change in miRNA level, because capture is
# length-selective [Nejad18]: 3'-variants >23 nt of miR-222-3p fall specifically on
# IFN-β stimulation (confirmed for >40 miRNA families after Salmonella infection),
# "and that this can lead to misinterpretation of results". Qualitative flag only —
# no bias factor is computed, since the capture values themselves rest on n = 2 miRNAs.
ISOMIR_3P_BIAS_MIN_FRACTION = 0.20   # median 3'-isoform share
ISOMIR_3P_BIAS_MIN_IQR      = 0.15   # IQR width of that share across samples

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
# Score bands for the full-primer occupancy — the tool's own (v1.9), no published
# source. With the mass-action formula (3.8.1) every hsa candidate is ≥ 99.6 %, so
# the criterion scores 100 throughout and does not discriminate (as before).
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
# v3.8.0 (algorithm 3.8.0, project decision 2026-11-16 — reopens the locked weights):
#   gc_skew removed (0.02 → gc_clamp, 0.04 → 0.06). See the ALGORITHM_VERSION changelog.
#   Raising a criterion that is equal for every candidate of a design (mfe_stemloop,
#   end_stability, bound_fraction_full, family_discrimination — family_discrimination
#   is scored once, on the winner's specific length) changes no ranking, so the weight
#   went to a criterion that differs between candidates.
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
    "gc_clamp":                0.06,  # +0.02 in 3.8.0 (gc_skew's share): 3'-terminal composition [Busk14][IDT]
    "primer_size":             0.02,  # -0.02 vs V3
    "amplicon_size":           0.02,  # -0.02 vs V3
}
# Total: 0.20+0.14+0.10+0.08+0.08+0.08+0.05+0.03+0.08+0.05+0.01+0.06+0.02+0.02 = 1.00
# 14 criteria; 13 scored (bound_fraction_binding is informational, UNSCORED_CRITERIA_V4).
assert abs(sum(SCORING_WEIGHTS_V4.values()) - 1.00) < 0.001

# Criteria kept in SCORING_WEIGHTS_V4 (weights are locked) but NOT scored.
# The total is renormalised over the criteria actually scored, so the other
# weights keep their relative proportions.
#   bound_fraction_binding — audit SCI-02 (project decision 2026-09-18): the
#   specific region alone binds cDNA only in PCR cycle 1, at Ta (median over the
#   hsa candidates at 60 °C: 0.08 % at 12 nt to 7.8 % at 17 nt, mass action since
#   3.8.1). No published threshold exists for that number, so it is reported as
#   information, not scored.
UNSCORED_CRITERIA_V4 = frozenset({"bound_fraction_binding"})

# (Removed FAMILY_DISCRIMINATION_RISK_SCORE — legacy seed-axis mapping. Family
# discrimination is scored on the assay-level ΔCq model via ASSAY_LABEL_SCORE
# (2026-10-29); the seed axis is biological context only, never scored.)

# BLAST off-target parameters [Ye12] Ye et al. 2012 BMC Bioinformatics 13:134
BLAST_WORD_SIZE        = 7       # [Ye12] — vs standard 11
BLAST_EVALUE_CUTOFF    = 30000   # [Ye12] — primer-only case (3000× standard)
BLAST_MAX_TARGET_SEQS  = 50000   # [Ye12] — vs standard 250
BLAST_REWARD           = 1       # [Ye12] — match reward
BLAST_PENALTY          = -1      # [Ye12] — mismatch penalty, ratio 1:1
BLAST_TASK             = "blastn-short"  # for queries <30 nt
# Batched BLAST (tiered 4.0.0, SPEC QD 24b): the forward candidates of one design
# go to blastn as multi-FASTA, split over this many parallel blastn processes.
# Performance only — blastn scores each query on its own, so the hits are the same
# for any split (benchmark/blast_batch_equivalence.json). hsa-miR-21-5p, 100
# candidates: 1 process 8.5 s, 4 → 3.4 s, 8 → 2.5 s, 12 → 2.5 s.
BLAST_BATCH_PROCESSES  = 8
# Hit classification of a batch (check_offtarget_batch) in a pool of worker processes
# that lives for the whole run (Bước 3, docs/REVIEW_panel_4.0.0.md §9). Performance
# only — every primer is classified on its own by the same _classify_hits and the
# results are merged in input order. Used for batches of ≥ BLAST_CLASSIFY_MIN_PRIMERS
# forward primers; 1 (or env BLAST_CLASSIFY_PROCESSES=1) = in-process.
BLAST_CLASSIFY_PROCESSES   = 12
BLAST_CLASSIFY_MIN_PRIMERS = 16

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
# (Legacy: used only when the on-target duplex Tm cannot be computed — the Tm gate
# below supersedes it whenever the target sequence is known.)

# Duplex-Tm gate (B3). Off-target duplex Tm is compared with the ON-TARGET duplex
# Tm of the same primer (primer3 calc_heterodimer, design salt conditions), NOT
# with Ta: the forward primer's specific region is designed to bind at ~45 °C
# (TM_BINDING_TARGET) and the 5' tail only raises the Tm after cycle 1, so an
# off-target follows the same priming route as the target. The 10 °C gap follows
# Primer3's convention: its thermodynamic limits (*_TH, absolute Tm values) sit
# 10 °C below PRIMER_MIN_TM (57 → 47). Measuring the gap from Tm_on is this tool's
# choice and is not calibrated against wet-lab data.
#   Tm_off <  Tm_on − SAFE_MARGIN               → SAFE
#   Tm_on − SAFE_MARGIN ≤ Tm_off < Tm_on − CRIT → Ye12/Kwok90 rules, capped at MEDIUM
#   Tm_off ≥ Tm_on − CRITICAL_MARGIN            → CRITICAL (HIGH if 3' blocked/unpaired)
BLAST_TM_SAFE_MARGIN     = 10.0   # °C
BLAST_TM_CRITICAL_MARGIN = 5.0    # °C
# Bump whenever classify_hit_risk's rules change — part of the BLAST cache key, so
# cached results computed under older rules are never served.
#   6 = species prefixes of 3–5 chars (kshv, hcmv, mdv1 were read as human); a
#       viral target also screens its host's miRNAs (VIRUS_HOST_SPECIES) (2026-10-29)
#   5 = seed-family hits flagged, no longer folded out of overall_risk; identical
#       hits split into identical / 5' isomiR / 3' isomiR; Tm gate skipped when the
#       primer does not match the target (2026-10-29)
#   4 = trimmed 3'-terminal bases restored from the full subject (true Kwok pair);
#       Tm_off on the primer's register window; Kwok tiers in the top Tm zone
#       (TOLERANT → CRITICAL, G:G/BLOCKING/REDUCING → HIGH); adjacent double
#       terminal mismatch → SAFE unless terminal T (→ MEDIUM) (2026-10-29)
#   3 = self-hit by name + compatible sequence; hits under other names with an
#       identical/compatible sequence folded into identical_sequence
#   2 = duplex-Tm gate (2026-10-28); 1 = 3'-anchoring
BLAST_CLASSIFIER_VERSION = "7"
# Self-hit identification. A hit named like the target is the target only if its
# sequence agrees: identical over the overlap, each end differing by ≤ 2 nt —
# the spread seen between miRBase 22.1 and sequences published against older
# releases (Busk 2014: mmu-miR-138-5p, -31-3p, -194-5p, ssc-miR-7134-3p, -1468).
SELF_MAX_END_SHIFT = 2    # nt
SELF_MIN_OVERLAP   = 15   # nt
BLAST_MAX_HITS_RETURNED = 200               # cap non-SAFE hits per primer in API response
MIRBASE_HUMAN_PREFIX = "hsa-"              # Homo sapiens species prefix in miRBase FASTA IDs
# miRBase species prefixes are 3–5 characters and may contain digits (hsa, kshv,
# hcmv, mdv1, hsv2). A 3-letter-only pattern read 'kshv-miR-K12-1' as human.
MIRBASE_PREFIX_PATTERN = r"[a-z][a-z0-9]{2,4}"

# Off-target screen for a viral miRNA = virus + its natural host present in miRBase
# 22.1: the assay runs on RNA from infected host cells, where host miRNAs dominate.
# Viruses whose host has no miRBase entry (hvsa: squirrel monkey; sfv: African green
# monkey; bpcv1/2: bandicoot; racpv: raccoon) are screened on their own.
VIRUS_HOST_SPECIES = {
    # human
    "ebv": "hsa", "kshv": "hsa", "hcmv": "hsa", "hsv1": "hsa", "hsv2": "hsa",
    "hiv1": "hsa", "hhv6b": "hsa", "bkv": "hsa", "jcv": "hsa",
    # rhesus macaque
    "rlcv": "mml", "rrv": "mml", "sv40": "mml", "hbv": "mml",   # hbv = herpes B virus (macacine HV 1)
    # mouse
    "mcmv": "mmu", "mghv": "mmu",
    # chicken / duck
    "mdv1": "gga", "mdv2": "gga", "hvt": "gga", "iltv": "gga", "dev": "apl",
    # cattle / pig
    "bhv1": "bta", "bhv5": "bta", "blv": "bta", "prv": "ssc",
}
# Species whose miRBase annotation is deep enough that "no annotated off-target" is
# close to "no off-target". Every other species gets an annotation-coverage note.
REFERENCE_ANNOTATED_SPECIES = ("hsa", "mmu")

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
# Assay-level cross-reactivity (ΔCq model, 2026-10-29; replaces the Week 2
# RT x FWD risk matrix). An off-target gives signal only if the RT overhang
# captures it AND the forward primer primes its cDNA; the delays add:
#     ΔCq_assay ≈ ΔCq_RT + ΔCq_FWD,   cross-reactivity ≈ 2^−ΔCq × 100 %.
# Every value is the LOWER bound of the published range (project decision
# 2026-10-29): the model predicts the most cross-reactivity the data allow.
# Literature values were measured with TaqMan probes (Chen05, Schamberger14,
# Stadhouders10); a SYBR assay lacks the probe's extra discrimination, so the
# prediction is an optimistic bound there. See specificity_check/assay_model.py.
# [Chen05] NAR 33:e179 | [Czimmerer13] PLoS One 8:e55168 | [Schamberger14] PLoS One
# 9:e106315 (Fig. 6) | [Stadhouders10] J Mol Diagn 12:109 (PMC2797725) | [Kwok90] NAR
# 18:999 | [Ye12] BMC Bioinformatics 13:134 | [Magee17] Non-Coding RNA 3:18
# ================================================================
FWD_PREFIX_LEN_FALLBACK = 12     # used when forward specific_length is unavailable (lower bound of [12..17])
COLLISION_MAX_REPORT    = 25     # cap rows returned to the client
# The recommender's RT-overhang ceiling reuses OVERHANG_LENGTH_MAX (=7) from Section A.

ASSAY_MAX_END_SHIFT = 2          # nt — registers tried at each end (isomiR range, Schamberger14)

# RT axis (stem-loop overhang, RNA:DNA). Positions counted from the RT primer's 3'
# terminus, which pairs with the 5'-most nt of the miRNA's 3'-terminal window.
# End-shift values rest on ONE study with TWO miRNAs, whose results differ by up to
# 4 Ct — the between-sequence spread is as large as the effect. Report the measured
# RANGE (ASSAY_DCQ_RT_SHIFT_RANGE) wherever a shift value is shown; the point value
# is the lower bound, in line with the rest of this table.
#   miR-877-5p [Schamberger14 Results]: "Assays specific for the 'GACA' and 'GAC' 3'
#     ends detected both 'GACA' and 'GAC' ended RNAs similarly" (±1 nt ≈ 0 Ct),
#     "'GA' ending was detected with ~3 Ct delay" (−2 nt), and the "'GA' specific
#     assay detected all three isoforms similarly" (longer ends ≈ 0 Ct).
#   miR-33b-5p [same section, Fig. 6B]: each assay "detected the corresponding
#     template better than the other isomiR, but the cross-detections were still
#     considerable (2–4 Ct delayed)" — a 1-nt 3' difference, so ±1 nt spans 0–4 Ct.
# The Ct values 36/37/39.6 in the Fig. 6 legend belong to the NON-TARGET CONTROLS
# used as reference samples ("Non-target controls were chosen as reference samples"),
# not to the isomiR reactions — they are not evidence about the assay's LLOQ.
ASSAY_DCQ_RT_3P_LONGER   = 0.0   # off-target 3' end 1–2 nt longer [Schamberger14]
ASSAY_DCQ_RT_3P_SHORT1   = 0.0   # 1 nt shorter [Schamberger14]
ASSAY_DCQ_RT_3P_SHORT2   = 3.0   # 2 nt shorter [Schamberger14]
# Measured range per shift → (low, high, n_mirnas). None = no measurement at all.
ASSAY_DCQ_RT_SHIFT_RANGE = {
    "longer":  (0.0, 4.0, 2),
    "short1":  (0.0, 4.0, 2),
    "short2":  (3.0, 4.0, 1),    # only miR-877-5p; miR-33b was not tested at −2 nt
}
ASSAY_SHIFT_EVIDENCE_NOTE = (
    "3'-end shift values come from one study, two miRNAs (Schamberger & Orbán 2014): "
    "miR-877-5p showed ~0 Ct at ±1 nt and ~3 Ct at −2 nt, miR-33b-5p 2–4 Ct at 1 nt. "
    "The between-sequence spread is as large as the effect, so treat a shift ΔCq as an "
    "order-of-magnitude estimate, not a correction factor."
)
ASSAY_DCQ_RT_WOBBLE      = 4.75  # single rG·dT pair: 3.7 % cross-signal (let-7a assay on let-7c) [Chen05]
ASSAY_DCQ_RT_MM_NEAR     = 7.0   # single other mismatch, positions 1–3: 0.1 % ≈ 10 Cq; range 7–10 → 7 [Chen05]
ASSAY_DCQ_RT_MM_FAR      = 3.5   # single other mismatch, positions 4–6: 6.8–9.0 % cross-signal [Czimmerer13]
ASSAY_DCQ_RT_MULTI       = 8.0   # ≥2 mismatches: ≤0.3 % [Chen05]
ASSAY_RT_NEAR_POSITIONS  = 3

# FWD axis (forward primer on the off-target's cDNA, DNA:DNA). The mismatch only
# costs the first cycles — later products carry the primer sequence — which is the
# setting Stadhouders10 measured (standard Taq qPCR). Pairs are primer–template.
# Lower bounds of the per-group ranges (Stadhouders10, Taq qPCR, 3'-terminal):
ASSAY_DCQ_FWD_TERMINAL = {
    "severe":       8.3,         # A–A, A–G, G–A, G–G, C–C: 8.29–9.09 Ct
    "intermediate": 3.8,         # T–C, C–T, T–T: 3.77–4.75 Ct
    "minor":        1.0,         # A–C, C–A, T–G, G–T: 0.99–1.91 Ct
}
ASSAY_FWD_TERMINAL_GROUP = {
    ("A", "A"): "severe", ("A", "G"): "severe", ("G", "A"): "severe",
    ("G", "G"): "severe", ("C", "C"): "severe",
    ("T", "C"): "intermediate", ("C", "T"): "intermediate", ("T", "T"): "intermediate",
    ("A", "C"): "minor", ("C", "A"): "minor", ("T", "G"): "minor", ("G", "T"): "minor",
}
ASSAY_DCQ_FWD_POS2       = 1.9   # penultimate: mean 1.87 Ct (no range reported) [Stadhouders10]
ASSAY_DCQ_FWD_POS3_5     = 0.5   # positions 3 and 5: means 0.53 / 0.71 Ct; position 4 not tested [Stadhouders10]
ASSAY_FWD_3P_WINDOW      = 5     # nt — beyond this a single mismatch costs ~0 [Kwok90; Ye12]
ASSAY_DCQ_FWD_MULTI_3P   = 8.3   # ≥2 mismatches in the last 5 nt: no amplification with Taq [Stadhouders10];
                                 # except a mismatched terminal T, which still amplifies [Kwok90 abstract]
                                 # → use the terminal pair's value instead.
ASSAY_DCQ_FWD_NO_TEMPLATE = 8.3  # primer 3' end runs past the off-target's end: nothing to extend
# Duplex stability: ΔCq_FWD = max(table, slope × (Tm_on − Tm_off)). Self-derived two-state
# (van 't Hoff, ΔH ≈ −90 kcal/mol) estimate already used for the BLAST Tm gate: 5 °C
# weaker ≈ 10 % bound (3.3 Cq), 10 °C ≈ 1 % (6.6 Cq) → 0.66 Cq/°C. Not from literature.
ASSAY_DCQ_PER_TM_DEGREE  = 0.66

# Labels on ΔCq_assay — thresholds from the thesis proposal's cross-reactivity criteria.
ASSAY_DCQ_COAMPLIFIED_BELOW = 3.3    # > 10 % cross-signal
ASSAY_DCQ_DISCRIMINATED_AT  = 4.3    # < 5 % cross-signal; between the two → PARTIAL

# Score contribution of the worst label among OTHER miRNAs (scoring.py criterion 15).
# isomiRs and identical-sequence copies are reported but not scored: no primer design
# can avoid them (project decision 2026-10-29). no_index_data → 100 (stated in the
# explanation).
ASSAY_LABEL_SCORE = {"DISCRIMINATED": 100, "PARTIAL": 70, "CO-AMPLIFIED": 0, "no_index_data": 100}

# ---- Short-duplex reporting (Week 2 P4) --------------------------
# NN parameters are calibrated on longer duplexes; below this length the initiation
# term and terminal fraying dominate, so a point Tm is not a defensible display value.
SHORT_DUPLEX_NT_THRESHOLD     = 8     # nt — report dG37 + a Tm band below this, not a point Tm
TM_SHORT_DUPLEX_UNCERTAINTY_C = 5.0   # +/- °C indicative band (conservative; NOT a statistical CI)


# ================================================================
# TIERED SCORING (4.0.0) — docs/SPEC_scoring_tiered_4.0.0.md §3
# Thresholds approved 2026-11-17 after the Giai đoạn 1 dry run (SPEC QD 17–23;
# backend/scripts/tiered_scoring_dryrun.py). Pure functions: algorithm/tiered_scoring.py;
# pipeline: algorithm/tiered_pipeline.py.
# Each table lists the lower edge of levels 5, 4, 3, 2 ("higher is better") or the
# upper edge ("lower is better"); anything beyond is level 1.
# "own threshold" = a value of this tool, no published source, not wet-lab calibrated.
# ================================================================
# Ranking system of /api/design: "tiered" (4.0.0 default) or "v4" (weighted sum, kept
# for the thesis comparison; SPEC QD 11). Per request: scoringSystem; per process: the
# SCORING_SYSTEM environment variable.
SCORING_SYSTEM_DEFAULT = "tiered"
SCORING_SYSTEMS = ("tiered", "v4")

# Tier 1 — specificity (max 15)
# S1 BLAST (classifier v7, same species + virus host): SAFE 5, MEDIUM with 1 hit 4,
# MEDIUM with ≥ 2 hits 3, HIGH 2, CRITICAL 1 (eliminated, SPEC QD 4).
TIERED_S1_BY_RISK = {"SAFE": 5, "MEDIUM_1": 4, "MEDIUM_2+": 3, "HIGH": 2, "CRITICAL": 1}
# S2 min ΔCq_assay over same-species miRNAs, on the candidate's own specific length.
TIERED_S2_DCQ = (
    10.0,                          # 5: ≥ 10 Cq ≈ 0.1 %, lowest single-mismatch cross-signal of Chen 2005 (DECISIONS D-2)
    7.0,                           # 4: own threshold
    ASSAY_DCQ_DISCRIMINATED_AT,    # 3: 4.3 — DISCRIMINATED
    ASSAY_DCQ_COAMPLIFIED_BELOW,   # 2: 3.3 — PARTIAL; below → 1 CO-AMPLIFIED (eliminated)
)
# S3 specificity Tm margin = Tm_on − max Tm_off (RT-captured same-species off-targets), °C
TIERED_S3_MARGIN_C = (
    15.0,                          # 5: own threshold
    BLAST_TM_SAFE_MARGIN,          # 4: 10 °C — BLAST SAFE margin
    7.5,                           # 3: own threshold
    BLAST_TM_CRITICAL_MARGIN,      # 2: 5 °C — BLAST CRITICAL margin; below → 1 (not eliminated)
)
TIERED_RT_CAPTURE_BELOW = ASSAY_DCQ_DISCRIMINATED_AT   # ΔCq_RT < 4.3 → the RT primer captures it

# Tier 2 — PCR (max 5 since the Giai đoạn 1 review, 2026-11-17); lower is better, °C.
# P2 |Tm_forward − Ta| is the only scored PCR criterion. Edges no tighter than 1 °C:
# nearest-neighbour Tm predictions carry ~±1–2 °C error, so finer steps would rank noise.
# P1 |Tm_forward − Tm_reverse| is REPORT-ONLY: the universal reverse primer is fixed
# (Tm 62.93 °C at the design defaults), so P1 is a function of Tm_forward alone and
# pulls it towards 62.9 °C while P2 pulls it towards Ta (r = −0.95 over 217,780 hsa
# candidates; P1 level 3 for 88 %). benchmark/tiered_scoring_dryrun.json.
TIERED_P1_TM_PAIR_C = (1.0, TM_PAIR_DIFF_MAX, 3.0, 5.0)   # report only; 4: 2 °C [PAST24]
TIERED_P2_TM_TA_C   = (1.0, 2.0, 3.0, 5.0)                # own thresholds (≥ 1 °C steps)

# Tier 3 — flexible (max 25)
TIERED_F3_LENGTH = {17: 5, 16: 5, 15: 4, 14: 3, 13: 2, 12: 1}   # own threshold (longer = more 3'-mismatch room)
TIERED_F4_BINDING_TM_DEV_C = (2.0, 4.0, 6.0, 8.0)   # |Tm_binding − TM_BINDING_TARGET|, own thresholds
# SPEC QD 29 (behind TIERED_F4_FLOOR until approved on the Giai đoạn 2b numbers):
# TM_BINDING_TARGET (45 °C) is the median Tm of 12–17-nt regions, not a biological
# optimum — at cycle 1 a higher binding Tm only binds better (3.8.1 mass balance at
# 60 °C: 0.08 % at 12 nt, 7.8 % at 17 nt), and mismatch discrimination is measured in
# tier S. So F4 becomes a one-sided floor and F3 (length) leaves the flexible tier
# (report only; F max 20); the detailed score drops primer_size and scores the binding
# Tm one-sided (100 at ≥ 45 °C, linear to 0 at 35 °C).
TIERED_F4_FLOOR = True    # default since QD 35 (approved 2026-11-18)
TIERED_F4_FLOOR_C = (45.0, 43.0, 41.0, 39.0)   # own threshold; floor = thesis cycle-1 hypothesis (let-7a 33.6 vs 46.2 °C)
# QD 33: 0 at 25 °C (≈ lowest binding Tm observed), 100 at ≥ 45 °C, so the detailed score
# still prefers a higher binding Tm among candidates below the floor (all F4 = 1). Own
# threshold. Its weight stays 0.10 after normalisation (raw 0.08 of 0.80).
TIERED_DETAIL_TM_BINDING_FLOOR = ((25.0, 0.0), (45.0, 100.0))
# SPEC QD 30 (behind TIERED_GRADE_BY_TIERS): tiered grade from the tiers, not the
# detailed score. A: no fallback, S1 ≥ 4, S2 ≥ 3, S3 ≥ 4, no veto; B: passed the
# elimination with a weakness (S1 2–3, S2 2, S3 ≤ 3, veto) or without BLAST (no A
# without S1); C: specificity_fallback.
TIERED_GRADE_BY_TIERS = True    # default since QD 35
TIERED_GRADE_A_MIN = {"blast": 4, "assay_dcq": 3, "tm_margin": 4}
# SPEC QD 34: within the same specificity total and veto, a candidate that breaks no V4
# rule (v4_rule_violations empty) ranks first. Giai đoạn 2b: it never lowered S1 or S3 of
# the #1 set. Key: (−S, veto, has_v4_violation, −P, −F, −detailed, |Tm − Ta|, sequence).
TIERED_V4_COMPLIANT_FIRST = True    # default since QD 35
# SPEC QD 36: binding Tm below the floor (F4 = 1, < 39 °C) is a soft veto like a
# structure sub-index at level 1 — below 39 °C the thesis cycle-1 hypothesis expects
# the primer to barely bind (let-7a 33.6 °C): a functional failure, whereas the V4 rule
# broken here is mostly gc_clamp_fail, a soft recommendation. Not eliminated. Key:
# (−S, structure_veto, binding_floor_fail, has_v4_violation, −P, −F, −detailed, |Tm − Ta|, seq).
TIERED_BINDING_FLOOR_VETO = True
# F5 structure = min of three sub-indices; a sub-index of 1 sets structure_veto (SPEC QD 8).
# F5c (3'-end dimer Tm) acts as a VETO in practice, not a graded criterion: level 5 for
# 99.2 % of hsa candidates; the 32 candidates at level 1 all also fail F5a and F5b
# (self-complementary 3' ends such as CTGCAG, GTCGAC). Kept because Primer3 has the rule.
TIERED_F5_HAIRPIN_TM_C   = (30.0, 37.0, 42.0, HAIRPIN_TM_HARD_MAX)    # level 1 at ≥ 47 °C [P3 PRIMER_MAX_HAIRPIN_TH]
TIERED_F5_DIMER_DG       = (-5.0, -7.0, -9.0, -10.0)                  # kcal/mol RNAcofold; ≤ −10 → 1 [Kang17 −9 ± 1]
TIERED_F5_END_DIMER_TM_C = (30.0, 37.0, 42.0, END_DIMER_TM_HARD_MAX)  # level 1 at ≥ 47 °C [P3 *_END_TH]

# Detailed score (0–100), tie-break only (SPEC §3.4). Sub-scores without an existing
# V4 function are piecewise-linear through these (value, sub-score) anchors — own choice,
# chosen so each table edge of levels 2…5 maps to 25/50/75/100 (or 20…100).
# tm_pair (0.15) removed with P1 (same conflict with tm_accuracy); the rest is
# renormalised by its sum (0.85).
TIERED_DETAIL_WEIGHTS = {
    "min_delta_cq": 0.25, "tm_margin": 0.15, "tm_accuracy": 0.15,
    "tm_binding_accuracy": 0.08, "gc_content": 0.05, "gc_clamp": 0.05,
    "primer_size": 0.05, "structure": 0.05, "amplicon_size": 0.02,
}
TIERED_DETAIL_ANCHORS = {
    "min_delta_cq": ((0.0, 0.0), (3.3, 25.0), (4.3, 50.0), (7.0, 75.0), (10.0, 100.0)),   # capped at 10
    "tm_margin":    ((0.0, 0.0), (5.0, 20.0), (7.5, 40.0), (10.0, 60.0), (15.0, 80.0), (20.0, 100.0)),
    "tm_pair":      ((1.0, 100.0), (2.0, 75.0), (3.0, 50.0), (5.0, 25.0), (10.0, 0.0)),
    "hairpin_tm":   ((30.0, 100.0), (37.0, 75.0), (42.0, 50.0), (47.0, 25.0), (60.0, 0.0)),
    "dimer_dg":     ((-5.0, 100.0), (-7.0, 75.0), (-9.0, 50.0), (-10.0, 25.0), (-15.0, 0.0)),
    "end_dimer_tm": ((30.0, 100.0), (37.0, 75.0), (42.0, 50.0), (47.0, 25.0), (60.0, 0.0)),
}
