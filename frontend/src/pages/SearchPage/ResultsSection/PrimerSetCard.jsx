// PrimerSetCard — displays one ranked primer set (forward + stemloop RT + universal reverse).

import ScoreGauge from './ScoreGauge.jsx';
import ScoreBreakdown from './ScoreBreakdown.jsx';
import StructureChecks from './StructureChecks.jsx';
import ExportButtons from './ExportButtons.jsx';
import OffTargetPanel from './OffTargetPanel.jsx';
import TierSummary, { GradeBadge, TierDetailTable } from './TierSummary.jsx';
import { hasTiers } from '../../../utils/tierRank.js';
import { useState } from 'react';

// How a set relates to the higher-ranked sets (backend select_diverse_top, v3.2.0).
const SELECTION_LABEL = {
  adjacent_3prime: {
    text: "3′ end 1 nt from a higher set",
    title: 'Binding region differs by one nucleotide at its 3′ end from a higher-ranked set. Offered because fewer sets with 3′ ends ≥2 nt apart were available.',
  },
  tail_variant: {
    text: 'Same binding region, other tail',
    title: 'Same miRNA-binding region as the set named here — only the non-binding 5′ tail differs, so specificity is the same. Offered because no other 3′ end passed the filters.',
  },
};

// Pre-filter notes shown on V4 sets only (review panel 2026-11-18):
//  - tiered sets score the clamp as F2 (chip above), so the V4 "75/100" text would
//    contradict it on the same card;
//  - "3′ end is T" is dropped everywhere: it asks for no action (the 3′ end is set
//    by the miRNA) and has no measured effect behind it.
const PREFILTER_WARNING_TEXT = {
  gc_clamp_weak_warning: "Only 1 G/C in the last 3 nt (weak GC clamp). The 3′ end is set by the miRNA sequence; scored 75/100 on the GC-clamp criterion",
};

const RISK_STYLE = {
  HIGH:     'text-red-700 bg-red-50 border-red-300',
  MODERATE: 'text-orange-700 bg-orange-50 border-orange-300',
  LOW:      'text-amber-700 bg-amber-50 border-amber-200',
  PASS:     'text-teal-700 bg-teal-50 border-teal-200',
};

export default function PrimerSetCard({
  set, stemloop, reverse, mirnaId, mirnaSequence, conditions, species,
  blastAvailable = true, equivalentTo = [], tmWindow = null, onExplain,
}) {
  const [expanded, setExpanded] = useState(set.rank === 1);
  const tiered = hasTiers(set);

  const rankColors = ['text-teal-700 bg-teal-50 border-teal-300', 'text-slate-700 bg-slate-50 border-slate-300', 'text-slate-600 bg-slate-50 border-slate-300'];
  const rankColor  = rankColors[(set.rank || 1) - 1] ?? rankColors[2];
  const isomirRisk = set.isomir_flag?.isomir_discrimination_risk;
  const selection  = SELECTION_LABEL[set.selection];
  const prefilterNotes = tiered ? [] : (set.warnings_from_prefilter || []).filter((w) => PREFILTER_WARNING_TEXT[w]);

  return (
    <div className={`rounded-2xl border shadow-sm ${set.rank === 1 ? 'border-teal-300 shadow-teal-100' : 'border-slate-200'}`}>
      {/* ── Card header ── */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-start sm:items-center justify-between gap-3 px-4 sm:px-5 py-4 text-left"
      >
        {/* Wraps on phones: badges on one line, the sequence below them. */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 min-w-0 flex-1">
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${rankColor}`}>
            #{set.rank}
          </span>
          {isomirRisk && (
            <span
              className="text-xs font-semibold px-2 py-0.5 rounded-full border text-purple-700 bg-purple-50 border-purple-300"
              title={set.isomir_flag.note}
            >
              isoMiR
            </span>
          )}
          {selection && (
            <span
              className="text-xs px-2 py-0.5 rounded-full border text-slate-600 bg-slate-50 border-slate-300"
              title={selection.title}
            >
              {selection.text}
              {set.same_binding_as_rank && ` as #${set.same_binding_as_rank}`}
            </span>
          )}
          <div className="min-w-0 basis-full sm:basis-auto">
            <p className="text-sm font-semibold text-slate-800 font-mono break-all">{set.sequence}</p>
            <p className="text-xs text-slate-500 mt-0.5 tabular-nums">
              {set.length} nt · Tm {set.tm_full?.toFixed(1)}°C · GC {set.gc_percent}%
              {set.amplicon_size && ` · ~${set.amplicon_size} bp amplicon`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 sm:gap-4 shrink-0">
          {tiered ? (
            <span className="flex flex-col items-end gap-1" data-testid="card-tier-header">
              <span className="flex items-center gap-1.5">
                <GradeBadge set={set} blastAvailable={blastAvailable} withTooltip={false} />
                <span className="text-xs font-semibold text-slate-700 tabular-nums" title="Required: specificity S1 + S2 + S3">
                  S {set.ranking.specificity.total}/{set.ranking.specificity.max}
                </span>
              </span>
            </span>
          ) : (
            <ScoreGauge score={set.total_score} grade={set.grade} compact />
          )}
          <span className="text-slate-500 text-sm">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>
      {tiered && equivalentTo?.length > 0 && (
        <p className="px-4 sm:px-5 -mt-2 pb-3">
          <span
            className="text-xs px-2 py-0.5 rounded-full border text-slate-700 bg-slate-50 border-slate-300"
            title="Same Required specificity, same No-critical-weakness result, same PCR and Composition & structure levels: the sets differ only in the tie-break score (SPEC QD 16)."
            data-testid="equivalent-label"
          >
            Equivalent in silico to #{equivalentTo.join(', #')}
          </span>
        </p>
      )}

      {expanded && (
        <div className="border-t border-slate-100 px-4 sm:px-5 py-4 space-y-5">
          {/* ── Forward primer (the RT primer and the universal reverse are the same for
               every set: shown once, in "Shared by all sets") ── */}
          <PrimerRow label="Forward" seq={set.sequence} detail={`Binding: ${set.specific_region || '—'} (${set.specific_length} nt)`} />
          {tiered && <LowBindingTmNote set={set} />}

          {/* ── Tiers (4.0.0) or the V4 score (U5) + structure ── */}
          {tiered ? (
            <div className="space-y-3">
              <TierSummary set={set} blastAvailable={blastAvailable} tmWindow={tmWindow} onExplain={onExplain} />
              <TierDetailTable set={set} />
              {set.structure_checks && (
                <StructureChecks checks={set.structure_checks} />
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="space-y-3">
                <ScoreGauge score={set.total_score} grade={set.grade} />
                {set.scores && set.weights && (
                  <ScoreBreakdown scores={set.scores} weights={set.weights} explanations={set.explanations} />
                )}
              </div>
              <div>
                {set.structure_checks && (
                  <StructureChecks checks={set.structure_checks} />
                )}
              </div>
            </div>
          )}

          {/* ── Heterodimer checks ── */}
          {set.heterodimer_checks && (
            <HeterodimersPanel checks={set.heterodimer_checks} />
          )}

          {/* ── isoMiR flag detail ── */}
          {isomirRisk && set.isomir_flag && (
            <div className="rounded-lg bg-purple-50 border border-purple-200 px-3 py-2 space-y-1">
              <p className="text-xs font-semibold text-purple-700">isoMiR Discrimination Risk</p>
              <p className="text-xs text-purple-700">{set.isomir_flag.note}</p>
              <p className="text-xs text-purple-400 italic">{set.isomir_flag.data_warning}</p>
            </div>
          )}

          {/* ── Pre-filter notes (V4 sets only) ── */}
          {prefilterNotes.length > 0 && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
              {prefilterNotes.map((w) => (
                <p key={w} className="text-xs text-amber-700">{PREFILTER_WARNING_TEXT[w]}</p>
              ))}
            </div>
          )}

          {/* ── Off-target check ── */}
          <OffTargetPanel
            forwardPrimer={set.sequence}
            reversePrimer={reverse?.sequence}
            mirnaId={mirnaId ?? ''}
            mirnaSequence={mirnaSequence}
            conditions={conditions}
            species={species}
            rtPrimer={stemloop?.sequence}
            designBlast={tiered ? set.ranking.specificity.blast : null}
            blastAvailable={blastAvailable}
          />

          {/* ── Export ── */}
          <ExportButtons set={set} stemloop={stemloop} reverse={reverse} />
        </div>
      )}
    </div>
  );
}

/** Binding-region Tm below the 39 °C floor (QD 36): in cycle 1 the forward primer
 *  anneals to the cDNA through this region only. Advice only — the ranking and the
 *  grade are unchanged (review panel 2026-11-18, A5). */
function LowBindingTmNote({ set }) {
  if (!set.ranking?.binding_floor_fail) return null;
  const tm = set.ranking.flexible?.binding_tm?.tm_binding;
  return (
    <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2" data-testid="low-binding-tm">
      <span className="font-semibold">Binding-region Tm {tm != null ? `${Number(tm).toFixed(1)} °C` : 'below 39 °C'}:</span>{' '}
      in cycle 1 the forward primer binds the cDNA through this region only. Run the first
      2–3 cycles at Ta ≈ 50 °C, or consider an LNA forward primer.
    </p>
  );
}

function HeterodimersPanel({ checks }) {
  // Fwd × universal reverse is the "Hetero-dimer" row of Structure Checks (same
  // primers, same PCR buffer): only the RT-step pair is added here.
  const pairs = [
    { key: 'heterodimer_fwd_stemloop', label: 'Fwd × RT (stem-loop)', subtitle: 'RT step buffer (Kramer 2011)' },
  ];

  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide px-3 py-2 bg-slate-50 border-b border-slate-200">
        Heterodimer with the RT primer
      </p>
      <div className="divide-y divide-slate-100">
        {pairs.map(({ key, label, subtitle }) => {
          const h = checks[key];
          if (!h) return null;
          const style = RISK_STYLE[h.risk_level] ?? RISK_STYLE.PASS;
          return (
            <div key={key} className="px-3 py-2 flex items-center justify-between gap-3" title={h.note}>
              <div className="min-w-0">
                <p className="text-xs font-medium text-slate-700">{label}</p>
                <p className="text-xs text-slate-500">{subtitle}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-xs font-mono text-slate-600 tabular-nums">
                  ΔG {h.dg?.toFixed(2)} kcal/mol
                </span>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${style}`}>
                  {h.risk_level}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PrimerRow({ label, seq, detail }) {
  return (
    <div className="bg-slate-50 rounded-lg px-3 py-2.5 space-y-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-slate-500 shrink-0">{label}</span>
        <span className="text-xs text-slate-500 truncate min-w-0">{detail}</span>
      </div>
      <p className="font-mono text-xs text-slate-800 break-all">5'–{seq}–3'</p>
    </div>
  );
}
