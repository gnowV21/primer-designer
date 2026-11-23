// One-sentence, bench-level answer to "why is set #1 above set #2?" (audit UX-03).
// Uses the same effective weights as the total, so the named criteria are the
// ones that actually moved the ranking.
import { CRITERION_LABELS } from './scoreSeverity.js';
import { compareTiered, decidingStep, hasTiers, KEY_STEPS, vetoedSubIndices } from './tierRank.js';
import { standardRuleLabels } from './criteriaGroups.js';

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

const COMPOSITION_LABEL = {
  gc: 'GC content', gc_clamp: '3′ GC clamp', binding_tm: 'binding-region Tm', structure: 'secondary structure',
};
const RISK_WORD = (r) => (r ? String(r).toLowerCase() : 'not run');

// Plain-English reasons (UI review 2026-11-23). The deciding step is the one of the
// ranking key (decidingStep / KEY_STEPS); only the words are written here.
function requiredDiffs(a, b) {
  const sa = a.ranking.specificity;
  const sb = b.ranking.specificity;
  const out = [];
  if (sa.blast?.score !== sb.blast?.score) {
    out.push(`its BLAST off-target screen is cleaner (${RISK_WORD(sa.blast?.overall_risk)} vs ${RISK_WORD(sb.blast?.overall_risk)})`);
  }
  if (sa.assay_dcq?.score !== sb.assay_dcq?.score) {
    out.push(`the closest other miRNA is held further back (assay ΔCq ${fmtNum(sa.assay_dcq?.min_delta_cq)} vs ${fmtNum(sb.assay_dcq?.min_delta_cq)})`);
  }
  if (sa.tm_margin?.score !== sb.tm_margin?.score) {
    out.push(`it discriminates the closest off-target better (Tm margin ${fmtNum(sa.tm_margin?.margin)} vs ${fmtNum(sb.tm_margin?.margin)} °C)`);
  }
  return out;
}

function compositionDiffs(a, b) {
  const fa = a.ranking.flexible;
  const fb = b.ranking.flexible;
  return Object.keys(COMPOSITION_LABEL)
    .filter((k) => fa[k] && fb[k] && fa[k].score !== fb[k].score)
    .map((k) => `${COMPOSITION_LABEL[k]} level ${fa[k].score} vs ${fb[k].score}`);
}

/** { step, text }: why `first` (#1) ranks above `second` (#2). step is a KEY_STEPS name,
 *  'identical' or 'out_of_order' — the same values as tierRank.tierReason. */
export function groupReason(first, second) {
  const i = decidingStep(first, second);
  if (i === -1) {
    return { step: 'identical',
      text: 'Sets #1 and #2 are identical on every criterion (they differ only in the 5′ tail); the order is arbitrary but fixed.' };
  }
  if (compareTiered(first, second) > 0) {
    return { step: 'out_of_order',
      text: `The order of #1 and #2 does not follow the ranking key (they differ at ${KEY_STEPS[i]}).` };
  }
  const a = first.ranking;
  const b = second.ranking;
  switch (KEY_STEPS[i]) {
    case 'specificity': {
      const d = requiredDiffs(first, second);
      return { step: 'specificity',
        text: `Set #1 ranks first because it is more specific (specificity ${a.specificity.total} vs ${b.specificity.total} of ${a.specificity.max})`
          + (d.length ? `: ${d.join('; ')}.` : '.') };
    }
    case 'structure_veto': {
      const sub = vetoedSubIndices(second);
      return { step: 'structure_veto',
        text: 'Set #1 ranks first: both sets are equally specific, but #2 has too strong a secondary structure'
          + `${sub.length ? ` (${sub.join(', ')})` : ''}.` };
    }
    case 'binding_floor_fail':
      return { step: 'binding_floor_fail',
        text: 'Set #1 ranks first: both sets are equally specific, but #2 binds the cDNA weakly in PCR cycle 1 '
          + '(binding-region Tm below 39 °C).' };
    case 'v4_violation': {
      const rules = standardRuleLabels(second);
      return { step: 'v4_violation',
        text: 'Set #1 ranks first: both sets are equally specific, but #2 does not meet a standard primer rule'
          + `${rules.length ? ` (${rules.join('; ')})` : ''}.` };
    }
    case 'pcr':
      return { step: 'pcr',
        text: 'Set #1 ranks first: both sets are equally specific, and #1 has its Tm closer to Ta '
          + `(${fmtNum(a.pcr.tm_vs_ta?.diff)} vs ${fmtNum(b.pcr.tm_vs_ta?.diff)} °C apart).` };
    case 'flexible': {
      const d = compositionDiffs(first, second);
      return { step: 'flexible',
        text: 'Set #1 ranks first: both sets are equally specific and equally close to Ta, and #1 scores higher on '
          + `composition and structure (${a.flexible.total} vs ${b.flexible.total} of ${a.flexible.max})`
          + `${d.length ? `: ${d.join(', ')}` : ''}.` };
    }
    case 'tie_break':
      return { step: 'tie_break',
        text: 'Sets #1 and #2 are equivalent in silico on every group; #1 is listed first on the tie-break score '
          + `(+${fmtNum(a.detailed_score - b.detailed_score)}).` };
    case 'tm_vs_ta':
      return { step: 'tm_vs_ta',
        text: 'Sets #1 and #2 are equivalent in silico on every group with the same tie-break score; #1 is closer to Ta '
          + `(${fmtNum(a.pcr.tm_vs_ta?.diff, 2)} vs ${fmtNum(b.pcr.tm_vs_ta?.diff, 2)} °C apart).` };
    default:
      return { step: 'identical',
        text: 'Sets #1 and #2 are identical on every criterion (they differ only in the 5′ tail); the order is arbitrary but fixed.' };
  }
}
