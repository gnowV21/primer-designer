// Criteria groups of the tiered ranking, as the UI presents them (2026-11-22).
//
// Display only: algorithm 4.0.0, the ranking key (utils/tierRank.js = backend
// tiered_scoring.rank_key) and the /api/design JSON (ranking.*) are unchanged.
//   Required = assay structure + forward Tm window + specificity S1–S3 (the S total
//              ranks first; S1 CRITICAL / S2 CO-AMPLIFIED are eliminated).
//   Flexible = 1. No critical weakness (structure_veto, binding_floor_fail,
//                 has_v4_violation — the three soft-veto steps of the key, in key order)
//              2. PCR (P2 |Tm − Ta|; ΔTm F–R, cycle-1 occupancy, amplicon Tm not scored)
//              3. Composition & structure (F1, F2, F4, F5; F3 length not scored).
// No UI label says "V4": the field names (v4_rule_violations, …) stay in code and API.
import { v4RuleLabel } from './v4Rules.js';
import { vetoedSubIndices } from './tierRank.js';

export const GROUP = {
  required: 'Required',
  flexible: 'Flexible',
  ncw: 'No critical weakness',
  pcr: 'PCR',
  composition: 'Composition & structure',
};

export const STANDARD_RULES = 'Meets standard primer rules';

/** The three conditions of "No critical weakness", in ranking-key order. */
export const NCW_CONDITIONS = [
  { key: 'structure_veto', label: 'Secondary structure not too strong',
    detail: 'no hairpin, dimer or 3′-end dimer sub-index at level 1' },
  { key: 'binding_floor_fail', label: 'Cycle-1 binding Tm ≥ 39 °C',
    detail: 'Tm of the miRNA-binding region' },
  { key: 'standard_rules', label: STANDARD_RULES,
    detail: 'the 6 classic hard filters: GC % window, G/C in the last 3 nt, not all of the last 5 nt G/C, '
      + 'full dimer ΔG, 3′-end dimer Tm, hairpin Tm' },
];

export const NCW_TOOLTIP = 'No critical weakness = all three, checked in this order: '
  + NCW_CONDITIONS.map((c, i) => `(${i + 1}) ${c.label.charAt(0).toLowerCase()}${c.label.slice(1)} (${c.detail})`).join('; ')
  + '. A set that fails one ranks below the sets with the same Required specificity; it is not eliminated.';

/** Failed "No critical weakness" conditions of a tiered set: [{ key, text, title }]. */
export function ncwFailures(set) {
  const r = set?.ranking || {};
  const out = [];
  if (r.structure_veto) {
    const sub = vetoedSubIndices(set);
    out.push({ key: 'structure_veto', text: `Secondary structure too strong${sub.length ? ` (${sub.join(', ')})` : ''}`,
      title: 'A structure sub-index is at level 1 (F5). Condition 1 of No critical weakness.' });
  }
  if (r.binding_floor_fail) {
    const tm = r.flexible?.binding_tm?.tm_binding;
    out.push({ key: 'binding_floor_fail',
      text: `Cycle-1 binding Tm ${tm != null ? `${Number(tm).toFixed(1)} °C ` : ''}< 39 °C`,
      title: set.explanations?.tm_binding_accuracy || 'Binding-region Tm below 39 °C (F4 level 1). Condition 2 of No critical weakness.' });
  }
  for (const code of set?.v4_rule_violations || []) {
    out.push({ key: code, text: `Standard primer rule not met: ${v4RuleLabel(code)}`,
      title: `${code} — condition 3 of No critical weakness.` });
  }
  return out;
}

/** Readable names of the standard primer rules a set does not meet. */
export function standardRuleLabels(set) {
  return (set?.v4_rule_violations || []).map(v4RuleLabel);
}

/** F4 note (decision 2026-11-22): it is cycle-1 binding but sits in F, after P2. */
export const F4_NOTE = 'PCR cycle-1 binding; scored with F, ranked after P2';
