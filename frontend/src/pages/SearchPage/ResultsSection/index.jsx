// ResultsSection — container for Phase 2 primer design output.
// Shows global warnings, top-3 primer sets, stem-loop RT info, and rejection log.

import PrimerSetCard from './PrimerSetCard.jsx';
import RejectionLog from './RejectionLog.jsx';

export default function ResultsSection({ results, error }) {
  if (error) return <ErrorPanel error={error} />;
  if (!results) return null;

  const { top3, stemloop_rt, universal_reverse, global_warnings = [], metadata } = results;

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">Design Results</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {metadata?.mirna_length}-nt miRNA · {top3?.length} primer set{top3?.length !== 1 ? 's' : ''} found
            {metadata?.elapsed_seconds !== undefined && ` · ${metadata.elapsed_seconds}s`}
          </p>
        </div>
        <span className="text-xs bg-teal-50 text-teal-700 border border-teal-200 rounded-full px-3 py-1 font-medium">
          Algorithm v{metadata?.algorithm_version}
        </span>
      </div>

      {/* ── Global warnings ── */}
      {global_warnings.length > 0 && (
        <div className="space-y-2">
          {global_warnings.map((w, i) => (
            <div
              key={i}
              className={`rounded-xl border px-4 py-3 text-sm ${
                w.severity === 'critical'
                  ? 'bg-red-50 border-red-200 text-red-800'
                  : 'bg-amber-50 border-amber-200 text-amber-800'
              }`}
            >
              <span className="font-semibold mr-2">{w.severity === 'critical' ? '⚠ Critical:' : 'ℹ Note:'}</span>
              {w.message}
            </div>
          ))}
        </div>
      )}

      {/* ── Stem-loop RT primer info ── */}
      {stemloop_rt && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 space-y-2">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Stem-loop RT Primer (shared)</p>
          <div className="font-mono text-xs text-slate-700 break-all leading-relaxed">
            {stemloop_rt.sequence}
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
            <span>Tm <strong>{stemloop_rt.tm_full?.toFixed(1)}°C</strong></span>
            <span>GC <strong>{stemloop_rt.gc_percent}%</strong></span>
            <span>MFE <strong>{stemloop_rt.mfe?.toFixed(2)} kcal/mol</strong></span>
            <span className="text-slate-400">({stemloop_rt.mfe_method})</span>
            <span>{stemloop_rt.length} nt</span>
          </div>
          {stemloop_rt.rt_primer_conc_note && (
            <p className="text-xs text-slate-500 border-t border-slate-200 pt-2 mt-1">
              {stemloop_rt.rt_primer_conc_note}
            </p>
          )}
        </div>
      )}

      {/* ── Universal reverse primer info ── */}
      {universal_reverse && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 space-y-2">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Universal Reverse Primer (fixed)</p>
          <div className="font-mono text-xs text-slate-700">
            5'–{universal_reverse.sequence}–3'
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
            <span>Tm <strong>{universal_reverse.tm?.toFixed(1)}°C</strong></span>
            <span>GC <strong>{universal_reverse.gc_percent}%</strong></span>
            <span>{universal_reverse.length} nt</span>
          </div>
        </div>
      )}

      {/* ── Top-3 primer sets ── */}
      <div className="space-y-5">
        {(top3 || []).map((set, i) => (
          <PrimerSetCard key={i} set={set} stemloop={stemloop_rt} reverse={universal_reverse} />
        ))}
      </div>

      {/* ── Rejection log ── */}
      {metadata?.candidates_rejected > 0 && (
        <RejectionLog
          rejected={metadata.candidates_rejected}
          total={metadata.candidates_generated}
          summary={metadata.rejection_summary}
        />
      )}

      {/* ── Source footnote ── */}
      {metadata?.sources && (
        <p className="text-center text-xs text-gray-400 pt-2">
          {metadata.sources.join(' · ')}
        </p>
      )}
    </div>
  );
}

function ErrorPanel({ error }) {
  const icons = {
    no_candidates: '⚠',
    validation: '✕',
    timeout: '⏱',
    network: '⚡',
  };
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-5 space-y-3">
      <div className="flex items-start gap-3">
        <span className="text-red-400 text-xl">{icons[error.type] || '✕'}</span>
        <div className="space-y-1">
          <p className="font-semibold text-red-800 text-sm">{error.message}</p>
          {error.suggestion && (
            <p className="text-red-700 text-xs">{error.suggestion}</p>
          )}
        </div>
      </div>
      {error.rejection_summary && Object.keys(error.rejection_summary).length > 0 && (
        <div className="border-t border-red-200 pt-3">
          <p className="text-xs font-semibold text-red-600 mb-2">Rejection reasons:</p>
          <div className="space-y-1">
            {Object.entries(error.rejection_summary).map(([reason, count]) => (
              <div key={reason} className="flex justify-between text-xs text-red-700">
                <span>{REJECTION_LABELS[reason] || reason}</span>
                <span className="font-semibold tabular-nums">{count}×</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const REJECTION_LABELS = {
  tm_out_of_range:       'Tm out of range',
  tm_binding_too_low:    'Binding-region Tm too low',
  gc_out_of_range:       'GC% out of range',
  too_short:             'Primer too short',
  too_long:              'Primer too long',
  homopolymer_run:       'Homopolymer run ≥ 5',
  gc_clamp_fail:         'GC clamp fail (< 2 G/C in last 3 nt)',
  gc_end_window_fail:    'Too many GC in 3\' window (> 5 in last 5 nt)',
  amplicon_out_of_range: 'Amplicon size out of range',
};
