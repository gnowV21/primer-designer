// One-sentence, bench-level answer to "why is set #1 above set #2?" (audit UX-03).
// Uses the same effective weights as the total, so the named criteria are the
// ones that actually moved the ranking.
import { CRITERION_LABELS } from './scoreSeverity.js';
import { compareTiered, decidingStep, hasTiers, KEY_STEPS, vetoedSubIndices } from './tierRank.js';
import { GROUP, standardRuleLabels } from './criteriaGroups.js';

const TIE_POINTS = 1.0;       // total-score gap below which the sets are called a tie
const MIN_CONTRIB = 0.3;      // ignore criteria that moved the total by < 0.3 points

function contributions(a, b) {
  const w = a?.weights || {};
  return Object.keys(w)
    .filter((k) => typeof a.scores?.[k] === 'number' && typeof b.scores?.[k] === 'number')
    .map((k) => ({ key: k, pts: (a.scores[k] - b.scores[k]) * w[k] }))
    .filter((c) => Math.abs(c.pts) >= MIN_CONTRIB)
    .sort((x, y) => Math.abs(y.pts) - Math.abs(x.pts));
}

const label = (k) => CRITERION_LABELS[k] || k.replace(/_/g, ' ');
const list = (cs) => cs.map((c) => `${label(c.key)} (${c.pts > 0 ? '+' : ''}${c.pts.toFixed(1)})`).join(', ');

export function rankReason(first, second) {
  if (!first || !second) return null;
  // Tiered sets (algorithm 4.0.0): explain by the deciding step of the ranking key, in
  // key order, with the Required / Flexible group names (groupReason below).
  // total_score is only the last tie-break there.
  if (hasTiers(first) && hasTiers(second)) return groupReason(first, second).text;
  return v4RankReason(first, second);
}

/** V4 sets (API scoringSystem "v4", old History records): weighted-score gap (U5). */
export function v4RankReason(first, second) {
  if (!first || !second) return null;
  const gap = (first.total_score ?? 0) - (second.total_score ?? 0);
  const cs = contributions(first, second);
  const ahead = cs.filter((c) => c.pts > 0).slice(0, 2);
  const behind = cs.filter((c) => c.pts < 0).slice(0, 1);
  if (gap < TIE_POINTS) {
    return `#1 and #2 are practically tied (${gap.toFixed(1)} points apart) — either is a sound choice; `
      + 'pick on practical grounds such as amplicon length or synthesis cost.';
  }
  let s = `#1 ranks ${gap.toFixed(1)} points above #2`;
  s += ahead.length ? `, mainly on ${list(ahead)}` : '';
  s += behind.length ? `; #2 is better on ${list(behind)}` : '';
  return `${s}.`;
}

// ── Tiered: "Why #1 over #2" with the criteria-group names (2026-11-22) ─────────
// Same deciding step as tierRank.tierReason (decidingStep / KEY_STEPS, the backend key);
// only the words differ. tierRank.js is unchanged, so check_tier_order.mjs still reads
// tierReason().step.

const fmtNum = (v, d = 1) => (v == null || Number.isNaN(Number(v)) ? 'n/a' : Number(v).toFixed(d));

const COMPOSITION_LABEL = { gc: 'F1 GC %', gc_clamp: 'F2 GC clamp', binding_tm: 'F4 binding Tm', structure: 'F5 structure' };

function requiredDiffs(a, b) {
  const sa = a.ranking.specificity;
  const sb = b.ranking.specificity;
  const out = [];
  if (sa.blast?.score !== sb.blast?.score) {
    out.push(`S1 BLAST ${sa.blast?.overall_risk ?? 'not run'} vs ${sb.blast?.overall_risk ?? 'not run'}`);
  }
  if (sa.assay_dcq?.score !== sb.assay_dcq?.score) {
    out.push(`S2 ΔCq ${fmtNum(sa.assay_dcq?.min_delta_cq)} vs ${fmtNum(sb.assay_dcq?.min_delta_cq)}`);
  }
  if (sa.tm_margin?.score !== sb.tm_margin?.score) {
    out.push(`S3 Tm margin ${fmtNum(sa.tm_margin?.margin)} vs ${fmtNum(sb.tm_margin?.margin)} °C`);
  }
  return out;
}

function compositionDiffs(a, b) {
  const fa = a.ranking.flexible;
  const fb = b.ranking.flexible;
  return Object.keys(COMPOSITION_LABEL)
    .filter((k) => fa[k] && fb[k] && fa[k].score !== fb[k].score)
    .map((k) => `${COMPOSITION_LABEL[k]} ${fa[k].score} vs ${fb[k].score}`);
}

/** { step, text }: why `first` (#1) ranks above `second` (#2). step is a KEY_STEPS name,
 *  'identical' or 'out_of_order' — the same values as tierRank.tierReason. */
export function groupReason(first, second) {
  const i = decidingStep(first, second);
  if (i === -1) {
    return { step: 'identical',
      text: 'Identical on every criterion (5′-tail variants); the order is arbitrary but fixed.' };
  }
  if (compareTiered(first, second) > 0) {
    return { step: 'out_of_order',
      text: `The order of #1 and #2 does not follow the ranking key (they differ at ${KEY_STEPS[i]}).` };
  }
  const a = first.ranking;
  const b = second.ranking;
  const ncw = GROUP.ncw.toLowerCase();
  switch (KEY_STEPS[i]) {
    case 'specificity': {
      const d = requiredDiffs(first, second);
      return { step: 'specificity',
        text: `${GROUP.required}: #1 is more specific (S ${a.specificity.total} vs ${b.specificity.total})`
          + (d.length ? `: ${d.join(', ')}.` : '.') };
    }
    case 'structure_veto': {
      const sub = vetoedSubIndices(second);
      return { step: 'structure_veto',
        text: `Same ${GROUP.required} specificity; #2 fails ${GROUP.ncw}: secondary structure too strong`
          + `${sub.length ? ` (${sub.join(', ')})` : ''}.` };
    }
    case 'binding_floor_fail':
      return { step: 'binding_floor_fail',
        text: `Same ${GROUP.required} specificity; #2 fails ${GROUP.ncw}: cycle-1 binding Tm below 39 °C.` };
    case 'v4_violation': {
      const rules = standardRuleLabels(second);
      return { step: 'v4_violation',
        text: `Same ${GROUP.required} specificity; #2 fails ${GROUP.ncw}: it does not meet the standard primer rules`
          + `${rules.length ? ` (${rules.join('; ')})` : ''}.` };
    }
    case 'pcr':
      return { step: 'pcr',
        text: `Same ${GROUP.required} specificity and ${ncw}; ${GROUP.pcr}: #1 is closer to Ta `
          + `(|Tm − Ta| ${fmtNum(a.pcr.tm_vs_ta?.diff)} vs ${fmtNum(b.pcr.tm_vs_ta?.diff)} °C).` };
    case 'flexible': {
      const d = compositionDiffs(first, second);
      return { step: 'flexible',
        text: `Same ${GROUP.required} specificity, ${ncw} and ${GROUP.pcr}; #1 scores higher on `
          + `${GROUP.composition.toLowerCase()} (F ${a.flexible.total} vs ${b.flexible.total})`
          + `${d.length ? `: ${d.join(', ')}` : ''}.` };
    }
    case 'tie_break':
      return { step: 'tie_break',
        text: 'Equivalent in silico on every group; ordered by tie-break score '
          + `(+${fmtNum(a.detailed_score - b.detailed_score)}).` };
    case 'tm_vs_ta':
      return { step: 'tm_vs_ta',
        text: 'Equivalent in silico on every group, same tie-break score; #1 is closer to Ta '
          + `(|Tm − Ta| ${fmtNum(a.pcr.tm_vs_ta?.diff, 2)} vs ${fmtNum(b.pcr.tm_vs_ta?.diff, 2)} °C).` };
    default:
      return { step: 'identical',
        text: 'Identical on every criterion (5′-tail variants); the order is arbitrary but fixed.' };
  }
}
