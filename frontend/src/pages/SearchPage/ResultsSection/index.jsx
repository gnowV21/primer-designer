// ResultsSection — container for Phase 2 primer design output.
// Shows global warnings, top-3 primer sets, stem-loop RT info, rejection log,
// and specificity warnings (cross-reactivity, heterodimer, isoMiR) from v2.8.2.

import PrimerSetCard from './PrimerSetCard.jsx';
import RejectionLog from './RejectionLog.jsx';
import Tooltip from '../../../components/ui/Tooltip.jsx';
import FamilySpecificityMap from '../../../components/FamilySpecificityMap.jsx';

export default function ResultsSection({ results, error, hideHeader = false }) {
  if (error) return <ErrorPanel error={error} />;
  if (!results) return null;

  const {
    top3,
    stemloop_rt,
    universal_reverse,
    global_warnings = [],
    metadata,
    specificity_warnings,
  } = results;

  const mirnaId = metadata?.mirna_id ?? '';

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      {!hideHeader && <div className="flex items-center justify-between">
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
      </div>}

      {/* ── Global warnings — suppressed when hideHeader=true (shown by QualitySummary in ResultsPage) ── */}
      {!hideHeader && global_warnings.length > 0 && (
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
            {/* [RESEARCH_QUESTIONS_UX A2] RT primer overhang anneals to RNA → DNA:RNA hybrid */}
            <span className="flex items-center gap-1">
              Tm (full) <strong>{stemloop_rt.tm_full?.toFixed(1)}°C</strong>
              <RtTmBadge stemloopRt={stemloop_rt} />
            </span>
            {stemloop_rt.tm_hybrid_c != null && (
              <span>
                Overhang hybrid Tm <strong>{stemloop_rt.tm_hybrid_c}°C</strong>
              </span>
            )}
            <span>GC <strong>{stemloop_rt.gc_percent}%</strong></span>
            <span>MFE <strong>{stemloop_rt.mfe?.toFixed(2)} kcal/mol</strong></span>
            <span className="text-slate-400">({stemloop_rt.mfe_method})</span>
            <span>{stemloop_rt.length} nt</span>
          </div>
          {stemloop_rt.tm_note && (
            <p className="text-[11px] text-slate-400 italic">{stemloop_rt.tm_note}</p>
          )}
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
          <PrimerSetCard key={i} set={set} stemloop={stemloop_rt} reverse={universal_reverse} mirnaId={mirnaId} />
        ))}
      </div>

      {/* ── Family specificity (Phase 7 PART C): map + table toggle ── */}
      {specificity_warnings?.cross_reactivity && (
        <FamilySpecificityMap familyCrossReactivity={specificity_warnings.cross_reactivity} />
      )}

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

// ── RT primer Tm chemistry badge + tooltip ──────────────────────────
// [RESEARCH_QUESTIONS_UX A2] RT primer anneals to miRNA (RNA) → DNA:RNA hybrid.
// Full-primer Tm uses primer3 DNA:DNA NN (indicative); overhang hybrid Tm uses Sugimoto 1995.

function RtTmBadge({ stemloopRt }) {
  const hasHybrid = stemloopRt?.tm_hybrid_c != null;
  const caveats   = stemloopRt?.tm_hybrid?.caveats ?? [];

  const tooltipText = hasHybrid
    ? `RT overhang anneals to miRNA (RNA) — DNA:RNA hybrid. `
      + `Overhang Tm modeled via Sugimoto 1995 nearest-neighbor (Biochemistry 34:11211). `
      + `Full-primer Tm uses primer3 DNA:DNA NN (SantaLucia 1998) — indicative only, not scored. `
      + (caveats.length > 0 ? `Caveats: ${caveats.join('; ')}.` : '')
    : `RT primer anneals to miRNA (RNA) → DNA:RNA hybrid. `
      + `Tm shown is from primer3 (DNA:DNA nearest-neighbor, SantaLucia 1998) — approximate; `
      + `true DNA:RNA hybrid Tm may differ by 3–8°C. Not used in scoring.`;

  const label = hasHybrid ? 'Tm: modeled (DNA:RNA, Sugimoto 1995)' : 'Tm: approximate (DNA:RNA)';
  const color = hasHybrid
    ? 'bg-blue-50 text-blue-700 border-blue-200'
    : 'bg-amber-50 text-amber-700 border-amber-200';

  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded border ${color}`}>
      {label}
      <Tooltip text={tooltipText} />
    </span>
  );
}

// ── Cross-reactivity section ────────────────────────────────────────

const CR_RISK_STYLE = {
  IDENTICAL: 'text-red-700 bg-red-50 border-red-300',
  HIGH:      'text-orange-700 bg-orange-50 border-orange-300',
  LOW:       'text-amber-700 bg-amber-50 border-amber-200',
  SAFE:      'text-teal-700 bg-teal-50 border-teal-200',
};

function CrossReactivityPanel({ data }) {
  const siblings = data.cross_reactivity || [];
  const rec = data.recommendation;
  const hasHighRisk = siblings.some((s) => s.risk === 'IDENTICAL' || s.risk === 'HIGH');

  return (
    <div className={`rounded-xl border px-4 py-3 space-y-3 ${hasHighRisk ? 'border-orange-200 bg-orange-50' : 'border-slate-200 bg-slate-50'}`}>
      {/* Header */}
      <div>
        <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
          Family Cross-reactivity
          {data.family && (
            <span className="ml-2 font-normal normal-case text-slate-500">
              ({data.family} family · {data.overhang_used}-nt overhang)
            </span>
          )}
        </p>
        {data.target_overhang && (
          <p className="text-xs text-slate-500 mt-0.5">
            Target 3′ overhang: <span className="font-mono">{data.target_overhang}</span>
          </p>
        )}
      </div>

      {/* Sibling table or empty state */}
      {siblings.length === 0 ? (
        <p className="text-xs text-teal-700">
          No cross-reactive family members detected (Hamming distance ≥ 3 on overhang).
        </p>
      ) : (
        <div className="rounded-lg border border-slate-200 overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-slate-100 border-b border-slate-200">
              <tr>
                <th className="text-left px-3 py-1.5 font-semibold text-slate-600">Sibling miRNA</th>
                <th className="text-center px-2 py-1.5 font-semibold text-slate-600">Overhang</th>
                <th className="text-center px-2 py-1.5 font-semibold text-slate-600">Mismatch</th>
                <th className="text-center px-2 py-1.5 font-semibold text-slate-600">ΔTm</th>
                <th className="text-center px-2 py-1.5 font-semibold text-slate-600">Risk</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {siblings.map((s) => (
                <tr key={s.sibling}>
                  <td className="px-3 py-1.5 font-mono text-slate-700">{s.sibling}</td>
                  <td className="px-2 py-1.5 text-center font-mono text-slate-600">{s.sibling_overhang}</td>
                  <td className="px-2 py-1.5 text-center tabular-nums text-slate-600">{s.mismatch}</td>
                  <td className="px-2 py-1.5 text-center tabular-nums text-slate-600">
                    {s.delta_tm > 0 ? '+' : ''}{s.delta_tm}°C
                  </td>
                  <td className="px-2 py-1.5 text-center">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${CR_RISK_STYLE[s.risk] ?? ''}`}>
                      {s.risk}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Recommendation (only if there's something to recommend) */}
      {rec && hasHighRisk && (
        <div className="rounded-lg bg-white border border-slate-200 px-3 py-2 space-y-1">
          <p className="text-xs font-semibold text-slate-600">Recommendation</p>
          <p className="text-xs text-slate-600">{rec.reason}</p>
          {rec.off_label_warning && (
            <p className="text-xs text-amber-700 mt-1">⚠ {rec.off_label_warning}</p>
          )}
          {!rec.resolved && rec.remaining_high_risk_siblings?.length > 0 && (
            <p className="text-xs text-red-700">
              Unresolved at max overhang: {rec.remaining_high_risk_siblings.join(', ')}
            </p>
          )}
        </div>
      )}

      {/* Data warning */}
      <p className="text-xs text-slate-400 italic">{data.data_warning}</p>
    </div>
  );
}

// ── Error panel ────────────────────────────────────────────────────

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
      {error.edge_cases?.length > 0 && (
        <div className="border-t border-red-200 pt-3 space-y-1">
          <p className="text-xs font-semibold text-red-600 mb-1">Sequence issues detected:</p>
          {error.edge_cases.map((ec, i) => (
            <p key={i} className="text-xs text-red-700">
              <span className="font-semibold">[{ec.code}]</span> {ec.message}
            </p>
          ))}
        </div>
      )}
      {error.global_warnings?.filter(w => w.severity === 'critical').length > 0 && (
        <div className="border-t border-red-200 pt-3 space-y-1">
          <p className="text-xs font-semibold text-red-600 mb-1">Critical warnings:</p>
          {error.global_warnings.filter(w => w.severity === 'critical').map((w, i) => (
            <p key={i} className="text-xs text-red-700">{w.message}</p>
          ))}
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
