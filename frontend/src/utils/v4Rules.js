// Labels of the V4 rules a tiered set can break (`v4_rule_violations`, SPEC
// scoring QD 25): the GC pre-filter rules and the three structural hard filters of
// V4 (backend tiered_pipeline.v4_rule_violations). Text follows the existing
// rejection labels (RejectionLog) and AUDIT REV-17/20/21 — no new science here.
export const V4_RULE_LABELS = {
  gc_out_of_range: 'GC % outside the V4 window',
  gc_clamp_fail: 'No G/C in the last 3 nt (all-A/T 3′ end)',
  gc_end_window_fail: 'All 5 of the last 5 nt are G/C (Primer3 Max End GC)',
  hard_dimer_full_dg: 'Full-structure dimer ΔG < −9 kcal/mol (RNAcofold, 37 °C; Kang 2017)',
  hard_dimer_3prime_critical: '3′-end dimer Tm at or above the Primer3 limit (47 °C)',
  hard_hairpin_tm: 'Hairpin Tm at or above the Primer3 limit (47 °C)',
};

export function v4RuleLabel(code) {
  return V4_RULE_LABELS[code] || code;
}
