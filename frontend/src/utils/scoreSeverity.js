/**
 * scoreSeverity — one severity scale for every 0–100 design-quality score.
 *
 * Previously ScoreBreakdown and ScoreGauge each hardcoded the same four hex
 * values, which had two problems:
 *   1. the "Good" band was #2563eb (blue) — a hue that means "info/link"
 *      everywhere else in this UI, not "slightly below target";
 *   2. the hex values bypassed the --brand-* CSS variables, so score colours
 *      stayed teal while the rest of the app switched to the Pink/Navy theme.
 *
 * The scale below stays inside the documented palette (tailwind.config.js):
 * brand family = on target, amber = caution, red = problem.
 */

export const SEVERITY = {
  excellent: { min: 80, label: 'At target',    color: 'var(--brand-600)' },
  good:      { min: 60, label: 'Near target',  color: 'var(--brand-400)' },
  fair:      { min: 40, label: 'Weak',          color: '#D97706' },  // amber-600
  poor:      { min: 0,  label: 'Problem',      color: '#DC2626' },  // red-600
};

/** Severity bucket for a 0–100 score. */
export function severityOf(score) {
  const v = Number(score);
  if (!Number.isFinite(v)) return SEVERITY.poor;
  if (v >= SEVERITY.excellent.min) return SEVERITY.excellent;
  if (v >= SEVERITY.good.min)      return SEVERITY.good;
  if (v >= SEVERITY.fair.min)      return SEVERITY.fair;
  return SEVERITY.poor;
}

/** Colour only — the common case. */
export function severityColor(score) {
  return severityOf(score).color;
}

/** A score at/above this needs no attention; used to fold away perfect rows. */
export const AT_TARGET = SEVERITY.excellent.min;

/** Grade name (from the backend) → colour, for the summary gauge. */
export function gradeColor(grade) {
  switch (grade) {
    case 'Excellent':  return SEVERITY.excellent.color;
    case 'Good':       return SEVERITY.good.color;
    case 'Acceptable': return SEVERITY.fair.color;
    case 'Poor':       return SEVERITY.poor.color;
    default:           return 'var(--brand-400)';
  }
}

// Human-readable labels — one per weighted criterion. Keep these clean:
// Title case, real primes (′), no snake_case keys ever shown to the user.
export const CRITERION_LABELS = {
  tm_accuracy:            'Primer Tm accuracy',
  tm_binding_accuracy:    'Binding-region Tm',
  mfe_stemloop:           'Stem-loop stability',
  gc_content:             'GC content',
  hairpin_penalty:        'Hairpin risk',
  dimer_penalty:          'Primer-dimer risk',
  end_stability:          '3′ end stability',
  bound_fraction_full:    'Full-primer occupancy',
  family_discrimination:  'Family discrimination',
  gc_clamp:               '3′ GC clamp',
  gc_skew:                'GC skew',
  primer_size:            'Specific-region length',
  amplicon_size:          'Amplicon size',
  tm_pair_match:          'Forward / reverse Tm balance',
};
