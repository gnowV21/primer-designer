// TierSummary — grade + the three tiers of one tiered primer set (algorithm 4.0.0).
// docs/SPEC_ui_tiered_4.0.0.md §2.1. Every value comes from the API's `ranking`
// block; tooltips reuse the backend `explanations` and the shared label tables.

import Tooltip from '../../../components/ui/Tooltip.jsx';
import { v4RuleLabel } from '../../../utils/v4Rules.js';
import { vetoedSubIndices } from '../../../utils/tierRank.js';

const GRADE_STYLE = {
  A: 'text-teal-800 bg-teal-50 border-teal-300',
  B: 'text-amber-800 bg-amber-50 border-amber-300',
  C: 'text-red-700 bg-red-50 border-red-300',
};

const GRADE_MEANING = {
  A: 'Grade A: passed the specificity screen with BLAST ≥ 4, assay ΔCq ≥ 3, Tm margin ≥ 4 and no soft veto.',
  B: 'Grade B: passed the specificity screen with a weakness.',
  C: 'Grade C: every candidate failed the specificity screen (specificity fallback).',
};

const fmt = (v, d = 1) => (v == null || Number.isNaN(Number(v)) ? 'n/a' : Number(v).toFixed(d));

/** F4 is a one-sided floor (TIERED_F4_FLOOR, QD 29) or a two-sided target: read the mode. */
const f4IsFloor = (bt) => !bt?.mode || String(bt.mode).startsWith('floor');
const f4Label = (bt) => `${f4IsFloor(bt) ? 'floor' : 'target'} ${fmt(bt?.target, 0)} °C`;
/** F3 specific length is report-only unless the backend scores it. */
const f3ReportOnly = (fx) => fx?.specific_length?.report_only !== false;

/** "A" / "B" / "C" pill; `withTooltip` adds the grade reasons on hover / focus. */
export function GradeBadge({ set, blastAvailable = true, withTooltip = true, size = 'md' }) {
  const g = set?.grade;
  const reasons = set?.grade_reasons || [];
  const text = [GRADE_MEANING[g], ...reasons.map((r) => `• ${r}`)].filter(Boolean).join(' ');
  const pad = size === 'sm' ? 'px-1.5 py-0 text-xs' : 'px-2 py-0.5 text-sm';
  return (
    <span className="inline-flex items-center gap-1" data-testid="grade-badge">
      <span
        className={`font-bold rounded-md border ${pad} ${GRADE_STYLE[g] ?? 'text-slate-700 bg-slate-50 border-slate-300'}`}
        aria-label={`Grade ${g}`}
      >
        {g}{!blastAvailable && g === 'B' ? ' — BLAST unavailable' : ''}
      </span>
      {withTooltip && text && <Tooltip text={text} />}
    </span>
  );
}

function levelTone(score) {
  if (score == null) return 'text-slate-500 bg-slate-50 border-slate-200';
  if (score >= 4) return 'text-teal-800 bg-teal-50 border-teal-200';
  if (score >= 2) return 'text-amber-800 bg-amber-50 border-amber-200';
  return 'text-red-700 bg-red-50 border-red-200';
}

/** One criterion: name, level 1–5, the value behind it. `title` is the hover text. */
function Chip({ name, score, value, title, reportOnly = false }) {
  const tone = reportOnly ? 'text-slate-500 bg-white border-slate-200 border-dashed' : levelTone(score);
  return (
    <span
      className={`inline-flex flex-wrap items-baseline gap-x-1 text-xs rounded-md border px-1.5 py-0.5 max-w-full ${tone}`}
      title={title}
    >
      <span className="font-medium">{name}</span>
      {!reportOnly && <span className="font-semibold tabular-nums">{score == null ? '—' : `L${score}`}</span>}
      {value && <span className="opacity-80 break-words min-w-0">{value}</span>}
    </span>
  );
}

function Tier({ label, total, max, children, testId }) {
  const pct = max ? Math.max(0, Math.min(100, (100 * total) / max)) : 0;
  return (
    <div className="space-y-1.5" data-testid={testId}>
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-slate-600 w-20 shrink-0">{label}</span>
        <div className="h-1.5 flex-1 rounded-full bg-slate-100 overflow-hidden" aria-hidden>
          <div className="h-full rounded-full bg-teal-600" style={{ width: `${pct}%` }} />
        </div>
        <span className="text-xs font-semibold tabular-nums text-slate-700 shrink-0">{total}/{max}</span>
      </div>
      <div className="flex flex-wrap gap-1.5 sm:pl-[5.5rem]">{children}</div>
    </div>
  );
}

/** Warning chips: soft vetoes, V4 rules broken, eliminated (fallback). */
export function TierFlags({ set }) {
  const r = set.ranking;
  const chips = [];
  if (r.eliminated) {
    chips.push({ key: 'elim', tone: 'red', text: 'Fails specificity screen',
      title: 'BLAST CRITICAL or assay ΔCq CO-AMPLIFIED; shown only because every candidate failed (specificity fallback).' });
  }
  if (r.structure_veto) {
    const sub = vetoedSubIndices(set);
    chips.push({ key: 'veto', tone: 'red', text: 'Structure veto: hairpin/dimer at level 1',
      title: `Structure sub-index at level 1${sub.length ? `: ${sub.join(', ')}` : ''}. Ranks below sets with the same specificity.` });
  }
  if (r.binding_floor_fail) {
    chips.push({ key: 'floor', tone: 'amber', text: 'Binding Tm < 39 °C',
      title: set.explanations?.tm_binding_accuracy || 'Specific-region Tm below the 39 °C floor (F4 level 1).' });
  }
  for (const code of set.v4_rule_violations || []) {
    // Readable rule in the chip, the code in the hover text (review panel: no raw codes).
    chips.push({ key: code, tone: 'slate', text: `Outside V4 rule: ${v4RuleLabel(code)}`, title: code });
  }
  if (!chips.length) return null;
  const TONE = {
    red: 'text-red-700 bg-red-50 border-red-200',
    amber: 'text-amber-800 bg-amber-50 border-amber-200',
    slate: 'text-slate-700 bg-slate-50 border-slate-300',
  };
  return (
    <div className="flex flex-wrap gap-1.5" data-testid="tier-flags">
      {chips.map((c) => (
        <span key={c.key} title={c.title}
          className={`text-xs font-medium rounded-full border px-2 py-0.5 max-w-full break-words ${TONE[c.tone]}`}>
          {c.text}
        </span>
      ))}
    </div>
  );
}

export default function TierSummary({ set, blastAvailable = true }) {
  const r = set.ranking;
  const sp = r.specificity;
  const pcr = r.pcr;
  const fx = r.flexible;
  const ex = set.explanations || {};
  const blastRun = blastAvailable && sp.blast?.score != null;
  const st = fx.structure || {};
  const sub = st.sub_scores || {};

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 sm:px-4 py-3 space-y-3" data-testid="tier-summary">
      <div className="flex flex-wrap items-center gap-2">
        <GradeBadge set={set} blastAvailable={blastAvailable} />
        <span className="text-xs text-slate-500">
          {set.grade_basis === 'tiers (QD 30)' ? 'Grade from the tiers' : set.grade_basis}
          {' · '}criterion levels L1–L5, L5 best
        </span>
      </div>

      <TierFlags set={set} />

      <Tier label="Specificity" total={sp.total} max={sp.max} testId="tier-specificity">
        <Chip
          name="S1 BLAST"
          score={blastRun ? sp.blast.score : null}
          value={blastRun ? `${sp.blast.overall_risk}${sp.blast.worst_hit ? ` · ${sp.blast.worst_hit}` : ''}` : 'not run'}
          title={blastRun
            ? 'Same-species BLAST of the forward primer, with the RT step (classifier v7).'
            : 'BLAST was not run: specificity ranking reduced to S2 + S3.'}
        />
        <Chip
          name="S2 ΔCq"
          score={sp.assay_dcq?.score}
          value={`${sp.assay_dcq?.min_delta_cq == null ? '> 10' : fmt(sp.assay_dcq.min_delta_cq)}${sp.assay_dcq?.worst_target ? ` · ${sp.assay_dcq.worst_target}` : ''}`}
          title={ex.min_delta_cq}
        />
        <Chip
          name="S3 Tm margin"
          score={sp.tm_margin?.score}
          value={`${fmt(sp.tm_margin?.margin)} °C${sp.tm_margin?.worst_target ? ` · ${sp.tm_margin.worst_target}` : ''}`}
          title={ex.tm_margin}
        />
      </Tier>

      <Tier label="PCR" total={pcr.total} max={pcr.max} testId="tier-pcr">
        <Chip name="P2 |Tm − Ta|" score={pcr.tm_vs_ta?.score} value={`${fmt(pcr.tm_vs_ta?.diff)} °C`} title={ex.tm_accuracy} />
        <Chip name="P1 Tm pair" reportOnly value={`report only · ${fmt(pcr.tm_pair?.diff)} °C`}
          title="Forward vs universal reverse Tm. Report only: with a fixed reverse primer it opposes P2." />
      </Tier>

      <Tier label="Flexible" total={fx.total} max={fx.max} testId="tier-flexible">
        <Chip name="F1 GC" score={fx.gc?.score} value={`${fmt(fx.gc?.gc_percent)} %`} title={ex.gc_content} />
        <Chip name="F2 GC clamp" score={fx.gc_clamp?.score} value={fx.gc_clamp?.last5} title={ex.gc_clamp} />
        <Chip name="F4 binding Tm" score={fx.binding_tm?.score}
          value={`${fmt(fx.binding_tm?.tm_binding)} °C · ${f4Label(fx.binding_tm)}`}
          title={ex.tm_binding_accuracy} />
        {!f3ReportOnly(fx) && (
          <Chip name="F3 length" score={fx.specific_length?.score}
            value={`${fx.specific_length?.length ?? set.specific_length} nt`} />
        )}
        <Chip name="F5 structure" score={st.score}
          value={`min of hairpin ${sub.hairpin_tm ?? '—'}, dimer ${sub.dimer_dg ?? '—'}, 3′ dimer ${sub.end_dimer_tm ?? '—'}`}
          title={ex.structure} />
      </Tier>
    </div>
  );
}

// ── Detail table (collapsed): every criterion with value, level and explanation ──

export function TierDetailTable({ set }) {
  const r = set.ranking;
  const sp = r.specificity;
  const pcr = r.pcr;
  const fx = r.flexible;
  const ex = set.explanations || {};
  const rows = [
    ['S1 BLAST', sp.blast?.score, sp.blast?.overall_risk ?? 'not run',
      sp.blast?.worst_hit ? `Worst hit ${sp.blast.worst_hit}.` : ''],
    ['S2 assay ΔCq', sp.assay_dcq?.score,
      `${sp.assay_dcq?.min_delta_cq == null ? '> 10' : fmt(sp.assay_dcq.min_delta_cq)} (${sp.assay_dcq?.label})`, ex.min_delta_cq],
    ['S3 Tm margin', sp.tm_margin?.score, `${fmt(sp.tm_margin?.margin)} °C`, ex.tm_margin],
    ['P2 |Tm − Ta|', pcr.tm_vs_ta?.score, `${fmt(pcr.tm_vs_ta?.diff, 2)} °C`, ex.tm_accuracy],
    ['P1 Tm pair (report only)', null, `${fmt(pcr.tm_pair?.diff, 2)} °C`, ''],
    ['F1 GC', fx.gc?.score, `${fmt(fx.gc?.gc_percent)} %`, ex.gc_content],
    ['F2 GC clamp', fx.gc_clamp?.score, fx.gc_clamp?.last5, ex.gc_clamp],
    [`F3 specific length${f3ReportOnly(fx) ? ' (report only)' : ''}`,
      f3ReportOnly(fx) ? null : fx.specific_length?.score,
      `${fx.specific_length?.length ?? set.specific_length} nt`, ''],
    [`F4 binding Tm (${f4Label(fx.binding_tm)})`, fx.binding_tm?.score, `${fmt(fx.binding_tm?.tm_binding)} °C`, ex.tm_binding_accuracy],
    ['F5 structure', fx.structure?.score,
      `hairpin Tm ${fmt(fx.structure?.hairpin_tm)} °C · dimer ΔG ${fmt(fx.structure?.dimer_dg)} · 3′ dimer Tm ${fmt(fx.structure?.end_dimer_tm)} °C`,
      ex.structure],
  ];
  return (
    <details className="group rounded-lg border border-slate-200" data-testid="tier-detail">
      <summary className="cursor-pointer list-none px-3 py-2 text-xs font-semibold text-slate-600 hover:text-teal-700">
        <span className="inline-block transition-transform group-open:rotate-90">▸</span> Criteria detail
      </summary>
      <div className="overflow-x-auto border-t border-slate-200">
        <table className="w-full text-xs">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left px-2 py-1.5 font-semibold text-slate-600">Criterion</th>
              <th className="text-left px-2 py-1.5 font-semibold text-slate-600">Value</th>
              <th className="text-center px-2 py-1.5 font-semibold text-slate-600">Level</th>
              <th className="text-left px-2 py-1.5 font-semibold text-slate-600 hidden sm:table-cell">Explanation</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map(([name, lvl, val, why]) => (
              <tr key={name}>
                <td className="px-2 py-1.5 text-slate-700">{name}</td>
                <td className="px-2 py-1.5 text-slate-700 tabular-nums break-words">{val ?? '—'}</td>
                <td className="px-2 py-1.5 text-center tabular-nums font-semibold text-slate-700">{lvl ?? '—'}</td>
                <td className="px-2 py-1.5 text-slate-500 hidden sm:table-cell">{why}</td>
              </tr>
            ))}
            <tr className="bg-slate-50">
              <td className="px-2 py-1.5 text-slate-700" colSpan={2}>
                Tie-break score — used only when all tiers are equal
              </td>
              <td className="px-2 py-1.5 text-center tabular-nums font-semibold text-slate-700" data-testid="tie-break-score">
                {fmt(r.detailed_score)}
              </td>
              <td className="hidden sm:table-cell" />
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  );
}
