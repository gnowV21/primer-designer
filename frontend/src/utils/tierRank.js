// Tiered ranking key on the frontend (docs/SPEC_ui_tiered_4.0.0.md §2.4, §2.5).
//
// Mirrors backend/algorithm/tiered_scoring.py rank_key exactly:
//   (−S_total, structure_veto, binding_floor_fail, has_v4_violation,
//    −P_total, −F_total, −detailed_score, |Tm_full − Ta|, sequence)
// Pure functions only (no React), so a Node script can check them against the API's
// own order (frontend/scripts/check_tier_order.mjs).

/** True when a set carries the tiered ranking (algorithm 4.0.0). V4 sets and old
 *  History records have no `ranking` and keep the V4 display (SPEC_ui U5). */
export function hasTiers(set) {
  return !!set?.ranking && set.ranking.system === 'tiered';
}

/** The ranking key of one set, as an array compared element by element. */
export function tierKey(set) {
  const r = set.ranking;
  const tvt = r.pcr?.tm_vs_ta || {};
  return [
    -r.specificity.total,
    r.structure_veto ? 1 : 0,
    r.binding_floor_fail ? 1 : 0,
    (set.v4_rule_violations || []).length > 0 ? 1 : 0,
    -r.pcr.total,
    -r.flexible.total,
    -r.detailed_score,
    Math.abs(tvt.tm - tvt.ta),
    set.sequence || '',
  ];
}

/** Names of the key steps, in key order (index = step). */
export const KEY_STEPS = [
  'specificity', 'structure_veto', 'binding_floor_fail', 'v4_violation',
  'pcr', 'flexible', 'tie_break', 'tm_vs_ta', 'sequence',
];

/** Steps that make two sets "Equivalent in silico" when all are equal (U4). */
const EQUIVALENCE_STEPS = 6;

function cmp(x, y) {
  if (typeof x === 'string') return x < y ? -1 : x > y ? 1 : 0;
  return x < y ? -1 : x > y ? 1 : 0;
}

/** First key step at which a and b differ, or -1 when the keys are identical. */
export function decidingStep(a, b) {
  const ka = tierKey(a);
  const kb = tierKey(b);
  for (let i = 0; i < ka.length; i++) {
    if (cmp(ka[i], kb[i]) !== 0) return i;
  }
  return -1;
}

/** Array.sort comparator: negative when a ranks above b. */
export function compareTiered(a, b) {
  const ka = tierKey(a);
  const kb = tierKey(b);
  for (let i = 0; i < ka.length; i++) {
    const c = cmp(ka[i], kb[i]);
    if (c !== 0) return c;
  }
  return 0;
}

/** Same (S, structure veto, binding floor, V4 rule, P, F): QD 16, extended by QD 34/36. */
export function equivalentInSilico(a, b) {
  if (!hasTiers(a) || !hasTiers(b)) return false;
  const step = decidingStep(a, b);
  return step === -1 || step >= EQUIVALENCE_STEPS;
}

/** Ranks of the other sets in `sets` that are equivalent in silico to `set`. */
export function equivalentRanks(set, sets) {
  return (sets || [])
    .filter((o) => o !== set && equivalentInSilico(set, o))
    .map((o) => o.rank);
}

// ── "Why #1 over #2" by the deciding tier (SPEC_ui §2.4) ──────────────────

const STRUCTURE_SUB = {
  hairpin_tm: 'hairpin Tm',
  dimer_dg: 'dimer ΔG',
  end_dimer_tm: '3′-end dimer Tm',
};

const fmtNum = (v, d = 1) => (v == null || Number.isNaN(Number(v)) ? 'n/a' : Number(v).toFixed(d));

/** S components that differ between a and b, e.g. "BLAST SAFE vs MEDIUM". */
function specificityDiffs(a, b) {
  const sa = a.ranking.specificity;
  const sb = b.ranking.specificity;
  const out = [];
  if (sa.blast?.score !== sb.blast?.score) {
    out.push(`BLAST ${sa.blast?.overall_risk ?? 'not run'} vs ${sb.blast?.overall_risk ?? 'not run'}`);
  }
  if (sa.assay_dcq?.score !== sb.assay_dcq?.score) {
    out.push(`assay ΔCq ${fmtNum(sa.assay_dcq?.min_delta_cq)} vs ${fmtNum(sb.assay_dcq?.min_delta_cq)}`);
  }
  if (sa.tm_margin?.score !== sb.tm_margin?.score) {
    out.push(`Tm margin ${fmtNum(sa.tm_margin?.margin)} vs ${fmtNum(sb.tm_margin?.margin)} °C`);
  }
  return out;
}

/** Structure sub-indices at level 1 (the ones behind a structure veto). */
export function vetoedSubIndices(set) {
  const sub = set.ranking?.flexible?.structure?.sub_scores || {};
  return Object.keys(sub).filter((k) => sub[k] === 1).map((k) => STRUCTURE_SUB[k] || k);
}

const FLEX_LABEL = { gc: 'GC %', gc_clamp: 'GC clamp', binding_tm: 'binding Tm', structure: 'structure' };

function flexibleDiffs(a, b) {
  const fa = a.ranking.flexible;
  const fb = b.ranking.flexible;
  return Object.keys(FLEX_LABEL)
    .filter((k) => fa[k] && fb[k] && fa[k].score !== fb[k].score)
    .map((k) => `${FLEX_LABEL[k]} ${fa[k].score} vs ${fb[k].score}`);
}

/**
 * One sentence: why `first` (#1) ranks above `second` (#2), taken from the first key
 * step where they differ. Returns { step, text }. step is a KEY_STEPS name, 'identical'
 * when every key element is equal, or 'out_of_order' if the API order disagrees with
 * the key (never expected; shown rather than hidden).
 */
export function tierReason(first, second) {
  const i = decidingStep(first, second);
  if (i === -1) {
    return { step: 'identical',
      text: 'Identical on every criterion (5′-tail variants); the order is arbitrary but fixed.' };
  }
  if (compareTiered(first, second) > 0) {
    return { step: 'out_of_order',
      text: `The order of #1 and #2 does not follow the tier key (they differ at ${KEY_STEPS[i]}).` };
  }
  const a = first.ranking;
  const b = second.ranking;
  switch (KEY_STEPS[i]) {
    case 'specificity': {
      const d = specificityDiffs(first, second);
      return { step: 'specificity',
        text: `#1 is more specific (S ${a.specificity.total} vs ${b.specificity.total})`
          + (d.length ? `: ${d.join(', ')}.` : '.') };
    }
    case 'structure_veto': {
      const sub = vetoedSubIndices(second);
      return { step: 'structure_veto',
        text: `Same specificity; #2 has a structure veto${sub.length ? ` (${sub.join(', ')})` : ''}.` };
    }
    case 'binding_floor_fail':
      return { step: 'binding_floor_fail',
        text: 'Same specificity; #2’s binding region Tm is below the 39 °C floor.' };
    case 'v4_violation':
      return { step: 'v4_violation',
        text: `Same specificity; #2 is outside a V4 rule (${(second.v4_rule_violations || []).join(', ')}).` };
    case 'pcr':
      return { step: 'pcr',
        text: `Same specificity; #1 is closer to Ta (|ΔTm| ${fmtNum(a.pcr.tm_vs_ta?.diff)} vs `
          + `${fmtNum(b.pcr.tm_vs_ta?.diff)} °C).` };
    case 'flexible': {
      const d = flexibleDiffs(first, second);
      return { step: 'flexible',
        text: `Same specificity and PCR; #1 scores higher on flexible criteria (F ${a.flexible.total} vs `
          + `${b.flexible.total})${d.length ? `: ${d.join(', ')}` : ''}.` };
    }
    case 'tie_break':
      return { step: 'tie_break',
        text: `Equivalent in silico on every tier; ordered by tie-break score `
          + `(+${fmtNum(a.detailed_score - b.detailed_score)}).` };
    case 'tm_vs_ta':
      return { step: 'tm_vs_ta',
        text: 'Equivalent in silico on every tier, same tie-break score; #1 is closer to Ta '
          + `(|ΔTm| ${fmtNum(a.pcr.tm_vs_ta?.diff, 2)} vs ${fmtNum(b.pcr.tm_vs_ta?.diff, 2)} °C).` };
    default:
      return { step: 'identical',
        text: 'Identical on every criterion (5′-tail variants); the order is arbitrary but fixed.' };
  }
}

// ── Run comparison (RerunBar ★) ──────────────────────────────────────────

/** Indices of the runs whose #1 set ranks best by the tier key (the same comparator
 *  as the ranking). Empty when a #1 is missing or not tiered, or when every run's
 *  #1 is equal on the key (nothing to single out). */
export function bestRunIndices(topSets) {
  if (topSets.length < 2 || !topSets.every(hasTiers)) return [];
  // S is out of 15 with BLAST and out of 10 without: runs that differ in BLAST
  // availability are not on one scale, so no run is singled out (review panel A3).
  const maxes = new Set(topSets.map((s) => s.ranking.specificity?.max));
  if (maxes.size > 1) return [];
  let best = topSets[0];
  for (const s of topSets) if (compareTiered(s, best) < 0) best = s;
  const idx = topSets.map((s, i) => (compareTiered(s, best) === 0 ? i : -1)).filter((i) => i >= 0);
  return idx.length === topSets.length ? [] : idx;
}
