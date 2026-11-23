// ResultsSection — container for Phase 2 primer design output.
// Shows global warnings, top-3 primer sets, stem-loop RT info, rejection log,
// and specificity warnings (cross-reactivity, heterodimer, isoMiR) from v2.8.2.

import { useState } from 'react';
import PrimerSetCard from './PrimerSetCard.jsx';
import CriteriaPanel from './CriteriaPanel.jsx';
import RejectionLog from './RejectionLog.jsx';
import FamilySpecificityMap from '../../../components/FamilySpecificityMap.jsx';
import OverhangCollisionPanel from '../../../components/OverhangCollisionPanel.jsx';
import CollapsibleCard from '../../../components/ui/CollapsibleCard.jsx';
import TierBanners, { TIER_WARNING_FIELDS } from './TierBanners.jsx';
import SetComparison, { sharedClosestOffTarget } from './SetComparison.jsx';
import NoBreak from '../../../components/ui/NoBreak.jsx';
import { levelWord } from '../../../utils/format.js';
import IsoformTable from './IsoformTable.jsx';
import { rankReason } from '../../../utils/rankReason.js';
import { equivalentRanks } from '../../../utils/tierRank.js';
import { SeqBlock } from '../../../components/ui/Seq.jsx';

// Warnings shown in-context elsewhere (design-page slider / results-page note, or the
// tiered banners) — not repeated in the generic list. Still in the exported report.
const DEDICATED_WARNING_FIELDS = new Set(['signalMethod', 'bindingRegion3prime', ...TIER_WARNING_FIELDS]);
// Warnings with their own panel on /results (Assay Specificity, Seed Family, the
// 3′-isomiR line of "Shared by all sets"): not repeated as a banner.
const PANEL_WARNING_FIELDS = new Set(['overhang_collision', 'cross_reactivity', 'three_prime_isomir',
  'three_prime_isomir_fold_change', 'three_prime_isomir_dominant']);

export default function ResultsSection({ results, error, hideHeader = false }) {
  const [criteriaOpen, setCriteriaOpen] = useState(false);
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
  const blastAvailable = results.ranking_summary?.blast_available !== false;

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      {!hideHeader && <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">Design results</h2>
          <p className="text-xs text-slate-600 mt-0.5">
            {metadata?.mirna_length}-nt miRNA · {top3?.length} primer set{top3?.length !== 1 ? 's' : ''} found
            {metadata?.elapsed_seconds !== undefined && ` · ${metadata.elapsed_seconds}s`}
          </p>
        </div>
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
              <span className="font-semibold mr-2">{w.severity === 'critical' ? 'Critical:' : 'Warning:'}</span>
              <NoBreak>{w.message}</NoBreak>
            </div>
          ))}
        </div>
      )}

      {/* ── Page order (review panel 2026-11-18): verdict → comparison → shared
           primers → per-set cards → detail panels. The most important finding (a
           specificity fallback, a fallback species) is the first thing on the page. ── */}

      {/* 1. Verdict: design-level banners, then why #1 is above #2 */}
      <TierBanners results={results} />
      {/* Critical design warnings without a dedicated display (the Quality summary that
          listed them is gone from /results; every warning stays in the PDF/CSV export). */}
      {hideHeader && global_warnings
        .filter((w) => w.severity === 'critical' && !DEDICATED_WARNING_FIELDS.has(w.field)
          && !PANEL_WARNING_FIELDS.has(w.field))
        .map((w, i) => (
          <div key={i} className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" data-testid="critical-warning">
            <span className="font-semibold mr-2">Critical:</span><NoBreak>{w.message}</NoBreak>
          </div>
        ))}
      {top3?.length > 1 && (
        <p className="text-sm text-slate-700 leading-relaxed" data-testid="rank-reason">{rankReason(top3[0], top3[1])}</p>
      )}

      {/* 2. The sets side by side (tiered) */}
      <SetComparison top3={top3} blastAvailable={blastAvailable} />

      {/* 3. RT primer + universal reverse: identical for every set, shown once */}
      {(stemloop_rt || universal_reverse) && (
        <SharedPrimers stemloopRt={stemloop_rt} reverse={universal_reverse}
          tmReverse={top3?.[0]?.ranking?.pcr?.tm_pair?.tm_reverse}
          closest={sharedClosestOffTarget(top3)} />
      )}

      {/* 4. Per-set cards (#1 open) */}
      <div className="space-y-5">
        {(top3 || []).map((set, i) => (
          <PrimerSetCard
            key={i}
            set={set}
            stemloop={stemloop_rt}
            reverse={universal_reverse}
            mirnaId={mirnaId}
            mirnaSequence={metadata?.mirna_sequence}
            conditions={metadata?.design_settings?.effective_p3}
            species={metadata?.species_code}
            blastAvailable={blastAvailable}
            equivalentTo={equivalentRanks(set, top3)}
            tmWindow={metadata?.design_settings?.tm_target_c}
            onExplain={() => setCriteriaOpen(true)}
          />
        ))}
      </div>
      <CriteriaPanel open={criteriaOpen} onClose={() => setCriteriaOpen(false)} />

      {/* ── Assay specificity (ΔCq model): the headline specificity verdict, drives scoring ──
           Collapsed by default; the worst label stays visible in the header so a
           co-amplified result is never hidden behind a closed panel. */}
      {specificity_warnings?.overhang_collision && (() => {
        const oc = specificity_warnings.overhang_collision;
        const label = oc.worst_assay_label || 'DISCRIMINATED';
        const s = oc.summary || {};
        const nSame = (s.shifted_5p || 0) + (s.shifted_3p || 0) + (s.same_sequence || 0);
        const tone = label === 'CO-AMPLIFIED' ? 'danger' : label === 'PARTIAL' ? 'warn' : 'ok';
        const parts = [levelWord(label)];
        if (s['CO-AMPLIFIED']) parts.push(`${s['CO-AMPLIFIED']} co-amplified`);
        if (s.PARTIAL) parts.push(`${s.PARTIAL} partial`);
        if (nSame) parts.push(`${nSame} same-molecule`);
        return (
          <CollapsibleCard
            title="Assay specificity"
            tone={tone}
            summary={parts.join(' · ')}
          >
            <OverhangCollisionPanel overhangCollision={oc} hideTitle closest={top3?.[0]?.ranking?.specificity?.assay_dcq} />
          </CollapsibleCard>
        );
      })()}

      {/* ── Seed family (biological context only): map + table toggle ── */}
      {specificity_warnings?.cross_reactivity && (() => {
        const cr = specificity_warnings.cross_reactivity;
        // The API's family label is an auto-generated cluster ID ("miR-1" for the miR-15/16
        // seed): the page names the group by its seed instead (UI review 2026-11-23).
        const seed = (metadata?.mirna_sequence || '').slice(1, 8).toUpperCase();
        const nSib = (cr.cross_reactivity || []).length;
        return (
          <CollapsibleCard
            title="Seed family (biological context)"
            summary={`Seed group ${seed} · ${nSib === 0 ? 'no close sibling' : `${nSib} close sibling${nSib !== 1 ? 's' : ''}`}`}
          >
            <FamilySpecificityMap familyCrossReactivity={cr} seed={seed} hideTitle />
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
        <p className="text-center text-xs text-slate-600 pt-2">
          {metadata.sources.join(' · ')}
        </p>
      )}
    </div>
  );
}

// ── RT primer + universal reverse (shared by every set) ─────────────
// Review panel 2026-11-18: what binds the miRNA is the overhang, so the overhang and its
// DNA:RNA ΔG37 are shown; the full-primer DNA:DNA Tm (not what anneals in the RT step)
// and the modelling caveats are one click away. The 3′-isomiR finding is one line with
// its numbers; the explanation is one click away.

const pct = (x) => (x == null ? '—' : `${Math.round(100 * x)}%`);
const NB = '\u00a0';

/** tmReverse: Tm of the universal reverse primer at the design's conditions, as the
 *  ranking computed it (ranking.pcr.tm_pair.tm_reverse). universal_reverse.tm is a
 *  pre-calculated constant (60.4 °C) the engine does not use; it is shown only for
 *  sets without a ranking block. */
function SharedPrimers({ stemloopRt: rt, reverse, tmReverse, closest }) {
  const tmR = tmReverse ?? reverse?.tm;
  const iso = rt?.three_prime_isomir;
  const isoShown = iso?.three_prime_isomir_risk || iso?.fold_change_bias_risk || iso?.dominant_isoform_risk;
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 space-y-3" data-testid="shared-primers">
      <h3 className="text-sm font-semibold text-slate-800">Shared by all sets</h3>
      {closest && (
        <p className="text-xs text-slate-700" data-testid="shared-closest">
          Closest off-target for every set: <span className="whitespace-nowrap font-medium">{closest}</span>
        </p>
      )}

      {rt && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-slate-700">
            Stem-loop RT primer <span className="text-slate-600 font-normal">(miRNA-specific)</span>
          </p>
          <SeqBlock sequence={rt.sequence} testId="rt-sequence" />
          <p className="text-xs text-slate-700 tabular-nums">
            Overhang <span className="seq">{rt.overhang_dna}</span> ({rt.binding_length}{NB}nt)
            {rt.tm_hybrid_c != null
              ? <> · hybrid Tm <strong className="whitespace-nowrap">{rt.tm_hybrid_c}{NB}°C</strong></>
              : rt.dg37_kcal_mol != null && <> · <span className="whitespace-nowrap">ΔG at 37{NB}°C</span> <strong className="whitespace-nowrap">{String(rt.dg37_kcal_mol).replace('-', '\u2212')}{NB}kcal/mol</strong> (DNA:RNA)</>}
            {' · '}stem MFE <span className="whitespace-nowrap">{rt.mfe?.toFixed(1).replace('-', '\u2212')}{NB}kcal/mol</span> · {rt.length}{NB}nt
          </p>
          {rt.rt_primer_conc_note && <p className="text-xs text-slate-700"><NoBreak>{rt.rt_primer_conc_note}</NoBreak></p>}
          <details className="group">
            <summary className="text-xs text-teal-700 cursor-pointer hover:underline list-none marker:hidden">
              <span aria-hidden className="inline-block transition-transform group-open:rotate-90">▸</span>{' '}
              Overhang Tm and model notes
            </summary>
            <div className="text-xs text-slate-700 mt-1 space-y-1 leading-relaxed">
              {rt.tm_note && <p><NoBreak>{rt.tm_note}</NoBreak></p>}
              <p>
                Full-primer Tm {rt.tm_full?.toFixed(1)}{NB}°C (primer3, DNA:DNA; for information only: the RT
                step anneals the overhang to RNA). Stem MFE: {rt.mfe_method}.
              </p>
            </div>
          </details>

          {isoShown && (
            <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 space-y-1" data-testid="isomir-note">
              {iso.dominant_isoform_risk ? (
                <p data-testid="isomir-dominant">
                  <span className="font-semibold">3′ isomiRs:</span> <NoBreak>{iso.dominant_isoform_short}</NoBreak>.
                </p>
              ) : (
                <p>
                  <span className="font-semibold">3′ isomiRs:</span> {pct(iso.median_3prime_fraction)} of reads
                  {iso.iqr_3prime_fraction && <> (IQR {pct(iso.iqr_3prime_fraction[0])}–{pct(iso.iqr_3prime_fraction[1])} across samples)</>}
                  {'. '}Fold changes can mix isoform shifts with level changes.
                </p>
              )}
              <details className="group">
                <summary className="cursor-pointer text-amber-900 font-medium hover:underline list-none marker:hidden">
                  <span aria-hidden className="inline-block transition-transform group-open:rotate-90">▸</span> Why
                </summary>
                <div className="mt-1 space-y-1 leading-relaxed">
                  <IsoformTable iso={iso} />
                  {iso.three_prime_isomir_risk && iso.warning && <p><NoBreak>{iso.warning}</NoBreak></p>}
                  {iso.fold_change_bias_risk && iso.fold_change_bias_warning && <p><NoBreak>{iso.fold_change_bias_warning}</NoBreak></p>}
                  {iso.dominant_isoform_risk && iso.dominant_isoform_warning && <p><NoBreak>{iso.dominant_isoform_warning}</NoBreak></p>}
                  {iso.source && <p>Source: {iso.source}.</p>}
                </div>
              </details>
            </div>
          )}
        </div>
      )}

      {reverse && (
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-t border-slate-200 pt-2.5">
          <p className="text-xs font-medium text-slate-700 shrink-0">
            Universal reverse primer <span className="text-slate-600 font-normal">(fixed)</span>
          </p>
          <SeqBlock sequence={reverse.sequence} className="basis-full sm:basis-auto" testId="reverse-sequence" />
          <span className="text-xs text-slate-700 tabular-nums whitespace-nowrap">
            GC {reverse.gc_percent}% · {reverse.length}{NB}nt
          </span>
          {tmR != null && (
            <p className="basis-full text-xs text-slate-700 tabular-nums" data-testid="reverse-tm-note">
              Tm (reverse) <span className="whitespace-nowrap">{Number(tmR).toFixed(1)}{NB}°C</span> at the design
              conditions. The forward–reverse Tm difference is about Tm (reverse) − Ta: it is set by Ta and the
              reaction conditions and is the same for every set.
            </p>
          )}
        </div>
      )}
    </div>
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
        <p className="text-xs font-semibold text-slate-600">
          Family cross-reactivity
          {data.family && (
            <span className="ml-2 font-normal text-slate-500">
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
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-5 space-y-3">
      <div className="flex items-start gap-3">
        <div className="space-y-1">
          <p className="font-semibold text-red-800 text-sm">{error.message}</p>
          {error.suggestion && (
            <p className="text-red-700 text-xs">{error.suggestion}</p>
          )}
        </div>
      </div>
      {error.rejection_summary && Object.keys(error.rejection_summary).length > 0 && (
        <div className="border-t border-red-200 pt-3">
          <p className="text-xs font-semibold text-red-700 mb-2">Rejection reasons</p>
          <div className="space-y-1">
            {Object.entries(error.rejection_summary).map(([reason, count]) => (
              <div key={reason} className="flex justify-between text-xs text-red-700">
                <span>{REJECTION_LABELS[reason] || reason}</span>
                <span className="font-semibold tabular-nums">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {error.edge_cases?.length > 0 && (
        <div className="border-t border-red-200 pt-3 space-y-1">
          <p className="text-xs font-semibold text-red-700 mb-1">Sequence issues</p>
          {error.edge_cases.map((ec, i) => (
            <p key={i} className="text-xs text-red-700">
              <span className="font-semibold">[{ec.code}]</span> {ec.message}
            </p>
          ))}
        </div>
      )}
      {error.global_warnings?.filter(w => w.severity === 'critical').length > 0 && (
        <div className="border-t border-red-200 pt-3 space-y-1">
          <p className="text-xs font-semibold text-red-700 mb-1">Critical warnings</p>
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
  gc_out_of_range:       'GC content out of range',
  too_short:             'Primer too short',
  too_long:              'Primer too long',
  homopolymer_run:       'Homopolymer run ≥ 5',
  gc_clamp_fail:         '3′ GC clamp missing (no G/C in the last 3 nt)',
  gc_end_window_fail:    '3′ end too GC-rich (last 5 nt all G/C)',
  amplicon_out_of_range: 'Amplicon size out of range',
};
