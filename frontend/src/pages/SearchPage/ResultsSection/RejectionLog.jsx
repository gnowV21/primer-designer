// RejectionLog — collapsed summary of rejected candidates, with tips that match the
// actual rejection reasons (UI review 2026-11-23).

import { useState } from 'react';

const NB = ' ';

const LABELS = {
  tm_out_of_range:       'Tm outside the Tm window',
  tm_binding_too_low:    `Binding-region Tm too low (< 25${NB}°C)`,
  gc_out_of_range:       'GC content outside the GC window',
  too_short:             'Primer too short',
  too_long:              'Primer too long',
  homopolymer_run:       'Homopolymer run of 5 or more nt',
  gc_clamp_fail:         '3′ GC clamp missing (no G/C in the last 3 nt)',
  gc_end_window_fail:    '3′ end too GC-rich (last 5 nt all G/C)',
  amplicon_out_of_range: 'Amplicon outside the amplicon range',
};

// What the user can do about each reason.
const TIPS = {
  tm_out_of_range:       'Tm: widen the Tm window under Parameters (Required).',
  gc_out_of_range:       'GC: widen the GC window under Parameters.',
  amplicon_out_of_range: 'Amplicon: widen the amplicon range under Parameters (Required).',
  too_short:             `Length: the engine keeps forward primers of 18–27${NB}nt; these rejections are expected and need no change.`,
  too_long:              `Length: the engine keeps forward primers of 18–27${NB}nt; these rejections are expected and need no change.`,
  homopolymer_run:       'Homopolymer: a fixed sequence rule; no parameter changes it.',
  gc_clamp_fail:         '3′ end: a standard primer rule; a candidate that fails it is still ranked, below those that pass.',
  gc_end_window_fail:    '3′ end: a standard primer rule; a candidate that fails it is still ranked, below those that pass.',
  tm_binding_too_low:    'Binding Tm: set by the miRNA sequence; no parameter changes it.',
};

export default function RejectionLog({ rejected, total, summary }) {
  const [open, setOpen] = useState(false);
  const reasons = Object.entries(summary || {}).sort((a, b) => b[1] - a[1]);
  const tips = [...new Set(reasons.map(([r]) => TIPS[r]).filter(Boolean))];

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-xs font-semibold text-slate-700">
          Rejected candidates: {rejected} of {total}
        </span>
        <span className="text-teal-700 text-xs font-medium">{open ? 'Hide' : 'Show'}</span>
      </button>

      {open && reasons.length > 0 && (
        <div className="border-t border-slate-200 px-4 py-3 space-y-1.5">
          {reasons.map(([reason, count]) => (
            <div key={reason} className="flex items-center justify-between gap-3 text-xs text-slate-700">
              <span>{LABELS[reason] || reason.replace(/_/g, ' ')}</span>
              <span className="font-semibold tabular-nums shrink-0">{count}</span>
            </div>
          ))}
          {tips.length > 0 && (
            <ul className="text-xs text-slate-700 mt-2 pt-2 border-t border-slate-200 space-y-0.5" data-testid="rejection-tips">
              {tips.map((t) => <li key={t}>{t}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
