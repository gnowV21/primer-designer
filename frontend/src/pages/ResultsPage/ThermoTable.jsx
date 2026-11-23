// ThermoTable — two-tab thermodynamics table (Phase 4 §5).
// Tab A: 3-set comparison matrix, best cell highlighted.
// Tab B: per-primer detail for a selected set.

import { useState } from 'react';
import Tooltip from '../../components/ui/Tooltip.jsx';
import LnaPanel from '../../components/LnaPanel/index.jsx';
import useLnaEnabled from '../../hooks/useLnaEnabled.js';
import { hasTiers } from '../../utils/tierRank.js';
import { SeqBlock as SeqBlockLine } from '../../components/ui/Seq.jsx';
import { signed } from '../../utils/format.js';
import { v4RuleLabel } from '../../utils/v4Rules.js';

const NB = '\u00a0';

// ── Helpers ────────────────────────────────────────────────────────

function fmt(v, digits = 1) {
  if (v === undefined || v === null || v === '') return '—';
  if (typeof v === 'boolean') return v ? 'Yes' : 'No';
  if (typeof v === 'number') return signed(v.toFixed(digits));
  return String(v);
}

// Small occupancies (cycle 1 is often < 1 %) need more than one decimal.
function fmtPct(v) {
  if (v === undefined || v === null) return '—';
  const n = Number(v);
  if (n < 0.01) return '< 0.01%';
  return `${n < 1 ? n.toFixed(2) : n.toFixed(1)}%`;
}

function fmtDg(v) {
  if (v === undefined || v === null) return '—';
  return signed(Number(v).toFixed(2));
}
const deg = (v, d = 1) => (v === undefined || v === null ? '—' : `${fmt(v, d)}${NB}°C`);

// Full-structure dimer ΔG behind hard-filter rule 1: RNAcofold, DNA parameters,
// 37 °C (Kang 2017), worst of forward self-dimer and forward × universal reverse.
// The other ΔG rows are primer3 at the annealing temperature — a different scale.
function cofoldDimerDg(s) {
  const a = get(s, 'structure_checks', 'self_dimer', 'dg_cofold');
  const b = get(s, 'structure_checks', 'hetero_dimer', 'dg_cofold');
  if (a == null || b == null) return undefined;
  return Math.min(a, b);
}

function get(obj, ...keys) {
  let cur = obj;
  for (const k of keys) {
    if (cur == null) return undefined;
    cur = cur[k];
  }
  return cur;
}

// Determine which column index (0/1/2) has the "best" value for a row.
// direction: 'max' means higher = better, 'min' means more-negative = better (ΔG rows), 'min_abs' = closer to 0
function bestIndex(sets, extractor, direction) {
  const vals = sets.map((s) => {
    const v = extractor(s);
    return typeof v === 'number' ? v : null;
  });
  if (vals.every((v) => v === null)) return -1;
  // Every set equal on this row (common for the tiers): nothing to highlight.
  const present = vals.filter((v) => v !== null);
  if (present.length > 1 && present.every((v) => v === present[0])) return -1;
  let best = -1, bestVal = null;
  for (let i = 0; i < vals.length; i++) {
    if (vals[i] === null) continue;
    if (bestVal === null) { best = i; bestVal = vals[i]; continue; }
    if (direction === 'max' && vals[i] > bestVal) { best = i; bestVal = vals[i]; }
    else if (direction === 'min' && vals[i] < bestVal) { best = i; bestVal = vals[i]; }
    else if (direction === 'min_abs' && Math.abs(vals[i]) < Math.abs(bestVal)) { best = i; bestVal = vals[i]; }
  }
  return best;
}

// ── Tab A — Comparison matrix ──────────────────────────────────────

const ROWS = [
  {
    label: 'Total score',
    extract: (s) => s?.total_score,
    format: (s) => s?.total_score !== undefined
      ? `${fmt(s.total_score)} ${s.grade ? `(${s.grade})` : ''}`
      : '—',
    best: 'max',
  },
  {
    label: 'Forward Tm, full primer',
    extract: (s) => s?.tm_full,
    format: (s) => deg(s?.tm_full),
    best: 'max',
  },
  {
    label: 'Forward Tm, binding region',
    extract: (s) => s?.tm_binding,
    format: (s) => deg(s?.tm_binding),
    best: 'max',
  },
  {
    label: 'GC content (forward)',
    extract: (s) => s?.gc_percent,
    format: (s) => `${fmt(s?.gc_percent)}%`,
    best: 'max',
  },
  {
    label: 'Amplicon',
    extract: (s) => s?.amplicon_size,
    format: (s) => `${fmt(s?.amplicon_size, 0)}${NB}bp`,
    best: 'min_abs', // closer to default is best
  },
  {
    label: 'Hairpin ΔG (kcal/mol)',
    extract: (s) => get(s, 'structure_checks', 'hairpin', 'dg'),
    format: (s) => fmtDg(get(s, 'structure_checks', 'hairpin', 'dg')),
    best: 'min_abs',
  },
  {
    label: 'Self-dimer ΔG (kcal/mol)',
    extract: (s) => get(s, 'structure_checks', 'self_dimer', 'dg_overall'),
    format: (s) => fmtDg(get(s, 'structure_checks', 'self_dimer', 'dg_overall')),
    best: 'min_abs',
  },
  {
    label: `Dimer ΔG, RNAcofold at 37${NB}°C (kcal/mol)`,
    extract: (s) => cofoldDimerDg(s),
    format: (s) => fmtDg(cofoldDimerDg(s)),
    best: 'min_abs',
  },
  {
    label: 'Forward × reverse dimer ΔG (kcal/mol)',
    extract: (s) => get(s, 'heterodimer_checks', 'heterodimer_fwd_reverse', 'dg'),
    format: (s) => fmtDg(get(s, 'heterodimer_checks', 'heterodimer_fwd_reverse', 'dg')),
    best: 'min_abs',
  },
  {
    label: 'Forward × RT dimer ΔG (kcal/mol)',
    extract: (s) => get(s, 'heterodimer_checks', 'heterodimer_fwd_stemloop', 'dg'),
    format: (s) => fmtDg(get(s, 'heterodimer_checks', 'heterodimer_fwd_stemloop', 'dg')),
    best: 'min_abs',
  },
  {
    // Primer3 reports 3′-end stability as a positive −ΔG of the last 5 nt.
    label: '3′-end stability, −ΔG (kcal/mol)',
    extract: (s) => get(s, 'structure_checks', 'end_stability', 'stability_kcal_mol'),
    format: (s) => {
      const v = get(s, 'structure_checks', 'end_stability', 'stability_kcal_mol');
      return v !== undefined ? fmtDg(v) : '—';
    },
    best: 'min_abs',
  },
  {
    // Informational (not scored, audit SCI-02): % of first-strand cDNA bound by
    // the specific region in PCR cycle 1 at Ta (mass action, AUDIT REV-24).
    label: 'Cycle-1 occupancy at Ta (% of primer bound)',
    extract: (s) => get(s, 'scores', 'bound_fraction_binding_pct'),
    format: (s) => {
      const v = get(s, 'scores', 'bound_fraction_binding_pct');
      return v !== undefined ? fmtPct(v) : '—';
    },
    best: 'max',
  },
  {
    label: 'GC clamp score (0–100)',
    extract: (s) => get(s, 'scores', 'gc_clamp'),
    format: (s) => {
      const v = get(s, 'scores', 'gc_clamp');
      return v !== undefined ? fmt(v, 0) : '—';
    },
    best: 'max',
  },
  {
    label: 'isomiR co-amplification risk',
    extract: () => null, // not numeric
    format: (s) => {
      const risk = get(s, 'isomir_flag', 'isomir_discrimination_risk');
      return risk === true ? 'Yes' : risk === false ? 'None' : '—';
    },
    best: null,
  },
];

// Tiered sets (4.0.0): the V4 "Total score" row is replaced by the criteria groups, in
// ranking-key order (Required, then Flexible 1 → 2 → 3; utils/criteriaGroups.js).
// total_score is only the final tie-break there.
const yesNo = (v) => (v ? 'Yes' : 'No');
const TIER_ROWS = [
  { label: 'Grade', extract: () => null, format: (s) => s.grade ?? '—', best: null },
  { label: 'Specificity (S)', extract: (s) => s.ranking.specificity.total,
    format: (s) => `${s.ranking.specificity.total}/${s.ranking.specificity.max}`, best: 'max' },
  { label: 'Secondary structure too strong', extract: () => null, format: (s) => yesNo(s.ranking.structure_veto), best: null },
  { label: `Binding-region Tm below 39${NB}°C`, extract: () => null, format: (s) => yesNo(s.ranking.binding_floor_fail), best: null },
  { label: 'Standard primer rules not met', extract: () => null,
    format: (s) => (s.v4_rule_violations || []).map(v4RuleLabel).join(', ') || 'None', best: null },
  { label: 'PCR (P)', extract: (s) => s.ranking.pcr.total,
    format: (s) => `${s.ranking.pcr.total}/${s.ranking.pcr.max}`, best: 'max' },
  { label: 'Composition and structure (F)', extract: (s) => s.ranking.flexible.total,
    format: (s) => `${s.ranking.flexible.total}/${s.ranking.flexible.max}`, best: 'max' },
  { label: 'Tie-break score', extract: (s) => s.ranking.detailed_score,
    format: (s) => fmt(s.ranking.detailed_score), best: 'max' },
];

function comparisonRows(top3) {
  return top3?.length && top3.every(hasTiers) ? [...TIER_ROWS, ...ROWS.slice(1)] : ROWS;
}

function TabA({ top3 }) {
  if (!top3?.length) return null;
  const rows = comparisonRows(top3);

  return (
    <div className="space-y-2">
    <div className="overflow-x-auto">
      <table className="w-full min-w-[30rem] text-xs border-collapse table-fixed">
        <colgroup>
          <col className="w-[40%]" />
          {top3.map((s) => <col key={s.rank} style={{ width: `${60 / top3.length}%` }} />)}
        </colgroup>
        <thead>
          <tr className="bg-teal-600 text-white">
            <th className="text-left px-3 py-2 font-semibold rounded-tl-lg">Criterion</th>
            {top3.map((s) => (
              <th key={s.rank} className="text-right px-3 py-2 font-semibold">
                Rank {s.rank}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => {
            const bIdx = row.best ? bestIndex(top3, row.extract, row.best) : -1;
            return (
              <tr
                key={row.label}
                className={ri % 2 === 0 ? 'bg-white' : 'bg-slate-50'}
              >
                <td className="px-3 py-1.5 font-medium text-slate-700 border-r border-slate-100">
                  {row.label}
                </td>
                {top3.map((s, si) => (
                  <td
                    key={s.rank}
                    className={`px-3 py-1.5 text-right tabular-nums ${si === bIdx ? 'bg-teal-50 text-teal-800 font-semibold' : 'text-slate-800'}`}
                  >
                    {row.format(s)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
    <p className="text-xs text-slate-700">
      <span className="inline-block w-3 h-3 align-middle rounded-sm bg-teal-50 border border-teal-200 mr-1" aria-hidden />
      Shaded: the best value of the row (no shading when the sets are equal).
    </p>
    </div>
  );
}

// ── Tab B — Per-primer detail ──────────────────────────────────────

function SeqBlock({ label, sequence, tag }) {
  return (
    <div className="rounded-lg border border-slate-200 px-3 py-2.5 space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-700">{label}</span>
        {tag && (
          <span className="text-xs bg-teal-50 text-teal-700 border border-teal-200 rounded-full px-2 py-0.5">
            {tag}
          </span>
        )}
      </div>
      <SeqBlockLine sequence={sequence} />
    </div>
  );
}

function PropRow({ label, value }) {
  if (value === undefined || value === null || value === '—') return null;
  return (
    <div className="flex justify-between text-xs py-0.5">
      <span className="text-slate-700">{label}</span>
      <span className="text-slate-900 tabular-nums font-medium text-right">{value}</span>
    </div>
  );
}

function TabB({ top3, stemloopRt, universalReverse, params }) {
  const [selRank, setSelRank] = useState(1);
  const [showLna, setShowLna] = useState(false);
  const lnaEnabled = useLnaEnabled();
  const set = top3?.find((s) => s.rank === selRank) ?? top3?.[0];

  if (!set) return null;

  // LNA suggester operates on the forward primer (DNA). Ion conditions and the
  // target Tm come from the form params the design was run with.
  const ionParams = params?.thermodynamic ?? {};
  const targetTm  = params?.thermodynamic?.tmMax ?? 60;

  return (
    <div className="space-y-4">
      {/* Rank selector */}
      <div className="flex gap-2">
        {(top3 ?? []).map((s) => (
          <button
            key={s.rank}
            onClick={() => setSelRank(s.rank)}
            type="button"
            aria-pressed={s.rank === selRank}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${s.rank === selRank
                ? 'bg-teal-600 text-white shadow-sm'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
          >
            Rank {s.rank}
            {s.grade && <span className="ml-1">· {s.grade}</span>}
          </button>
        ))}
      </div>

      {/* Forward primer */}
      <div className="space-y-2">
        <p className="text-xs font-bold text-slate-800">Forward primer</p>
        <SeqBlock label="Sequence" sequence={set.sequence} tag={`${set.length}${NB}nt`} />
        <div className="grid grid-cols-2 gap-x-6 px-1">
          <PropRow label="Tm, full primer" value={set.tm_full !== undefined ? deg(set.tm_full) : undefined} />
          <PropRow label="Tm, binding region" value={set.tm_binding !== undefined ? deg(set.tm_binding) : undefined} />
          <PropRow label="GC content" value={set.gc_percent !== undefined ? `${fmt(set.gc_percent)}%` : undefined} />
          <PropRow label="Amplicon" value={set.amplicon_size !== undefined ? `${fmt(set.amplicon_size, 0)}${NB}bp` : undefined} />
          <PropRow label="Hairpin ΔG (kcal/mol)" value={fmtDg(get(set, 'structure_checks', 'hairpin', 'dg'))} />
          <PropRow label="Self-dimer ΔG (kcal/mol)" value={fmtDg(get(set, 'structure_checks', 'self_dimer', 'dg_overall'))} />
          <PropRow label={`Dimer ΔG, RNAcofold at 37${NB}°C (kcal/mol)`} value={fmtDg(cofoldDimerDg(set))} />
          <PropRow label="3′-end stability, −ΔG (kcal/mol)" value={fmtDg(get(set, 'structure_checks', 'end_stability', 'stability_kcal_mol'))} />
          <PropRow label="miRNA-specific region" value={set.specific_length !== undefined ? `${set.specific_length}${NB}nt` : undefined} />
          <PropRow label="Binding position on the miRNA (nt)" value={
            set.binding_start_1based !== undefined
              ? `${set.binding_start_1based}–${set.binding_end_1based}`
              : undefined
          } />
          {/* Cycle-1 occupancy: informational, evaluated at the user's Ta (audit SCI-02) */}
          <PropRow
            label="Cycle-1 occupancy at Ta (not scored)"
            value={set.scores?.bound_fraction_binding_pct !== undefined
              ? fmtPct(set.scores.bound_fraction_binding_pct)
              : undefined}
          />
          <PropRow
            label={`Bound fraction, full primer at 55${NB}°C`}
            value={set.scores?.bound_fraction_full_pct !== undefined
              ? `${fmt(set.scores.bound_fraction_full_pct)}%`
              : undefined}
          />
          {hasTiers(set) ? (
            <>
              <PropRow label="Grade" value={set.grade} />
              <PropRow label="Specificity · PCR · composition and structure"
                value={`${set.ranking.specificity.total}/${set.ranking.specificity.max} · ${set.ranking.pcr.total}/${set.ranking.pcr.max} · ${set.ranking.flexible.total}/${set.ranking.flexible.max}`} />
              <PropRow label="Tie-break score" value={fmt(set.ranking.detailed_score)} />
            </>
          ) : (
            <PropRow label="Total score" value={set.total_score !== undefined ? fmt(set.total_score) : undefined} />
          )}
        </div>

        {/* LNA Tm suggester (informational only) — on-demand for the forward primer.
            Gated: hidden while the backend LNA NN tables are unverified. */}
        {lnaEnabled && (
          <div className="pt-1">
            {!showLna ? (
              <button
                type="button"
                onClick={() => setShowLna(true)}
                className="text-xs font-medium text-amber-800 border border-amber-200 bg-amber-50 rounded-lg px-3 py-1.5 hover:bg-amber-100 transition-colors"
              >
                Suggest LNA (Tm)
              </button>
            ) : (
              <LnaPanel
                key={selRank}
                sequence={set.sequence}
                role="forward"
                params={ionParams}
                mode="tm"
                targetTm={targetTm}
                onClose={() => setShowLna(false)}
              />
            )}
          </div>
        )}
      </div>

      {/* RT stem-loop primer */}
      {stemloopRt && (
        <div className="space-y-2">
          <p className="text-xs font-bold text-slate-800">RT stem-loop primer (shared)</p>
          <SeqBlock label="Sequence" sequence={stemloopRt.sequence} tag={`${stemloopRt.length}${NB}nt`} />
          <div className="grid grid-cols-2 gap-x-6 px-1">
            {/* [RESEARCH_QUESTIONS_UX A2] Full-primer Tm: DNA:DNA NN (primer3, indicative).
                Overhang hybrid Tm: DNA:RNA NN (Sugimoto 1995), if USE_HYBRID_TM enabled. */}
            <RtTmRow stemloopRt={stemloopRt} />
            <PropRow label="GC content" value={stemloopRt.gc_percent !== undefined ? `${fmt(stemloopRt.gc_percent)}%` : undefined} />
            <PropRow label="MFE (kcal/mol)" value={stemloopRt.mfe !== undefined ? fmt(stemloopRt.mfe, 2) : undefined} />
            <PropRow label="MFE method" value={stemloopRt.mfe_method} />
          </div>
          {/* 3′ isomiR share from isomiRdb (audit SCI-10) — warning when the canonical
              3′ form is a minority, plain note otherwise. */}
          {stemloopRt.three_prime_isomir?.three_prime_isomir_risk ? (
            <p className="text-xs text-amber-800 px-1 leading-relaxed">
              3′ isomiRs: {stemloopRt.three_prime_isomir.warning}{' '}
              <span className="text-slate-700">Source: {stemloopRt.three_prime_isomir.source}.</span>
            </p>
          ) : stemloopRt.three_prime_isomir?.summary && (
            <p className="text-xs text-slate-700 px-1 leading-relaxed">
              3′ isomiRs: {stemloopRt.three_prime_isomir.summary} Source: {stemloopRt.three_prime_isomir.source}.
            </p>
          )}
          {stemloopRt.three_prime_isomir?.fold_change_bias_risk && (
            <p className="text-xs text-amber-800 px-1 leading-relaxed">
              {stemloopRt.three_prime_isomir.fold_change_bias_warning}
            </p>
          )}
        </div>
      )}

      {/* Universal reverse */}
      {universalReverse && (
        <div className="space-y-2">
          <p className="text-xs font-bold text-slate-800">Universal reverse primer (fixed)</p>
          <SeqBlock label="Sequence" sequence={universalReverse.sequence} tag={`${universalReverse.length}${NB}nt`} />
          <div className="grid grid-cols-2 gap-x-6 px-1">
            {/* Tm at the design conditions, as in "Shared by all sets". Since 2026-11-23 the
                API's universal_reverse.tm is the same computed value; records saved earlier
                carry the old fixed 60.4 °C there, so the ranking value comes first. */}
            <PropRow label="Tm at the design conditions" value={deg(set?.ranking?.pcr?.tm_pair?.tm_reverse ?? universalReverse.tm)} />
            <PropRow label="GC content" value={universalReverse.gc_percent !== undefined ? `${fmt(universalReverse.gc_percent)}%` : undefined} />
            <PropRow label="Hairpin ΔG (kcal/mol)" value={fmtDg(get(universalReverse, 'self_structure_check', 'hairpin_dg'))} />
            <PropRow label="Self-dimer ΔG (kcal/mol)" value={fmtDg(get(universalReverse, 'self_structure_check', 'self_dimer_dg'))} />
          </div>
        </div>
      )}
    </div>
  );
}

// ── RT primer Tm rows (Tab B) ──────────────────────────────────────
// [RESEARCH_QUESTIONS_UX A2] Shows both full-primer Tm (DNA:DNA NN, indicative)
// and overhang hybrid Tm (DNA:RNA NN, Sugimoto 1995) when USE_HYBRID_TM is enabled.

function RtTmRow({ stemloopRt }) {
  const hasHybrid = stemloopRt?.tm_hybrid_c != null;
  const caveats   = stemloopRt?.tm_hybrid?.caveats ?? [];

  const fullTmTooltip =
    'Full-primer Tm computed by primer3 using DNA:DNA nearest-neighbor (SantaLucia 1998). ' +
    'The RT primer is DNA; this Tm describes the full 50-nt oligo as a standalone molecule. ' +
    'NOT the hybridization Tm with the miRNA target. Not used in scoring.';

  const hybridTooltip = hasHybrid
    ? 'Overhang hybrid Tm: Tm of the 3\' overhang (DNA) annealing to the miRNA (RNA). ' +
      'Computed via Sugimoto 1995 DNA:RNA nearest-neighbor (Biochemistry 34:11211). ' +
      'Informational only — NOT scored. ' +
      (caveats.length > 0 ? 'Caveats: ' + caveats.join('; ') + '.' : '')
    : '';

  return (
    <>
      <div className="flex justify-between text-xs py-0.5">
        <span className="text-slate-700 flex items-center gap-1">
          Tm, full primer (DNA:DNA)
          <Tooltip text={fullTmTooltip} />
        </span>
        <span className="text-slate-700 tabular-nums font-medium">
          {stemloopRt.tm_full !== undefined ? deg(stemloopRt.tm_full) : '—'}
          <span className="text-slate-600 ml-1 text-xs font-normal">indicative</span>
        </span>
      </div>
      {hasHybrid && (
        <div className="flex justify-between text-xs py-0.5">
          <span className="text-slate-700 flex items-center gap-1">
            Overhang Tm (DNA:RNA, Sugimoto 1995)
            <Tooltip text={hybridTooltip} />
          </span>
          <span className="text-slate-700 tabular-nums font-medium">
            {deg(stemloopRt.tm_hybrid_c)}
            <span className="text-slate-600 ml-1 text-xs font-normal">modeled</span>
          </span>
        </div>
      )}
      {/* Week2 P4: <8 bp duplex → report ΔG37 + a band, never a point Tm. */}
      {!hasHybrid && stemloopRt?.dg37_kcal_mol != null && (
        <div className="flex justify-between text-xs py-0.5">
          <span className="text-slate-700 flex items-center gap-1">
            Overhang ΔG at 37{NB}°C (DNA:RNA)
            <Tooltip text={hybridTooltip || (stemloopRt?.tm_note ?? '')} />
          </span>
          <span className="tabular-nums text-right">
            <span className="text-slate-900 font-medium whitespace-nowrap">{fmt(stemloopRt.dg37_kcal_mol, 2)}{NB}kcal/mol</span>
            {Array.isArray(stemloopRt.tm_hybrid_band_c) && (
              <span className="text-slate-600 ml-1 text-xs font-normal">
                Tm ≈ {stemloopRt.tm_hybrid_band_c[0]}–{stemloopRt.tm_hybrid_band_c[1]}{NB}°C (no point value below 8{NB}bp)
              </span>
            )}
          </span>
        </div>
      )}
      {!hasHybrid && stemloopRt?.dg37_kcal_mol == null && (
        <div className="flex justify-between text-xs py-0.5">
          <span className="text-slate-700">Overhang Tm (DNA:RNA)</span>
          <span className="text-slate-700 tabular-nums text-xs">approximate, see the note</span>
        </div>
      )}
    </>
  );
}

// ── Main export ────────────────────────────────────────────────────

export default function ThermoTable({ results, params }) {
  const [tab, setTab] = useState('A');
  const { top3, stemloop_rt, universal_reverse } = results ?? {};

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      {/* Tab bar */}
      <div role="tablist" aria-label="Thermodynamic parameters view" className="flex border-b border-slate-200 bg-slate-50">
        {[
          { key: 'A', label: 'Comparison' },
          { key: 'B', label: 'Per primer' },
        ].map(({ key, label }) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`px-4 py-2.5 text-xs font-semibold transition-colors border-b-2 -mb-px ${tab === key
                ? 'text-teal-700 border-teal-600 bg-white'
              : 'text-slate-700 border-transparent hover:text-slate-900 hover:bg-white'}`}
          >
            {label}
          </button>
        ))}
      </div>

      <div role="tabpanel" className="p-4">
        {tab === 'A' && <TabA top3={top3} />}
        {tab === 'B' && (
          <TabB top3={top3} stemloopRt={stemloop_rt} universalReverse={universal_reverse} params={params} />
        )}
      </div>
    </div>
  );
}
