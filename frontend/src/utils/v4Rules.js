// Labels of the standard primer rules (the V4 hard filters; never called "V4" on the UI)
// a tiered set can break (`v4_rule_violations`, SPEC scoring QD 25): the GC pre-filter
// rules and the three structural hard filters of V4 (backend tiered_pipeline.v4_rule_violations).
// Same short labels as the PDF/CSV export (backend utils/report_text.RULE_LABELS); the
// longer explanation is in V4_RULE_DETAILS (tooltips). No new science here.
export const V4_RULE_LABELS = {
  gc_out_of_range: 'GC content outside the GC window',
  gc_clamp_fail: '3′ GC clamp missing',
  gc_end_window_fail: '3′ end too GC-rich (last 5 nt all G/C)',
  hard_dimer_full_dg: 'Strong primer dimer (ΔG < −9 kcal/mol)',
  hard_dimer_3prime_critical: '3′-end dimer Tm ≥ 47 °C',
  hard_hairpin_tm: 'Hairpin Tm ≥ 47 °C',
};

export const V4_RULE_DETAILS = {
  gc_out_of_range: 'GC % outside the GC window set under Parameters.',
  gc_clamp_fail: 'No G or C in the last 3 nt (all-A/T 3′ end).',
  gc_end_window_fail: 'All 5 of the last 5 nt are G/C (Primer3 Max End GC).',
  hard_dimer_full_dg: 'Full-structure dimer ΔG below −9 kcal/mol (RNAcofold, 37 °C; Kang 2017).',
  hard_dimer_3prime_critical: '3′-end dimer Tm at or above the Primer3 limit (47 °C).',
  hard_hairpin_tm: 'Hairpin Tm at or above the Primer3 limit (47 °C).',
};

export function v4RuleLabel(code) {
  return V4_RULE_LABELS[code] || String(code).replace(/_/g, ' ');
}
