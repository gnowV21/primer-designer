// ThermoTable — two-tab thermodynamics table (Phase 4 §5).
// Tab A: 3-set comparison matrix, best cell highlighted.
// Tab B: per-primer detail for a selected set.

import { useState } from 'react';

// ── Helpers ────────────────────────────────────────────────────────

function fmt(v, digits = 1) {
  if (v === undefined || v === null || v === '') return '—';
  if (typeof v === 'boolean') return v ? '✓' : '✗';
  if (typeof v === 'number') return v.toFixed(digits);
  return String(v);
}

function fmtDg(v) {
  if (v === undefined || v === null) return '—';
  return `${Number(v).toFixed(2)}`;
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
    label: 'Forward Tm (full)',
    extract: (s) => s?.tm_full,
    format: (s) => fmt(s?.tm_full) + '°C',
    best: 'max',
  },
  {
    label: 'Forward Tm (binding)',
    extract: (s) => s?.tm_binding,
    format: (s) => s?.tm_binding !== undefined ? fmt(s.tm_binding) + '°C' : '—',
    best: 'max',
  },
  {
    label: 'GC% (forward)',
    extract: (s) => s?.gc_percent,
    format: (s) => fmt(s?.gc_percent) + '%',
    best: 'max',
  },
  {
    label: 'Amplicon',
    extract: (s) => s?.amplicon_size,
    format: (s) => fmt(s?.amplicon_size, 0) + ' bp',
    best: 'min_abs', // closer to default is best
  },
  {
    label: 'Hairpin ΔG',
    extract: (s) => get(s, 'structure_checks', 'hairpin', 'dg'),
    format: (s) => fmtDg(get(s, 'structure_checks', 'hairpin', 'dg')),
    best: 'min_abs',
  },
  {
    label: 'Self-dimer ΔG',
    extract: (s) => get(s, 'structure_checks', 'self_dimer', 'dg'),
    format: (s) => fmtDg(get(s, 'structure_checks', 'self_dimer', 'dg')),
    best: 'min_abs',
  },
  {
    label: 'Hetero-dimer fwd×rev ΔG',
    extract: (s) => get(s, 'heterodimer_checks', 'fwd_reverse', 'dg'),
    format: (s) => fmtDg(get(s, 'heterodimer_checks', 'fwd_reverse', 'dg')),
    best: 'min_abs',
  },
  {
    label: 'Hetero-dimer fwd×RT ΔG',
    extract: (s) => get(s, 'heterodimer_checks', 'fwd_stemloop', 'dg'),
    format: (s) => fmtDg(get(s, 'heterodimer_checks', 'fwd_stemloop', 'dg')),
    best: 'min_abs',
  },
  {
    label: "3′ end stability ΔG",
    extract: (s) => get(s, 'structure_checks', 'end_stability', 'stability_kcal_mol'),
    format: (s) => {
      const v = get(s, 'structure_checks', 'end_stability', 'stability_kcal_mol');
      return v !== undefined ? fmtDg(v) : '—';
    },
    best: 'min_abs',
  },
  {
    label: 'Bound fraction (binding)',
    extract: (s) => get(s, 'scores', 'bound_fraction_binding'),
    format: (s) => {
      const v = get(s, 'scores', 'bound_fraction_binding');
      return v !== undefined ? fmt(v) : '—';
    },
    best: 'max',
  },
  {
    label: 'GC clamp',
    extract: (s) => get(s, 'scores', 'gc_clamp'),
    format: (s) => {
      const v = get(s, 'scores', 'gc_clamp');
      return v !== undefined ? fmt(v, 0) : '—';
    },
    best: 'max',
  },
  {
    label: 'isoMiR flag',
    extract: () => null, // not numeric
    format: (s) => {
      const risk = get(s, 'isomir_flag', 'isomir_discrimination_risk');
      return risk === true ? '⚠ Yes' : risk === false ? '✓ No' : '—';
    },
    best: null,
  },
];

function TabA({ top3 }) {
  if (!top3?.length) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="bg-teal-600 text-white">
            <th className="text-left px-3 py-2 font-semibold rounded-tl-lg w-48">Criterion</th>
            {top3.map((s) => (
              <th key={s.rank} className="text-center px-3 py-2 font-semibold">
                Rank {s.rank}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row, ri) => {
            const bIdx = row.best ? bestIndex(top3, row.extract, row.best) : -1;
            return (
              <tr
                key={row.label}
                className={ri % 2 === 0 ? 'bg-white' : 'bg-slate-50'}
              >
                <td className="px-3 py-1.5 font-medium text-slate-600 border-r border-slate-100">
                  {row.label}
                </td>
                {top3.map((s, si) => (
                  <td
                    key={s.rank}
                    className={`px-3 py-1.5 text-center tabular-nums ${
                      si === bIdx ? 'bg-teal-50 text-teal-800 font-semibold' : 'text-slate-700'
                    }`}
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
  );
}

// ── Tab B — Per-primer detail ──────────────────────────────────────

function SeqBlock({ label, sequence, tag }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(sequence ?? '').then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="rounded-lg border border-slate-200 px-3 py-2.5 space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">{label}</span>
        {tag && (
          <span className="text-xs bg-teal-50 text-teal-700 border border-teal-200 rounded-full px-2 py-0.5">
            {tag}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-slate-800 break-all leading-relaxed flex-1">
          5′–{sequence}–3′
        </span>
        <button
          onClick={copy}
          className="shrink-0 text-xs px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-600 transition"
        >
          {copied ? '✓' : 'Copy'}
        </button>
      </div>
    </div>
  );
}

function PropRow({ label, value }) {
  if (value === undefined || value === null || value === '—') return null;
  return (
    <div className="flex justify-between text-xs py-0.5">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-700 tabular-nums font-medium">{value}</span>
    </div>
  );
}

function TabB({ top3, stemloopRt, universalReverse }) {
  const [selRank, setSelRank] = useState(1);
  const set = top3?.find((s) => s.rank === selRank) ?? top3?.[0];

  if (!set) return null;

  return (
    <div className="space-y-4">
      {/* Rank selector */}
      <div className="flex gap-2">
        {(top3 ?? []).map((s) => (
          <button
            key={s.rank}
            onClick={() => setSelRank(s.rank)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              s.rank === selRank
                ? 'bg-teal-600 text-white shadow-sm'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Rank {s.rank}
            {s.grade && <span className="ml-1 opacity-70">· {s.grade}</span>}
          </button>
        ))}
      </div>

      {/* Forward primer */}
      <div className="space-y-2">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">Forward Primer</p>
        <SeqBlock label="Sequence" sequence={set.sequence} tag={`${set.length} nt`} />
        <div className="grid grid-cols-2 gap-x-6 px-1">
          <PropRow label="Tm (full)" value={set.tm_full !== undefined ? fmt(set.tm_full) + '°C' : undefined} />
          <PropRow label="Tm (binding region)" value={set.tm_binding !== undefined ? fmt(set.tm_binding) + '°C' : undefined} />
          <PropRow label="GC%" value={set.gc_percent !== undefined ? fmt(set.gc_percent) + '%' : undefined} />
          <PropRow label="Amplicon" value={set.amplicon_size !== undefined ? fmt(set.amplicon_size, 0) + ' bp' : undefined} />
          <PropRow label="Hairpin ΔG" value={fmtDg(get(set, 'structure_checks', 'hairpin', 'dg'))} />
          <PropRow label="Self-dimer ΔG" value={fmtDg(get(set, 'structure_checks', 'self_dimer', 'dg'))} />
          <PropRow label="3′ stability ΔG" value={fmtDg(get(set, 'structure_checks', 'end_stability', 'stability_kcal_mol'))} />
          <PropRow label="Binding region" value={set.specific_length !== undefined ? `${set.specific_length} nt` : undefined} />
          <PropRow label="Binding pos (1-based)" value={
            set.binding_start_1based !== undefined
              ? `${set.binding_start_1based}–${set.binding_end_1based}`
              : undefined
          } />
          <PropRow label="Total score" value={set.total_score !== undefined ? fmt(set.total_score) : undefined} />
        </div>
      </div>

      {/* RT stem-loop primer */}
      {stemloopRt && (
        <div className="space-y-2">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">RT Stem-loop Primer (shared)</p>
          <SeqBlock label="Sequence" sequence={stemloopRt.sequence} tag={`${stemloopRt.length} nt`} />
          <div className="grid grid-cols-2 gap-x-6 px-1">
            <PropRow label="Tm" value={stemloopRt.tm_full !== undefined ? fmt(stemloopRt.tm_full) + '°C' : undefined} />
            <PropRow label="GC%" value={stemloopRt.gc_percent !== undefined ? fmt(stemloopRt.gc_percent) + '%' : undefined} />
            <PropRow label="MFE" value={stemloopRt.mfe !== undefined ? fmt(stemloopRt.mfe, 2) + ' kcal/mol' : undefined} />
            <PropRow label="MFE method" value={stemloopRt.mfe_method} />
          </div>
        </div>
      )}

      {/* Universal reverse */}
      {universalReverse && (
        <div className="space-y-2">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">Universal Reverse Primer (fixed)</p>
          <SeqBlock label="Sequence" sequence={universalReverse.sequence} tag={`${universalReverse.length} nt`} />
          <div className="grid grid-cols-2 gap-x-6 px-1">
            <PropRow label="Tm" value={universalReverse.tm !== undefined ? fmt(universalReverse.tm) + '°C' : undefined} />
            <PropRow label="GC%" value={universalReverse.gc_percent !== undefined ? fmt(universalReverse.gc_percent) + '%' : undefined} />
            <PropRow label="Hairpin ΔG" value={fmtDg(get(universalReverse, 'self_structure_check', 'hairpin_dg'))} />
            <PropRow label="Self-dimer ΔG" value={fmtDg(get(universalReverse, 'self_structure_check', 'self_dimer_dg'))} />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main export ────────────────────────────────────────────────────

export default function ThermoTable({ results }) {
  const [tab, setTab] = useState('A');
  const { top3, stemloop_rt, universal_reverse } = results ?? {};

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-slate-200 bg-slate-50">
        {[
          { key: 'A', label: 'Comparison (3 sets)' },
          { key: 'B', label: 'Per-primer detail' },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2.5 text-xs font-semibold transition-colors border-b-2 -mb-px ${
              tab === key
                ? 'text-teal-700 border-teal-600 bg-white'
                : 'text-slate-500 border-transparent hover:text-slate-700 hover:bg-white'
            }`}
          >
            Tab {key} — {label}
          </button>
        ))}
      </div>

      <div className="p-4">
        {tab === 'A' && <TabA top3={top3} />}
        {tab === 'B' && (
          <TabB top3={top3} stemloopRt={stemloop_rt} universalReverse={universal_reverse} />
        )}
      </div>
    </div>
  );
}
