// TierSummary — grade + the criteria groups of one tiered primer set (algorithm 4.0.0).
// Groups as presented since 2026-11-22 (utils/criteriaGroups.js): Required (assay
// structure, forward Tm window, specificity S1–S3) and Flexible (1. No critical weakness,
// 2. PCR, 3. Composition & structure). Display only — every value comes from the API's
// `ranking` block, unchanged; tooltips reuse the backend `explanations`.

import Tooltip from '../../../components/ui/Tooltip.jsx';
import { F4_NOTE, GROUP, NCW_TOOLTIP, ncwFailures, standardRuleLabels } from '../../../utils/criteriaGroups.js';
import { levelWord, STATUS_CLASSES } from '../../../utils/format.js';

const GRADE_STYLE = {
  A: 'text-green-800 bg-green-50 border-green-300',
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
const f4Label = (bt) => `${f4IsFloor(bt) ? 'floor' : 'target'} ${fmt(bt?.target, 0)}\u00a0°C`;
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

const NB = ' ';
const deg = (v, d = 1) => `${fmt(v, d)}${NB}°C`;

/** Level 1–5 → the status vocabulary: 4–5 Pass, 2–3 Warning, 1 Fail. */
function levelStatus(score) {
  if (score == null) return '';
  if (score >= 4) return 'Pass';
  if (score >= 2) return 'Warning';
  return 'Fail';
}

/** A status word in its colour (never the brand colour); "Info" for values not scored. */
function Status({ status, info = false }) {
  if (info) return <span className="text-xs font-medium text-slate-600 shrink-0">Not scored</span>;
  if (!status) return <span className="text-xs font-medium text-slate-600 shrink-0">Not run</span>;
  return (
    <span className={`text-xs font-semibold rounded border px-1.5 py-0.5 shrink-0 ${STATUS_CLASSES[status]}`}>
      {status}
    </span>
  );
}

/** One criterion in plain words: label · value · status. Codes and levels are in "Criteria detail". */
function Row({ label, value, status, info = false, title, testId, children }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1" title={title} data-testid={testId}>
      <div className="min-w-0 text-xs">
        <span className="text-slate-700">{label}</span>
        {value != null && value !== '' && <span className="ml-2 font-medium text-slate-900 tabular-nums">{value}</span>}
        {children}
      </div>
      <Status status={status} info={info} />
    </div>
  );
}

/** A group heading with its total and a thin level bar (no box). */
function GroupHead({ label, total, max }) {
  const pct = max ? Math.max(0, Math.min(100, (100 * total) / max)) : 0;
  return (
    <div className="flex items-center gap-2 pt-1">
      <span className="text-xs font-semibold text-slate-800 shrink-0">{label}</span>
      <div className="h-1.5 flex-1 rounded-full bg-slate-100 overflow-hidden" aria-hidden>
        <div className="h-full rounded-full bg-teal-600" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold tabular-nums text-slate-800 shrink-0">{total}/{max}</span>
    </div>
  );
}

/** Flexible 1, "No critical weakness": one line. When a condition fails, the line names it
 *  in plain words ("Standard primer rules: 1 not met (3′ GC clamp missing)"), no double negative. */
export function NoCriticalWeakness({ set }) {
  const fails = ncwFailures(set);
  const rules = (set?.v4_rule_violations || []);
  const parts = [];
  for (const f of fails) {
    if (f.key === 'structure_veto') parts.push(f.text);
    else if (f.key === 'binding_floor_fail') parts.push(f.text);
  }
  if (rules.length) {
    parts.push(`Standard primer rules: ${rules.length} not met (${standardRuleLabels(set).join(', ')})`);
  }
  const worst = fails.some((f) => f.key === 'structure_veto') ? 'Fail' : (fails.length ? 'Warning' : 'Pass');
  return (
    <div data-testid="ncw">
      <Row label={<span className="inline-flex items-center gap-1">1. {GROUP.ncw}<Tooltip text={NCW_TOOLTIP} /></span>}
        status={worst}>
        {fails.length === 0
          ? <span className="sr-only" data-testid="ncw-pass">passed</span>
          : <span className="sr-only" data-testid="ncw-fail">not met</span>}
      </Row>
      {parts.length > 0 && (
        <ul className="text-xs text-slate-800 pl-3 space-y-0.5" data-testid="tier-flags">
          {parts.map((p) => <li key={p}>{p}</li>)}
        </ul>
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
  const [lo, hi] = tmWindow && tmWindow[0] != null && tmWindow[1] != null ? tmWindow : [58, 62];
  const occupancy = set.scores?.bound_fraction_binding_pct;
  const dcq = sp.assay_dcq?.min_delta_cq;

  return (
    <div className="space-y-3" data-testid="tier-summary">
      <div className="flex flex-wrap items-center gap-2">
        <GradeBadge set={set} blastAvailable={blastAvailable} />
        {onExplain && (
          <button type="button" onClick={onExplain} data-testid="open-criteria"
            className="ml-auto text-xs font-medium text-teal-700 underline decoration-dotted underline-offset-2 hover:text-teal-900">
            How sets are ranked
          </button>
        )}
      </div>

      {/* ── Required ── */}
      <section className="space-y-0.5" data-testid="group-required">
        <h4 className="text-xs font-bold text-slate-800 border-b border-slate-200 pb-1">{GROUP.required}</h4>
        <Row testId="req-structure" label="Built to the Chen 2005 assay structure" status="Pass"
          title="RT primer = 44-nt stem-loop body + 3′ overhang complementary to the miRNA 3′ end; forward primer = 5′ tail + miRNA 5′ region; fixed universal reverse primer (Chen et al. 2005)." />
        <Row testId="req-tm-window" label={<>Forward Tm {deg(set.tm_full)}, inside the Tm window {lo}–{hi}{NB}°C</>} status="Pass"
          title="Hard limit: candidates outside the forward-primer Tm window are not generated." />
        {r.eliminated && (
          <p className="text-xs font-medium text-red-700" data-testid="req-fallback">
            Fails the specificity screen (BLAST critical hit or a co-amplified miRNA). Shown only because
            every candidate failed (specificity fallback).
          </p>
        )}
        <div data-testid="tier-specificity">
          <GroupHead label="Specificity" total={sp.total} max={sp.max} />
          <Row label="BLAST off-target screen"
            value={blastRun ? `${levelWord(sp.blast.overall_risk)}${sp.blast.worst_hit ? `, worst hit ${sp.blast.worst_hit}` : ''}` : 'not run'}
            status={blastRun ? levelStatus(sp.blast.score) : ''}
            title={blastRun
              ? 'Same-species BLAST of the forward primer, with the RT step. A critical hit is eliminated.'
              : 'BLAST was not run: specificity ranking reduced to the assay ΔCq and the Tm margin.'} />
          <Row label="Closest other miRNA, assay ΔCq"
            value={<>{dcq == null ? '> 10' : fmt(dcq)}{sp.assay_dcq?.worst_target && <span className="whitespace-nowrap">{` (${sp.assay_dcq.worst_target})`}</span>}</>}
            status={levelStatus(sp.assay_dcq?.score)} title={ex.min_delta_cq} />
          <Row label="Tm margin over the closest other miRNA"
            value={deg(sp.tm_margin?.margin)}
            status={levelStatus(sp.tm_margin?.score)} title={ex.tm_margin} />
        </div>
      </section>

      {/* ── Flexible: 1 → 2 → 3, the order of the ranking key ── */}
      <section className="space-y-0.5" data-testid="group-flexible">
        <h4 className="text-xs font-bold text-slate-800 border-b border-slate-200 pb-1">{GROUP.flexible}</h4>
        <NoCriticalWeakness set={set} />

        <div data-testid="tier-pcr">
          <GroupHead label={`2. ${GROUP.pcr}`} total={pcr.total} max={pcr.max} />
          <Row label="Forward Tm vs Ta" value={`${deg(pcr.tm_vs_ta?.diff)} apart`}
            status={levelStatus(pcr.tm_vs_ta?.score)} title={ex.tm_accuracy} />
          <Row testId="dtm-fr" label="Forward vs reverse Tm" value={deg(pcr.tm_pair?.diff, 2)} info
            title="About Tm (reverse) − Ta: set by Ta and the reaction conditions, the same for every set (not scored)." />
          {occupancy != null && (
            <Row label="Cycle-1 occupancy at Ta" value={`${fmt(occupancy, 2)}% of primer bound`} info
              title="Bound fraction of the miRNA-binding region on the cDNA at Ta (PCR cycle 1)." />
          )}
          {set.predicted_amplicon_tm != null && (
            <Row label="Predicted amplicon Tm" value={deg(set.predicted_amplicon_tm)} info
              title="Predicted melt peak of the product (empirical long-duplex formula)." />
          )}
        </div>

        <div data-testid="tier-flexible">
          <GroupHead label={`3. ${GROUP.composition}`} total={fx.total} max={fx.max} />
          <Row label="GC content" value={`${fmt(fx.gc?.gc_percent)}%`} status={levelStatus(fx.gc?.score)} title={ex.gc_content} />
          <Row label="3′ GC clamp (last 5 nt)" value={<span className="seq">{fx.gc_clamp?.last5}</span>}
            status={levelStatus(fx.gc_clamp?.score)} title={ex.gc_clamp} />
          <Row testId="chip-f4" label="Binding-region Tm (PCR cycle 1)"
            value={`${deg(fx.binding_tm?.tm_binding)}, ${f4Label(fx.binding_tm)}`}
            status={levelStatus(fx.binding_tm?.score)} title={`${F4_NOTE}. ${ex.tm_binding_accuracy || ''}`} />
          <Row label="Secondary structure (hairpin, dimers)" value={st.score != null ? `level ${st.score} of 5` : ''}
            status={levelStatus(st.score)} title={ex.structure} />
          <Row label="miRNA-specific length" value={`${fx.specific_length?.length ?? set.specific_length}${NB}nt`}
            info={f3ReportOnly(fx)} status={f3ReportOnly(fx) ? undefined : levelStatus(fx.specific_length?.score)} />
          <p className="text-xs text-slate-600" data-testid="f4-note">Binding-region Tm: {F4_NOTE}.</p>
        </div>
      </section>
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
      ['ΔTm forward–reverse (not scored)', null, `${fmt(pcr.tm_pair?.diff, 2)} °C`,
        'About Tm (reverse) − Ta: set by Ta and the reaction conditions, the same for every set.'],
    ]],
    [`${GROUP.flexible} · 3. ${GROUP.composition}`, [
      ['F1 GC', fx.gc?.score, `${fmt(fx.gc?.gc_percent)} %`, ex.gc_content],
      ['F2 GC clamp', fx.gc_clamp?.score, fx.gc_clamp?.last5, ex.gc_clamp],
      [`F4 binding Tm (${f4Label(fx.binding_tm)})`, fx.binding_tm?.score, `${fmt(fx.binding_tm?.tm_binding)} °C`,
        `${F4_NOTE}. ${ex.tm_binding_accuracy || ''}`],
      ['F5 structure', fx.structure?.score,
        `hairpin Tm ${fmt(fx.structure?.hairpin_tm)} °C · dimer ΔG ${fmt(fx.structure?.dimer_dg)} kcal/mol · 3′ dimer Tm ${fmt(fx.structure?.end_dimer_tm)} °C`,
        ex.structure],
      [`F3 specific length${f3ReportOnly(fx) ? ' (not scored)' : ''}`,
        f3ReportOnly(fx) ? null : fx.specific_length?.score,
        `${fx.specific_length?.length ?? set.specific_length} nt`, ''],
    ]],
  ];
  return (
    <details className="group rounded-lg border border-slate-200" data-testid="tier-detail">
      <summary className="cursor-pointer list-none px-3 py-2 text-xs font-semibold text-slate-700 hover:text-teal-700">
        <span aria-hidden className="inline-block transition-transform group-open:rotate-90">▸</span> Criteria detail
        <span className="font-normal text-slate-600"> (codes and levels L1–L5, L5 best)</span>
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
                <th colSpan={4} className="text-left px-2 py-1 text-[11px] font-bold text-slate-600">{title}</th>
              </tr>
              {rows.map(([name, lvl, val, why]) => (
                <tr key={name}>
                  <td className="px-2 py-1.5 text-slate-700">{name}</td>
                  <td className="px-2 py-1.5 text-slate-700 tabular-nums break-words">{val ?? '—'}</td>
                  <td className="px-2 py-1.5 text-center tabular-nums font-semibold text-slate-700">{lvl ?? '—'}</td>
                  <td className="px-2 py-1.5 text-slate-700 hidden sm:table-cell">{why}</td>
                </tr>
              ))}
            </tbody>
          ))}
          <tbody>
            <tr className="bg-slate-50">
              <td className="px-2 py-1.5 text-slate-700" colSpan={2}>
                Tie-break score (used only when every group is equal)
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
