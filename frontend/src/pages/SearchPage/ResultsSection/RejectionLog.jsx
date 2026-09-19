// RejectionLog — collapsed summary of rejected candidates.

import { useState } from 'react';

const LABELS = {
  tm_out_of_range:       'Tm out of range',
  tm_binding_too_low:    'Binding-region Tm too low (< 25°C)',
  gc_out_of_range:       'GC% out of range',
  too_short:             'Primer too short',
  too_long:              'Primer too long',
  homopolymer_run:       'Homopolymer run ≥ 5 nt',
  gc_clamp_fail:         'GC clamp fail (< 2 G/C in last 3 nt)',
  gc_end_window_fail:    '3\' GC window too dense (> 5 in last 5 nt)',
  amplicon_out_of_range: 'Amplicon size out of range',
};

export default function RejectionLog({ rejected, total, summary }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-xs font-semibold text-slate-500">
          Rejected candidates: {rejected} / {total}
        </span>
        <span className="text-slate-500 text-xs">{open ? '▲ hide' : '▼ show'}</span>
      </button>

      {open && summary && (
        <div className="border-t border-slate-200 px-4 py-3 space-y-1.5">
          {Object.entries(summary).map(([reason, count]) => (
            <div key={reason} className="flex items-center justify-between gap-3 text-xs text-slate-600">
              <span>{LABELS[reason] || reason}</span>
              <span className="font-semibold tabular-nums text-slate-500 shrink-0">{count}×</span>
            </div>
          ))}
          <p className="text-xs text-slate-500 mt-2 pt-2 border-t border-slate-200">
            Tip: loosen Tm range, GC%, or amplicon size limits to include more candidates.
          </p>
        </div>
      )}
    </div>
  );
}
