# UI / PDF polish review, 2026-11-23

Branch `ui-polish-2026-11`. Source: a strict review of the live site and of the exported
PDF `primer_report_hsa-miR-16-5p_1.pdf`. Presentation only: algorithm 4.0.0, the
ranking key and the primers are unchanged (checks at the end).

Status words: **fixed**, **deferred**, **needs decision** (the fix would change a computed
value or a default, so it is listed instead of done).

## Phase 1: PDF report (`backend/routes/report_pdf.py`, new)

| Item | Status | How |
|---|---|---|
| 1.1 Missing Δ, ², ☐, ⚠, ℹ, ′; ≥ collisions | fixed | DejaVu Sans / Sans Mono embedded (`backend/assets/fonts`, Bitstream Vera licence, copied in `Dockerfile.vercel`). The file now carries only embedded DejaVu fonts (`pdffonts`: `emb yes`). "Critical:" / "Warning:" text labels in dark red / amber; "Pass (Y/N)". |
| 1.2 Overflowing tables, widths, repeated headers, alignment | fixed | Every cell is a Paragraph; every table spans the text width; header repeats on a page break; at least 3 rows on each side of a break; numbers right-aligned; Grade / S / P / F on separate rows; ΔG labels carry kcal/mol; occupancy is "% of primer bound". |
| 1.3 Broken RT primer | fixed | Mono 8.4 pt, no word splitting, sequence column wide enough for 50 nt; a sequence inside a sentence (positive control) goes on its own line. |
| 1.4 Footer, metadata, orphans, spacing | fixed | "<miRNA> · HG Lab stem-loop RT-qPCR primer report · <date>" and "Page x of y"; title and author metadata; each warning kept together; headings never end a page. |
| 1.5 Developer language | fixed | Header scoring line, tie-break in the rank-1 line, "Total primers designed", build-script text, "Phase 3", "byte-identical", `specific_length`, `entr(ies)`, rule codes, P-codes and match casing removed or reworded; hashes moved to a Reproducibility appendix; the NTC pass criterion is written once as a footnote. |
| 1.6 Structure | fixed | Page 1 = ready to order; then comparison, assay design, BLAST, protocol advisor, controls, checklist; appendix with notes (one sentence each), isoforms, methods (the ΔCq model text), reproducibility, references. |
| 1.7 References | fixed | One numbered list, built from what the report cites (advisor sources included). Only identifiers recorded in the repository are used; no titles were invented. |
| 1.8 Conventions | fixed | `utils/report_text.py`: 60.0 °C, 47.6%, −6.10, ′, en dash, Mg²⁺. Numeric CSV columns keep the ASCII minus so spreadsheets parse them. |
| 1.9 Contradictions | see the investigations below | |

## Phase 2: global web rules

| Item | Status | How |
|---|---|---|
| 2.1 Line breaking | fixed | `break-all` removed (13 places); `.seq` / `.seq-block` classes, `SeqBlock` with a copy button, `NoBreak` for API text (miRNA names, sequences, value + unit); `text-wrap: pretty/balance`. |
| 2.2 Overflow and alignment | fixed | Panel headers put the summary on its own line on phones with Show/Hide always visible; short label "Na⁺/K⁺ total" with fixed-height label rows; assay-specificity chart drawn at container width (text 11–12 px); seed-family view opens on the table, map text ≥ 11 px; visualizations drawn at their own pixel size inside a scrolling box. |
| 2.3 Capitalization | fixed | No CSS `uppercase` left (40 places); sentence case for titles and headings; status words sentence case; one vocabulary Pass / Warning / Fail. |
| 2.4 Characters and notation | fixed | No glyphs on buttons; `5′-SEQ-3′`; true minus for ΔG; `Tm_R`, `ΔCq_assay`, `*_END_TH`, rule codes, "Tab A/B" removed; US spelling. |
| 2.5 Colour | fixed | One theme, navy #273E74 (switcher removed, variables kept); status colours green / amber / red, never brand; text ≥ 4.5:1; readable disabled buttons; one "selected" style; footer static at the end of the page. |
| Verification | fixed | `e2e/ui-audit.spec.js`: /home, /design (all groups open), /results (miR-16 design, panels open), /analyze (example run), /history, /benchmark at 1366 and 375 px: no text below 4.5:1, no page overflow, no sequence or miRNA name split, no chart text below 11 px. 12/12 pass. |

## Phase 3: pages

| Page | Status | Notes |
|---|---|---|
| Home | fixed | Stat cards, entry cards and the four "why" cards removed; one paragraph; engine ranges stated (forward 18–27 nt, miRNA-specific region 12–17 nt); cautious, cited precursor sentence; no "HG Lab ↗" button. |
| Designer | fixed | One trigger, every group open once Parameters is open; fewer "?" (helper text instead); one free-Mg²⁺ box; primer-length control removed (form state and request body unchanged); value labels under the slider thumbs; SYBR text once; re-folding checkbox inline; search box with a visible label, keeps what was typed, seed chip without the number, name not in mono; neutral reference descriptions and a reference = target warning; "Reset Tm window" under Required, "Reset reaction conditions" under Flexible. |
| Results | fixed | Plain-English "#1 over #2" (words only); S/P/F legend; closest off-target shown once when identical; flat set card with plain labels and Pass/Warning/Fail, codes in "Criteria detail"; "Standard primer rules: 1 not met (3′ GC clamp missing)"; 3′-end stability labelled −ΔG everywhere; copy buttons next to sequences; duplicate headings removed; ΔCq method behind a "Method" expander; reference to "Assay specificity" fixed; rejection tips match the reasons; visualization: one "simulated" note, gel note no longer repeats the melting note, −dF/dT ticks, "Ladder (bp)", miRNA drawn with U, prose in sans; ThermoTable widths, alignment, legend, "None", GC-clamp label, "isomiR"; version pill moved to the footer; export labels. |
| Analyzer | fixed | Intro rewritten; RT self-dimer is an information note; no `*_END_TH`; same no-point-Tm rule below 8 bp as /results; labelled metrics; "Load example" fills the search box; button style as the Designer. |
| History | fixed | `2026-11-23 08:59`; #1 forward primer; name and sequence in separate elements; no "tiered · v4.0.0" (a record saved before 4.0.0 still says "algorithm v3.8.2", because its score is not a grade). |
| Benchmark | fixed | Renamed "Validation"; empty competitor columns hidden; metrics labelled as an algorithm v3.1 result (not re-run); the 2439/2439 block labelled a consistency check; published-table agreement shown as the independent evidence; readable labels; mean V4 score removed. |
| Mobile 375 px | fixed | Covered by the audit spec; choice cards stack; the header keeps "Primer designer" (on two lines below 460 px so the four tabs fit: checked at every 5 px from 320 to 1024 px). |

## [INVESTIGATE] findings

1. **SantaLucia reference (1.7).** primer3-py `calc_tm` with its defaults is what the engine runs (`thermodynamics.py`): SantaLucia 1998 nearest-neighbour parameters and salt correction, divalent ions by von Ahsen 2001. The PDF now cites SantaLucia 1998 like the web.
2. **BLAST "not assessed" vs "reviewed" (1.9.1).** Algorithm 4.0.0 runs BLAST during every design (`ranking.specificity.blast`, S1). The PDF only looked at the optional "Show all hits" result, and the checklist row was a fixed string. Both now report the design screen (here: Pass, safe, 0 medium hits) or the full check when it was run.
3. **P1 "SYBR + high family cross-reactivity" with family risk low (1.9.2).** `protocol_advisor.py` adds weights 0.5 (SYBR) + 0.5 (family risk HIGH/IDENTICAL); SYBR alone scores 0.5 → "medium". **Needs decision:** requiring both conditions changes `protocol_advice` in the API output. The PDF now says the item matched on SYBR only.
4. **Reference = target (1.9.3).** Warning added on /design and in the PDF; the choice is not changed.
5. **Three reverse-primer Tm values (1.9.4).** 60.4 °C is the hard-coded `UNIVERSAL_REVERSE_TM_PRECALC` (`constants.py:153`), not reproduced by primer3 at any tested condition (primer3 defaults 61.35 °C) and not used by the engine. 62.93 °C is primer3 at the design conditions (50 mM monovalent, 1.5 mM Mg²⁺, 0.8 mM dNTP, 200 nM), from `ranking.pcr.tm_pair.tm_reverse`. The Analyzer's 62.9 °C is the same call at the same default conditions. PDF, CSV and the per-primer table now show the design value. **Needs decision:** removing or recomputing the constant changes the `/api/design` JSON.
6. **"Na+ 50 / K+ 50" (1.9.5).** The PDF prints the request values; the reviewed PDF came from a build that still sent K⁺ 50 mM (before PR #29). The label was wrong: `na_mm` is the Na⁺/K⁺ total, now printed as "Na⁺/K⁺ total 50 mM · extra K⁺ 0 mM". The Analyzer's default line was stale text ("50 mM Na⁺, 50 mM K⁺ … pH 8.4"); it is now built from the defaults (50 mM total, no K⁺, pH not applied). Note: the reviewer's URL (`primer-designer-plum.vercel.app`) is not the project's production domain (`primer-designer-hg-lab-hcmus.vercel.app`).
7. **Mg²⁺ warnings at the defaults.** Defaults 1.5 mM Mg²⁺ and 0.8 mM dNTP give 0.70 mM free Mg²⁺, below the form's 1.0 mM line. The second box fired at the standard dNTP 0.8 mM (its threshold, 0.4 mM, contradicted its own tooltip) and has been folded into the single free-Mg²⁺ box. **Needs decision:** either the 1.0 mM free-Mg²⁺ line or the 1.5 mM default; neither was changed.
8. **Closest off-target, miR-195-5p vs miR-3943 (Results).** The comparison names each set's closest off-target over every miRNA screened (`ranking.specificity.assay_dcq`); the chart lists the miRNAs flagged by the design-level screen (`overhang_collision`, here miR-3943, which shares the RT overhang). Both are at ΔCq 8.3: a tie between two screens. The panel now says so.
9. **Seed family "miR-1 · 1 sibling".** "miR-1" is an auto-generated label: `build_mirbase_data.py` names a seed group by the common prefix of its members (miR-15a, miR-16, miR-195 → "miR-1"); the real miR-1 group was renamed "miR-1_GGAAUGU" by the collision rule. The AGCAGCA group has 5 human siblings (miR-15a, 15b, 195, 424, 497); the API lists only those within 2 mismatches of the RT overhang (here miR-15a-5p). The page now says "Seed group AGCAGCA · 1 close sibling" and explains the list. **Needs decision:** renaming the labels in the data file changes the API `family` field; the grouping itself is correct.
10. **Analyzer hybrid Tm for a 6-nt overhang.** Now hidden below 8 bp, the rule /results uses.

## Changes to computed values

None. Primers, ranking, grades and every number are unchanged. Text-only API changes:
warning messages (plurals, "identical RT primer", "forward-primer specific length",
dimer notes without `*_END_TH`), the family data warning, and the visualization SVGs
(render version 12: miRNA drawn with U, sans prose, −dF/dT ticks).

## Checks

See the PR description for the numbers of this run (backend, crossreactivity, build,
tier order, UI-default check, e2e, PDF pages). Before/after PNGs of the PDF:
`docs/review/ui-polish-2026-11/`.
