// CriteriaPanel — "How sets are ranked": the Required / Flexible criteria with their
// thresholds (2026-11-22). Opened from a primer-set card. Display only: the thresholds
// are the algorithm 4.0.0 constants (backend constants.py, section TIERED SCORING),
// copied here as text; nothing is computed from them.
import { useEffect, useRef } from 'react';
import { F4_NOTE, GROUP, NCW_CONDITIONS } from '../../../utils/criteriaGroups.js';
import { V4_RULE_LABELS } from '../../../utils/v4Rules.js';

const IDT_TA_URL = 'https://eu.idtdna.com/pages/support/faqs/how-should-i-determine-the-annealing-temperature-for-a-probe-based-qpcr-assay-should-i-select-a-tm-midway-between-my-primer-and-probe-tms-';
const CHEN_URL = 'https://pmc.ncbi.nlm.nih.gov/articles/PMC1292995/';
const PRIMERAST_URL = 'https://doi.org/10.1038/s41598-026-38238-8';
const PRIMER3_URL = 'https://primer3.org/manual.html';

const REQUIRED_ROWS = [
  ['Assay structure', 'Chen 2005: stem-loop RT primer (44-nt body + 3′ overhang, 6 nt; 5 and 7 nt off-label), forward primer = 5′ tail + miRNA 5′ region (12–17 nt), fixed universal reverse primer.', 'built in'],
  ['Forward Tm window', 'Tm min–max under Parameters (default 58–62 °C). Outside the window a candidate is not generated.', 'hard limit'],
  ['S1 BLAST', 'SAFE 5 · MEDIUM, 1 hit 4 · MEDIUM, ≥ 2 hits 3 · HIGH 2 · CRITICAL 1', 'CRITICAL eliminated'],
  ['S2 assay ΔCq', '≥ 10 → 5 · ≥ 7 → 4 · ≥ 4.3 → 3 · ≥ 3.3 → 2 · < 3.3 (CO-AMPLIFIED) → 1', 'CO-AMPLIFIED eliminated'],
  ['S3 Tm margin', 'Tm_on − max Tm_off ≥ 15 °C → 5 · ≥ 10 → 4 · ≥ 7.5 → 3 · ≥ 5 → 2 · < 5 → 1', 'scored'],
];

const COMPOSITION_ROWS = [
  ['F1 GC %', '40–60 % → 5 · ≤ 5 % outside → 4 · ≤ 10 → 3 · ≤ 15 → 2 · further → 1'],
  ['F2 GC clamp', 'G/C in the last 5 nt: 2 → 5 · 3 (last 3 not all G/C) → 4 · 1 → 3 · 4, or last 3 all G/C → 2 · 0 or 5 → 1'],
  ['F4 binding Tm', `${F4_NOTE}. ≥ 45 °C → 5 · ≥ 43 → 4 · ≥ 41 → 3 · ≥ 39 → 2 · < 39 → 1`],
  ['F5 structure', 'Lowest of: hairpin Tm < 30 / 37 / 42 / 47 °C → 5 / 4 / 3 / 2; dimer ΔG (RNAcofold) > −5 / −7 / −9 / −10 kcal/mol → 5 / 4 / 3 / 2; 3′-end dimer Tm < 30 / 37 / 42 / 47 °C → 5 / 4 / 3 / 2'],
  ['F3 specific length', 'Reported, not scored.'],
];

function Table({ head, rows }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full text-xs">
        <thead className="bg-slate-50 text-slate-600">
          <tr>{head.map((h) => <th key={h} className="text-left px-2 py-1.5 font-semibold">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-slate-700">
          {rows.map((r) => (
            <tr key={r[0]}>
              {r.map((c, i) => <td key={i} className={`px-2 py-1.5 align-top ${i === 0 ? 'font-medium whitespace-nowrap' : ''}`}>{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function WhyDefaultTa() {
  return (
    <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2.5 space-y-1.5 text-xs text-slate-700 leading-relaxed"
      data-testid="why-default-ta">
      <p className="font-semibold text-slate-800">Why the default Ta equals the forward-primer Tm</p>
      <ul className="list-disc pl-4 space-y-1">
        <li>
          The default Ta of 60 °C is the two-step cycling of{' '}
          <a className="underline hover:text-teal-800" href={CHEN_URL} target="_blank" rel="noopener noreferrer">Chen et al. 2005</a>{' '}
          (40 × 95 °C 15 s / 60 °C 1 min, annealing and extension combined). The same optimum is the{' '}
          <a className="underline hover:text-teal-800" href={PRIMER3_URL} target="_blank" rel="noopener noreferrer">Primer3</a>{' '}
          default: PRIMER_OPT_TM 60.0 °C (PRIMER_MIN_TM 57.0, PRIMER_MAX_TM 63.0; libprimer3 2.6.1, the release in
          primer3-py 2.0.3). PrimerAST (
          <a className="underline hover:text-teal-800" href={PRIMERAST_URL} target="_blank" rel="noopener noreferrer">Al-Mahrami et al., Sci Rep 2026</a>
          ) designs with 58–62 °C (secondary source).
        </li>
        <li>
          Tm is computed by nearest-neighbour thermodynamics (primer3, SantaLucia 1998) at the salt, Mg²⁺, dNTP and
          primer concentration you enter. Entering a lower concentration than you run gives a Tm below the real one.
        </li>
        <li>The universal reverse primer has Tm 62.93 °C at the default 50 mM monovalent salt.</li>
        <li>
          Common guidance sets Ta 3–5 °C below the lowest primer Tm (
          <a className="underline hover:text-teal-800" href={IDT_TA_URL} target="_blank" rel="noopener noreferrer">IDT</a>).
          At Chen 2005 concentrations the computed Tm rises 2.4–3.4 °C, so Tm(200 nM) ≈ Ta matches Ta ≈ Tm(real) − 3.
        </li>
      </ul>
    </div>
  );
}

export default function CriteriaPanel({ open, onClose }) {
  const closeRef = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    closeRef.current?.focus();
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/40 px-4 py-6 overflow-y-auto"
      onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="criteria-title" data-testid="criteria-panel"
        className="w-full max-w-3xl rounded-2xl bg-white shadow-xl p-4 sm:p-5 space-y-4"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 id="criteria-title" className="text-base font-semibold text-slate-800">How primer sets are ranked</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Two groups. {GROUP.required} comes first; {GROUP.flexible} only reorders sets with the same
              Required specificity, in the order 1 → 2 → 3. Levels L1–L5, L5 best. Most thresholds are this
              tool&apos;s own and not wet-lab calibrated.
            </p>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} aria-label="Close"
            className="shrink-0 text-sm px-2.5 py-1 rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200">✕</button>
        </div>

        <section className="space-y-2" data-testid="criteria-required">
          <h4 className="text-xs font-bold text-slate-500">{GROUP.required}</h4>
          <Table head={['Criterion', 'Rule / levels', 'Effect']} rows={REQUIRED_ROWS} />
          <p className="text-xs text-slate-600">
            Specificity S = S1 + S2 + S3 (max 15; 10 without BLAST) ranks first. When every candidate is eliminated,
            the least bad sets are returned as grade C (specificity fallback).
          </p>
        </section>

        <section className="space-y-3" data-testid="criteria-flexible">
          <h4 className="text-xs font-bold text-slate-500">{GROUP.flexible}</h4>
          <div className="space-y-1">
            <p className="text-xs font-semibold text-slate-700">1. {GROUP.ncw}</p>
            <p className="text-xs text-slate-600">Checked in this order; a set that fails one ranks below, it is not eliminated.</p>
            <ol className="list-decimal pl-5 text-xs text-slate-700 space-y-0.5">
              {NCW_CONDITIONS.map((c) => (
                <li key={c.key}>
                  <span className="font-medium">{c.label}</span>
                  {c.key === 'standard_rules'
                    ? <>: {Object.values(V4_RULE_LABELS).join('; ')}.</>
                    : <> ({c.detail}).</>}
                </li>
              ))}
            </ol>
          </div>
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-slate-700">2. {GROUP.pcr}</p>
            <Table head={['Criterion', 'Rule / levels']} rows={[
              ['P2 |Tm − Ta|', '≤ 1 °C → 5 · ≤ 2 → 4 · ≤ 3 → 3 · ≤ 5 → 2 · > 5 → 1 (forward Tm vs your Ta)'],
              ['ΔTm F–R', 'Not scored. ΔTm F–R ≈ Tm_R − Ta: set by Ta and reaction conditions, the same for every set.'],
              ['Cycle-1 occupancy', 'Not scored. Bound fraction of the miRNA-binding region at Ta.'],
              ['Amplicon Tm', 'Not scored. Predicted melt peak of the product.'],
            ]} />
            <WhyDefaultTa />
          </div>
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-slate-700">3. {GROUP.composition}</p>
            <Table head={['Criterion', 'Rule / levels']} rows={COMPOSITION_ROWS} />
            <p className="text-xs text-slate-600">F = F1 + F2 + F4 + F5 (max 20).</p>
          </div>
        </section>

        <p className="text-xs text-slate-600 border-t border-slate-100 pt-3">
          Still equal: tie-break score (0–100), then |Tm − Ta|, then the sequence. Grade A = S1 ≥ 4, S2 ≥ 3, S3 ≥ 4,
          secondary structure not too strong and cycle-1 binding Tm ≥ 39 °C; B = passed with a weakness, or BLAST not
          run; C = specificity fallback.
        </p>
      </div>
    </div>
  );
}
