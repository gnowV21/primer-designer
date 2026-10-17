// ResultsSection — container for Phase 2 primer design output.
// Shows global warnings, top-3 primer sets, stem-loop RT info, rejection log,
// and specificity warnings (cross-reactivity, heterodimer, isoMiR) from v2.8.2.

import PrimerSetCard from './PrimerSetCard.jsx';
import RejectionLog from './RejectionLog.jsx';
import Tooltip from '../../../components/ui/Tooltip.jsx';
import FamilySpecificityMap from '../../../components/FamilySpecificityMap.jsx';
import OverhangCollisionPanel from '../../../components/OverhangCollisionPanel.jsx';
import CollapsibleCard from '../../../components/ui/CollapsibleCard.jsx';
import { rankReason } from '../../../utils/rankReason.js';

// Warnings shown in-context elsewhere (design-page slider / results-page note) —
// not repeated in the generic list. Still recorded in the exported report.
const DEDICATED_WARNING_FIELDS = new Set(['signalMethod', 'bindingRegion3prime']);

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
          <h2 className="text-lg font-semibold text-slate-800">Design Results</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {metadata?.mirna_length}-nt miRNA · {top3?.length} primer set{top3?.length !== 1 ? 's' : ''} found
            {metadata?.elapsed_seconds !== undefined && ` · ${metadata.elapsed_seconds}s`}
          </p>
        </div>
        <span className="text-xs bg-teal-50 text-teal-700 border border-teal-200 rounded-full px-3 py-1 font-medium">
          Algorithm v{metadata?.algorithm_version}
        </span>
      </div>}

      {/* ── Global warnings — suppressed when hideHeader=true (shown by QualitySummary in ResultsPage) ── */}
      {/* Off-label overhang + SYBR choice are shown in-context (design page / results note),
          so they are not repeated here. They remain in the exported report. */}
      {!hideHeader && global_warnings.filter((w) => !DEDICATED_WARNING_FIELDS.has(w.field)).length > 0 && (
        <div className="space-y-2">
          {global_warnings.filter((w) => !DEDICATED_WARNING_FIELDS.has(w.field)).map((w, i) => (
            <div
              key={i}
              className={`rounded-xl border px-4 py-3 text-sm ${
                w.severity === 'critical'
                  ? 'bg-red-50 border-red-200 text-red-800'
                  : 'bg-amber-50 border-amber-200 text-amber-800'
              }`}
            >
              <span className="font-semibold mr-2">{w.severity === 'critical' ? 'Critical:' : 'Note:'}</span>
              {w.message}
            </div>
          ))}
        </div>
      )}

      {/* ── Shared components ──────────────────────────────────────────────
           The RT primer and the universal reverse are identical across all
           three candidates, so they are grouped once here rather than competing
           with the ranked results for attention. The universal reverse is the
           same string in every assay ever run, so it gets a single line; the RT
           primer is miRNA-specific and keeps its metrics. */}
      {(stemloop_rt || universal_reverse) && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 space-y-3">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
            Shared by all candidates
          </p>

          {stemloop_rt && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-slate-600">
                Stem-loop RT primer <span className="text-slate-500 font-normal">· miRNA-specific</span>
              </p>
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
                <span className="text-slate-500">({stemloop_rt.mfe_method})</span>
                <span>{stemloop_rt.length} nt</span>
              </div>
              {/* The caveat is signposted by the badge above and stays one click
                  away — it is long methodology, not a finding, so it should not
                  outweigh the sequence it annotates. */}
              {stemloop_rt.tm_note && (
                <details className="group">
                  <summary className="text-xs text-slate-500 cursor-pointer hover:text-teal-700 list-none marker:hidden">
                    <span className="inline-block transition-transform group-open:rotate-90">▸</span>{' '}
                    Why this Tm is approximate
                  </summary>
                  <p className="text-xs text-slate-500 italic mt-1 leading-relaxed">
                    {stemloop_rt.tm_note}
                  </p>
                </details>
              )}
              {stemloop_rt.rt_primer_conc_note && (
                <p className="text-xs text-slate-500">{stemloop_rt.rt_primer_conc_note}</p>
              )}
              {/* A finding, not methodology: when most of this miRNA is 3′ isoforms the
                  assay measures a minority of it — must be visible without expanding. */}
              {stemloop_rt.three_prime_isomir?.three_prime_isomir_risk && (
                <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
                  <span className="font-semibold">3′ isomiRs:</span> {stemloop_rt.three_prime_isomir.warning}{' '}
                  <span className="text-amber-700">Source: {stemloop_rt.three_prime_isomir.source}.</span>
                </p>
              )}
            </div>
          )}

          {universal_reverse && (
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-t border-slate-200 pt-2.5">
              <p className="text-xs font-medium text-slate-600 shrink-0">
                Universal reverse <span className="text-slate-500 font-normal">· fixed</span>
              </p>
              <code className="font-mono text-xs text-slate-700">
                5'–{universal_reverse.sequence}–3'
              </code>
              <span className="text-xs text-slate-500 tabular-nums">
                Tm {universal_reverse.tm?.toFixed(1)}°C · GC {universal_reverse.gc_percent}% · {universal_reverse.length} nt
              </span>
            </div>
          )}
        </div>
      )}

      {/* ── Top-3 primer sets ── */}
      {top3?.length > 1 && (
        <p className="text-sm text-slate-600 leading-relaxed">{rankReason(top3[0], top3[1])}</p>
      )}
      <div className="space-y-5">
        {(top3 || []).map((set, i) => (
          <PrimerSetCard key={i} set={set} stemloop={stemloop_rt} reverse={universal_reverse} mirnaId={mirnaId} />
        ))}
      </div>

      {/* ── Primer-binding specificity (Week 2 P1): the RT + forward axes drive scoring ──
           Collapsed by default; the worst risk stays visible in the header so a
           CRITICAL result is never hidden behind a closed panel. */}
      {specificity_warnings?.overhang_collision && (() => {
        const oc = specificity_warnings.overhang_collision;
        const risk = oc.worst_combined_risk || 'SAFE';
        const nCollide = (oc.collisions || []).length;
        const tone = risk === 'CRITICAL' ? 'danger' : risk === 'LOW' ? 'warn' : 'ok';
        return (
          <CollapsibleCard
            title="Primer Binding Specificity"
            tone={tone}
            summary={`${risk}${nCollide ? ` · ${nCollide} screened collision${nCollide !== 1 ? 's' : ''}` : ''}`}
          >
            <OverhangCollisionPanel overhangCollision={oc} />
          </CollapsibleCard>
        );
      })()}

      {/* ── Seed family (biological context only): map + table toggle ── */}
      {specificity_warnings?.cross_reactivity && (() => {
        const cr = specificity_warnings.cross_reactivity;
        const fam = cr.family || 'ungrouped';
        const nSib = (cr.cross_reactivity || []).length;
        return (
          <CollapsibleCard
            title="Seed Family (biological context)"
            summary={`${fam} · ${nSib} sibling${nSib !== 1 ? 's' : ''}`}
          >
            <FamilySpecificityMap familyCrossReactivity={cr} />
          </CollapsibleCard>
        );
      })()}

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
        <p className="text-center text-xs text-slate-500 pt-2">
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
  // The "approximate" state is a modeling caveat shown on every result, not a
  // problem — neutral slate (not amber) so it does not read as an alarm.
  const color = hasHybrid
    ? 'bg-slate-50 text-slate-700 border-slate-200'
    : 'bg-slate-50 text-slate-500 border-slate-200';

  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded border ${color}`}>
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
            <p className="text-xs text-amber-800 mt-1">{rec.off_label_warning}</p>
          )}
          {!rec.resolved && rec.remaining_high_risk_siblings?.length > 0 && (
            <p className="text-xs text-red-700">
              Unresolved at max overhang: {rec.remaining_high_risk_siblings.join(', ')}
            </p>
          )}
        </div>
      )}

      {/* Data warning */}
      <p className="text-xs text-slate-500 italic">{data.data_warning}</p>
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
