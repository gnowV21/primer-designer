// PrimerSetCard — displays one ranked primer set (forward + stemloop RT + universal reverse).

import ScoreGauge from './ScoreGauge.jsx';
import ScoreBreakdown from './ScoreBreakdown.jsx';
import StructureChecks from './StructureChecks.jsx';
import ExportButtons from './ExportButtons.jsx';
import OffTargetPanel from './OffTargetPanel.jsx';
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

const PREFILTER_WARNING_TEXT = {
  t_at_3prime_warning: "3′ end is T — may reduce polymerase efficiency slightly",
  gc_clamp_weak_warning: "Only 1 G/C in the last 3 nt (weak GC clamp). The 3′ end is set by the miRNA sequence; scored 75/100 on the GC-clamp criterion",
};

const RISK_STYLE = {
  HIGH:     'text-red-700 bg-red-50 border-red-300',
  MODERATE: 'text-orange-700 bg-orange-50 border-orange-300',
  LOW:      'text-amber-700 bg-amber-50 border-amber-200',
  PASS:     'text-teal-700 bg-teal-50 border-teal-200',
};

export default function PrimerSetCard({ set, stemloop, reverse, mirnaId, mirnaSequence, conditions, species }) {
  const [expanded, setExpanded] = useState(set.rank === 1);

  const rankColors = ['text-teal-700 bg-teal-50 border-teal-300', 'text-slate-700 bg-slate-50 border-slate-300', 'text-slate-600 bg-slate-50 border-slate-300'];
  const rankColor  = rankColors[(set.rank || 1) - 1] ?? rankColors[2];
  const isomirRisk = set.isomir_flag?.isomir_discrimination_risk;
  const selection  = SELECTION_LABEL[set.selection];

  return (
    <div className={`rounded-2xl border shadow-sm ${set.rank === 1 ? 'border-teal-300 shadow-teal-100' : 'border-slate-200'}`}>
      {/* ── Card header ── */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
      >
        <div className="flex items-center gap-3">
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
          <div>
            <p className="text-sm font-semibold text-slate-800 font-mono">{set.sequence}</p>
            <p className="text-xs text-slate-500 mt-0.5 tabular-nums">
              {set.length} nt · Tm {set.tm_full?.toFixed(1)}°C · GC {set.gc_percent}%
              {set.amplicon_size && ` · ~${set.amplicon_size} bp amplicon`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4 shrink-0">
          <ScoreGauge score={set.total_score} grade={set.grade} compact />
          <span className="text-slate-500 text-sm">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-slate-100 px-5 py-4 space-y-5">
          {/* ── Primer sequences ── */}
          <div className="grid gap-2">
            <PrimerRow label="Forward" seq={set.sequence} detail={`Binding: ${set.specific_region || '—'} (${set.specific_length} nt)`} />
            {stemloop && <PrimerRow label="RT (stem-loop)" seq={stemloop.sequence} detail={`Tm ${stemloop.tm_full?.toFixed(1)}°C · MFE ${stemloop.mfe?.toFixed(2)} kcal/mol`} />}
            {reverse  && <PrimerRow label="Reverse (universal)" seq={reverse.sequence}  detail={`Tm ${reverse.tm?.toFixed(1)}°C · GC ${reverse.gc_percent}%`} />}
          </div>

          {/* ── Score + structure ── */}
          <div className="grid md:grid-cols-2 gap-5">
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

          {/* ── Warnings ── */}
          {(set.warnings_from_prefilter || []).length > 0 && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
              <p className="text-xs font-semibold text-amber-700 mb-1">Warnings</p>
              {set.warnings_from_prefilter.map((w) => (
                <p key={w} className="text-xs text-amber-700">
                  • {PREFILTER_WARNING_TEXT[w] ?? w}
                </p>
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
          />

          {/* ── Export ── */}
          <ExportButtons set={set} stemloop={stemloop} reverse={reverse} />
        </div>
      )}
    </div>
  );
}

function HeterodimersPanel({ checks }) {
  const pairs = [
    { key: 'heterodimer_fwd_stemloop', label: 'Fwd × RT (stem-loop)', subtitle: 'RT step buffer (Kramer 2011)' },
    { key: 'heterodimer_fwd_reverse',  label: 'Fwd × Universal Rev',  subtitle: 'PCR step buffer (user params)' },
  ];

  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide px-3 py-2 bg-slate-50 border-b border-slate-200">
        Heterodimer Check
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
        <span className="text-xs text-slate-500 truncate">{detail}</span>
      </div>
      <p className="font-mono text-xs text-slate-800 break-all">5'–{seq}–3'</p>
    </div>
  );
}
