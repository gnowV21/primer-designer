// TierSummary — grade + the criteria groups of one tiered primer set (algorithm 4.0.0).
// Groups as presented since 2026-11-22 (utils/criteriaGroups.js): Required (assay
// structure, forward Tm window, specificity S1–S3) and Flexible (1. No critical weakness,
// 2. PCR, 3. Composition & structure). Display only — every value comes from the API's
// `ranking` block, unchanged; tooltips reuse the backend `explanations`.

import Tooltip from '../../../components/ui/Tooltip.jsx';
import { F4_NOTE, GROUP, NCW_TOOLTIP, ncwFailures } from '../../../utils/criteriaGroups.js';

const GRADE_STYLE = {
  A: 'text-teal-800 bg-teal-50 border-teal-300',
  B: 'text-amber-800 bg-amber-50 border-amber-300',
  C: 'text-red-700 bg-red-50 border-red-300',
};

const GRADE_MEANING = {
  A: 'Grade A: passed the specificity screen with S1 BLAST ≥ 4, S2 assay ΔCq ≥ 3, S3 Tm margin ≥ 4, secondary structure not too strong and cycle-1 binding Tm ≥ 39 °C.',
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

/** One criterion: name, level 1–5, the value behind it. `title` is the hover text.
 *  notScored: a value shown for information, labelled "not scored". */
function Chip({ name, score, value, title, notScored = false, testId }) {
  const tone = notScored ? 'text-slate-600 bg-white border-slate-200 border-dashed' : levelTone(score);
  return (
    <span
      className={`inline-flex flex-wrap items-baseline gap-x-1 text-xs rounded-md border px-1.5 py-0.5 max-w-full ${tone}`}
      title={title}
      data-testid={testId}
    >
      <span className="font-medium">{name}</span>
      {!notScored && <span className="font-semibold tabular-nums">{score == null ? '—' : `L${score}`}</span>}
      {value && <span className="opacity-80 break-words min-w-0">{value}</span>}
      {notScored && <span className="text-slate-500 italic">not scored</span>}
    </span>
  );
}

/** A check every returned set passes by construction: a tick and its text. */
function Check({ children, title, testId }) {
  return (
    <p className="text-xs text-slate-700 flex items-baseline gap-1.5" title={title} data-testid={testId}>
      <span className="text-teal-700 font-bold" aria-hidden>✓</span>
      <span className="min-w-0">{children}</span>
    </p>
  );
}

/** A level bar with its total, and the criterion chips below it. */
function Bar({ label, hint, total, max, testId, children }) {
  const pct = max ? Math.max(0, Math.min(100, (100 * total) / max)) : 0;
  return (
    <div className="space-y-1.5" data-testid={testId}>
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-slate-600 sm:w-44 shrink-0">
          {label}{hint && <span className="font-normal text-slate-500"> · {hint}</span>}
        </span>
        <div className="h-1.5 flex-1 rounded-full bg-slate-100 overflow-hidden" aria-hidden>
          <div className="h-full rounded-full bg-teal-600" style={{ width: `${pct}%` }} />
        </div>
        <span className="text-xs font-semibold tabular-nums text-slate-700 shrink-0">{total}/{max}</span>
      </div>
      <div className="flex flex-wrap gap-1.5 sm:pl-[11.5rem]">{children}</div>
    </div>
  );
}

function GroupBlock({ title, testId, tone = 'slate', children }) {
  return (
    <section className={`rounded-lg border px-3 py-2.5 space-y-2 ${tone === 'red' ? 'border-red-200' : 'border-slate-200'}`}
      data-testid={testId}>
      <h4 className="text-xs font-bold uppercase tracking-wide text-slate-500">{title}</h4>
      {children}
    </section>
  );
}

const CHIP_TONE = {
  structure_veto: 'text-red-700 bg-red-50 border-red-200',
  binding_floor_fail: 'text-amber-800 bg-amber-50 border-amber-200',
  rule: 'text-slate-700 bg-slate-50 border-slate-300',
};

/** Flexible 1: one line, "No critical weakness"; a chip per failed condition. */
export function NoCriticalWeakness({ set }) {
  const fails = ncwFailures(set);
  return (
    <div className="space-y-1.5" data-testid="ncw">
      <p className="text-xs text-slate-700 flex flex-wrap items-center gap-1.5">
        <span className="font-semibold text-slate-600">1. {GROUP.ncw}</span>
        <Tooltip text={NCW_TOOLTIP} />
        {fails.length === 0
          ? <span className="text-teal-700 font-medium" data-testid="ncw-pass">✓ passed</span>
          : <span className="text-amber-800 font-medium" data-testid="ncw-fail">not met</span>}
      </p>
      {fails.length > 0 && (
        <div className="flex flex-wrap gap-1.5 sm:pl-4" data-testid="tier-flags">
          {fails.map((f) => (
            <span key={f.key} title={f.title}
              className={`text-xs font-medium rounded-full border px-2 py-0.5 max-w-full break-words ${CHIP_TONE[f.key] || CHIP_TONE.rule}`}>
              {f.text}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * tmWindow: [tmMin, tmMax] the run used (metadata.design_settings.tm_target_c), or null
 * for an API request without one (backend default 58–62 °C).
 * onExplain: opens the criteria panel.
 */
export default function TierSummary({ set, blastAvailable = true, tmWindow = null, onExplain }) {
  const r = set.ranking;
  const sp = r.specificity;
  const pcr = r.pcr;
  const fx = r.flexible;
  const ex = set.explanations || {};
  const blastRun = blastAvailable && sp.blast?.score != null;
  const st = fx.structure || {};
  const sub = st.sub_scores || {};
  const [lo, hi] = tmWindow && tmWindow[0] != null && tmWindow[1] != null ? tmWindow : [58, 62];
  const occupancy = set.scores?.bound_fraction_binding_pct;

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 sm:px-4 py-3 space-y-3" data-testid="tier-summary">
      <div className="flex flex-wrap items-center gap-2">
        <GradeBadge set={set} blastAvailable={blastAvailable} />
        <span className="text-xs text-slate-500">criterion levels L1–L5, L5 best</span>
        {onExplain && (
          <button type="button" onClick={onExplain} data-testid="open-criteria"
            className="ml-auto text-xs font-medium text-teal-700 underline decoration-dotted underline-offset-2 hover:text-teal-900">
            How sets are ranked
          </button>
        )}
      </div>

      {/* ── Required ── */}
      <GroupBlock title={GROUP.required} testId="group-required" tone={r.eliminated ? 'red' : 'slate'}>
        <Check testId="req-structure"
          title="RT primer = 44-nt stem-loop body + 3′ overhang complementary to the miRNA 3′ end; forward primer = 5′ tail + miRNA 5′ region; fixed universal reverse primer (Chen et al. 2005).">
          Built to the Chen 2005 assay structure
        </Check>
        <Check testId="req-tm-window" title="Hard limit: candidates outside the forward-primer Tm window are not generated.">
          Forward Tm {fmt(set.tm_full)} °C, inside the Tm window {lo}–{hi} °C
        </Check>
        {r.eliminated && (
          <p className="text-xs font-medium text-red-700" data-testid="req-fallback">
            ✕ Fails the specificity screen (BLAST CRITICAL or assay ΔCq CO-AMPLIFIED). Shown only because
            every candidate failed (specificity fallback).
          </p>
        )}
        <Bar label="Specificity" hint="ranks first" total={sp.total} max={sp.max} testId="tier-specificity">
          <Chip
            name="S1 BLAST"
            score={blastRun ? sp.blast.score : null}
            value={blastRun ? `${sp.blast.overall_risk}${sp.blast.worst_hit ? ` · ${sp.blast.worst_hit}` : ''}` : 'not run'}
            title={blastRun
              ? 'Same-species BLAST of the forward primer, with the RT step (classifier v7). CRITICAL is eliminated.'
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
        </Bar>
      </GroupBlock>

      {/* ── Flexible: 1 → 2 → 3, the order of the ranking key ── */}
      <GroupBlock title={GROUP.flexible} testId="group-flexible">
        <NoCriticalWeakness set={set} />

        <Bar label={`2. ${GROUP.pcr}`} total={pcr.total} max={pcr.max} testId="tier-pcr">
          <Chip name="P2 |Tm − Ta|" score={pcr.tm_vs_ta?.score} value={`${fmt(pcr.tm_vs_ta?.diff)} °C`} title={ex.tm_accuracy} />
          <Chip name="ΔTm F–R" notScored value={`${fmt(pcr.tm_pair?.diff, 2)} °C`} testId="dtm-fr"
            title="Forward vs universal reverse Tm. ΔTm F–R ≈ Tm_R − Ta: set by Ta and reaction conditions, the same for every set." />
          {occupancy != null && (
            <Chip name="Cycle-1 occupancy" notScored value={`${fmt(occupancy, 2)} %`}
              title="Bound fraction of the miRNA-binding region on the cDNA at Ta (PCR cycle 1)." />
          )}
          {set.predicted_amplicon_tm != null && (
            <Chip name="Amplicon Tm" notScored value={`${fmt(set.predicted_amplicon_tm)} °C`}
              title="Predicted melt peak of the product (empirical long-duplex formula)." />
          )}
        </Bar>

        <Bar label={`3. ${GROUP.composition}`} total={fx.total} max={fx.max} testId="tier-flexible">
          <Chip name="F1 GC" score={fx.gc?.score} value={`${fmt(fx.gc?.gc_percent)} %`} title={ex.gc_content} />
          <Chip name="F2 GC clamp" score={fx.gc_clamp?.score} value={fx.gc_clamp?.last5} title={ex.gc_clamp} />
          <Chip name="F4 binding Tm" score={fx.binding_tm?.score} testId="chip-f4"
            value={`${fmt(fx.binding_tm?.tm_binding)} °C · ${f4Label(fx.binding_tm)}`}
            title={`${F4_NOTE}. ${ex.tm_binding_accuracy || ''}`} />
          <Chip name="F5 structure" score={st.score}
            value={`min of hairpin ${sub.hairpin_tm ?? '—'}, dimer ${sub.dimer_dg ?? '—'}, 3′ dimer ${sub.end_dimer_tm ?? '—'}`}
            title={ex.structure} />
          {f3ReportOnly(fx) ? (
            <Chip name="F3 length" notScored value={`${fx.specific_length?.length ?? set.specific_length} nt`} />
          ) : (
            <Chip name="F3 length" score={fx.specific_length?.score}
              value={`${fx.specific_length?.length ?? set.specific_length} nt`} />
          )}
        </Bar>
        <p className="text-xs text-slate-500 sm:pl-[11.5rem]" data-testid="f4-note">F4: {F4_NOTE}.</p>
      </GroupBlock>
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
  const fails = ncwFailures(set);
  const groups = [
    [GROUP.required, [
      ['S1 BLAST', sp.blast?.score, sp.blast?.overall_risk ?? 'not run',
        sp.blast?.worst_hit ? `Worst hit ${sp.blast.worst_hit}.` : ''],
      ['S2 assay ΔCq', sp.assay_dcq?.score,
        `${sp.assay_dcq?.min_delta_cq == null ? '> 10' : fmt(sp.assay_dcq.min_delta_cq)} (${sp.assay_dcq?.label})`, ex.min_delta_cq],
      ['S3 Tm margin', sp.tm_margin?.score, `${fmt(sp.tm_margin?.margin)} °C`, ex.tm_margin],
    ]],
    [`${GROUP.flexible} · 1. ${GROUP.ncw}`, [
      [GROUP.ncw, null, fails.length ? fails.map((f) => f.text).join('; ') : 'passed', NCW_TOOLTIP],
    ]],
    [`${GROUP.flexible} · 2. ${GROUP.pcr}`, [
      ['P2 |Tm − Ta|', pcr.tm_vs_ta?.score, `${fmt(pcr.tm_vs_ta?.diff, 2)} °C`, ex.tm_accuracy],
      ['ΔTm F–R (not scored)', null, `${fmt(pcr.tm_pair?.diff, 2)} °C`,
        'ΔTm F–R ≈ Tm_R − Ta: set by Ta and reaction conditions, the same for every set.'],
    ]],
    [`${GROUP.flexible} · 3. ${GROUP.composition}`, [
      ['F1 GC', fx.gc?.score, `${fmt(fx.gc?.gc_percent)} %`, ex.gc_content],
      ['F2 GC clamp', fx.gc_clamp?.score, fx.gc_clamp?.last5, ex.gc_clamp],
      [`F4 binding Tm (${f4Label(fx.binding_tm)})`, fx.binding_tm?.score, `${fmt(fx.binding_tm?.tm_binding)} °C`,
        `${F4_NOTE}. ${ex.tm_binding_accuracy || ''}`],
      ['F5 structure', fx.structure?.score,
        `hairpin Tm ${fmt(fx.structure?.hairpin_tm)} °C · dimer ΔG ${fmt(fx.structure?.dimer_dg)} · 3′ dimer Tm ${fmt(fx.structure?.end_dimer_tm)} °C`,
        ex.structure],
      [`F3 specific length${f3ReportOnly(fx) ? ' (not scored)' : ''}`,
        f3ReportOnly(fx) ? null : fx.specific_length?.score,
        `${fx.specific_length?.length ?? set.specific_length} nt`, ''],
    ]],
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
          {groups.map(([title, rows]) => (
            <tbody key={title} className="divide-y divide-slate-100">
              <tr className="bg-slate-50">
                <th colSpan={4} className="text-left px-2 py-1 text-[11px] font-bold uppercase tracking-wide text-slate-500">{title}</th>
              </tr>
              {rows.map(([name, lvl, val, why]) => (
                <tr key={name}>
                  <td className="px-2 py-1.5 text-slate-700">{name}</td>
                  <td className="px-2 py-1.5 text-slate-700 tabular-nums break-words">{val ?? '—'}</td>
                  <td className="px-2 py-1.5 text-center tabular-nums font-semibold text-slate-700">{lvl ?? '—'}</td>
                  <td className="px-2 py-1.5 text-slate-500 hidden sm:table-cell">{why}</td>
                </tr>
              ))}
            </tbody>
          ))}
          <tbody>
            <tr className="bg-slate-50">
              <td className="px-2 py-1.5 text-slate-700" colSpan={2}>
                Tie-break score — used only when every group is equal
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
