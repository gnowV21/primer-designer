// ProbeCard — displays TaqMan probe result from /api/design (Phase 6 §A.5).
// Receives `probe` (object|null) and `probeNote` (string|null) from parent.
// Probe is quality-checked only — NOT in weighted-sum score.

import { useState } from 'react';

const RISK_COLOR = {
  pass:  'bg-teal-50 border-teal-200 text-teal-800',
  fail:  'bg-red-50  border-red-200  text-red-800',
  warn:  'bg-amber-50 border-amber-200 text-amber-800',
  info:  'bg-slate-50 border-slate-200 text-slate-600',
};

function Badge({ label, pass }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium border ${
        pass ? 'bg-teal-50 border-teal-300 text-teal-700' : 'bg-red-50 border-red-300 text-red-700'
      }`}
    >
      {pass ? '✓' : '✗'} {label}
    </span>
  );
}

function SeqDisplay({ sequence, mode }) {
  // In custom mode colour: first 7 nt = miRNA side (teal), last 4 nt = stemloop side (violet).
  // In universal mode: plain sequence (all stemloop body).
  if (!sequence) return null;

  if (mode === 'custom') {
    const mirnaSide    = sequence.slice(0, 7);
    const stemloopSide = sequence.slice(-4);
    const middle       = sequence.slice(7, -4);
    return (
      <span className="font-mono text-sm tracking-wide">
        <span className="text-teal-700 font-semibold" title="miRNA-side (7 nt)">{mirnaSide}</span>
        <span className="text-slate-700">{middle}</span>
        <span className="text-violet-700 font-semibold" title="Stemloop-side (4 nt)">{stemloopSide}</span>
      </span>
    );
  }

  return <span className="font-mono text-sm tracking-wide text-slate-700">{sequence}</span>;
}

export default function ProbeCard({ probe, probeNote }) {
  const [showChecks, setShowChecks] = useState(false);

  // No TaqMan (SYBR or not designed)
  if (!probe && probeNote) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
        ℹ {probeNote}
      </div>
    );
  }

  if (!probe) return null;

  const {
    sequence, length, tm, gc_percent, position_1based,
    mode, probe_type,
    quality = {},
    warnings = [],
    passes_all,
    disclaimer,
  } = probe;

  const { tm_gap, checks = {} } = quality;

  const allCheckEntries = Object.entries(checks);
  // checks[key] is {value, pass} object from backend; normalise to boolean for display
  const checkPass = (v) => (v != null && typeof v === 'object' ? v.pass : Boolean(v));
  const failedChecks = allCheckEntries.filter(([, v]) => !checkPass(v));

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-4 space-y-3">
      {/* [§3.4] Specificity advisory — always shown for any TaqMan probe */}
      <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800 leading-relaxed">
        <span className="font-semibold">Specificity note:</span> The probe does not confer
        miRNA sequence specificity. Discrimination between miRNAs is delivered by the
        stem-loop RT primer (3′ overhang) and the forward primer. A universal probe generates
        signal for any amplicon sharing the stem-loop body, including non-specific products.
      </div>

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <p className="text-sm font-semibold text-slate-700">
          TaqMan Probe
          <span className="ml-2 text-xs font-normal text-slate-500 capitalize">
            ({mode ?? 'custom'} · {probe_type === 'mgb' ? 'MGB' : probe_type === 'lna' ? 'LNA' : 'Single-Q'})
          </span>
        </p>

        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-semibold border ${
            passes_all
              ? 'bg-teal-50 border-teal-300 text-teal-700'
              : 'bg-red-50 border-red-300 text-red-700'
          }`}
        >
          {passes_all ? 'Passes QC' : 'Fails QC'}
        </span>
      </div>

      {/* Sequence */}
      <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <SeqDisplay sequence={sequence} mode={mode} />
        </div>
        {mode === 'custom' && (
          <p className="text-xs text-slate-400">
            <span className="text-teal-600 font-medium">■ miRNA-side (7 nt)</span>
            {'  '}
            <span className="text-violet-600 font-medium">■ Stemloop-side (4 nt)</span>
            {'  '}
            Position: {position_1based ?? '—'}
          </p>
        )}
        {mode === 'universal' && (
          <p className="text-xs text-slate-400">
            Universal mode — binds stemloop body. Position: {position_1based ?? '—'}
          </p>
        )}
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-3 gap-2 text-xs text-center">
        <div className="rounded-lg bg-slate-50 border border-slate-100 px-2 py-1.5">
          <p className="text-slate-400 mb-0.5">Tm</p>
          <p className="font-semibold text-slate-700">{tm != null ? `${tm.toFixed(1)} °C` : '—'}</p>
        </div>
        <div className="rounded-lg bg-slate-50 border border-slate-100 px-2 py-1.5">
          <p className="text-slate-400 mb-0.5">GC%</p>
          <p className="font-semibold text-slate-700">{gc_percent != null ? `${gc_percent.toFixed(1)}%` : '—'}</p>
        </div>
        <div className="rounded-lg bg-slate-50 border border-slate-100 px-2 py-1.5">
          <p className="text-slate-400 mb-0.5">Tm gap</p>
          <p className={`font-semibold ${tm_gap != null && tm_gap >= 6 ? 'text-teal-700' : 'text-red-600'}`}>
            {tm_gap != null ? `+${tm_gap.toFixed(1)} °C` : '—'}
          </p>
        </div>
      </div>

      {/* Quality badges */}
      {allCheckEntries.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {allCheckEntries.map(([key, val]) => (
            <Badge key={key} label={key.replace(/_/g, ' ')} pass={checkPass(val)} />
          ))}
        </div>
      )}

      {/* Toggle checks detail */}
      {failedChecks.length > 0 && (
        <button
          onClick={() => setShowChecks(!showChecks)}
          className="text-xs text-slate-500 underline underline-offset-2 hover:text-slate-700"
        >
          {showChecks ? 'Hide' : 'Show'} {failedChecks.length} failed check{failedChecks.length > 1 ? 's' : ''}
        </button>
      )}
      {showChecks && failedChecks.length > 0 && (
        <div className="space-y-1">
          {failedChecks.map(([key]) => (
            <div key={key} className={`rounded-lg border px-3 py-1.5 text-xs ${RISK_COLOR.fail}`}>
              ✗ {key.replace(/_/g, ' ')}
            </div>
          ))}
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="space-y-1">
          {warnings.map((w, i) => (
            <div key={i} className={`rounded-lg border px-3 py-1.5 text-xs ${RISK_COLOR.warn}`}>
              ⚑ {w}
            </div>
          ))}
        </div>
      )}

      {/* [§3.2] Double-quenched advisory */}
      {probe_type === 'single_q' && length >= 20 && (
        <div className={`rounded-lg border px-3 py-1.5 text-xs ${RISK_COLOR.info}`}>
          Advisory: For probes ≥20 nt, double-quenched chemistry (e.g. ZEN/Iowa Black, TAO)
          reduces background fluorescence and improves signal-to-noise ratio.
        </div>
      )}

      {/* Disclaimer */}
      {disclaimer && (
        <p className="text-xs text-slate-400 border-t border-slate-100 pt-2">{disclaimer}</p>
      )}
    </div>
  );
}
