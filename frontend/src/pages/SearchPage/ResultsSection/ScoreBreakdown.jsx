// ScoreBreakdown — horizontal bar chart for the 15 scoring criteria (V4).
// Only keys present in `weights` are rendered, so display-only helper keys
// (e.g. *_pct raw percentages) never leak into the list. Rows are ordered by
// weight so the most influential criteria appear first.

import { useState } from 'react';

// Human-readable labels — one per weighted criterion. Keep these clean:
// Title case, real primes (′), no snake_case keys ever shown to the user.
const LABELS = {
  tm_accuracy:            'Primer Tm accuracy',
  tm_binding_accuracy:    'Binding-region Tm',
  mfe_stemloop:           'Stem-loop stability',
  gc_content:             'GC content',
  hairpin_penalty:        'Hairpin risk',
  dimer_penalty:          'Primer-dimer risk',
  end_stability:          '3′ end stability',
  bound_fraction_binding: 'Binding occupancy',
  bound_fraction_full:    'Full-primer occupancy',
  family_discrimination:  'Family discrimination',
  gc_clamp:               '3′ GC clamp',
  gc_skew:                'GC skew',
  primer_size:            'Specific-region length',
  amplicon_size:          'Amplicon size',
  tm_pair_match:          'Forward / reverse Tm balance',
};

// Fallback: turn any unmapped key into a readable phrase instead of showing
// "some_raw_key". Defensive only — every weighted key should be in LABELS.
function prettify(key) {
  return key
    .replace(/_pct$/, '')
    .replace(/_/g, ' ')
    .replace(/^\w/, (c) => c.toUpperCase());
}

export default function ScoreBreakdown({ scores, weights, explanations }) {
  const [activeKey, setActiveKey] = useState(null);

  // Render only real weighted criteria, ordered by weight (most influential first).
  const rows = Object.keys(weights || {})
    .filter((key) => key in scores)
    .sort((a, b) => (weights[b] ?? 0) - (weights[a] ?? 0));

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Score breakdown</p>
      <div className="space-y-1.5">
        {rows.map((key) => {
          const val      = scores[key];
          const w        = weights?.[key] ?? 0;
          const contrib  = (val * w).toFixed(1);
          const label    = LABELS[key] || prettify(key);
          const barColor = val >= 80 ? '#0d9488' : val >= 60 ? '#2563eb' : val >= 40 ? '#d97706' : '#dc2626';
          const open     = activeKey === key;
          return (
            <div key={key}>
              <button
                type="button"
                className="w-full text-left group"
                onClick={() => setActiveKey(open ? null : key)}
                aria-expanded={open}
              >
                <div className="flex items-center gap-2">
                  <span
                    title={label}
                    className="w-44 shrink-0 text-xs text-gray-700 truncate group-hover:text-teal-700 transition-colors"
                  >
                    {label}
                  </span>
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${val}%`, backgroundColor: barColor }}
                    />
                  </div>
                  <span className="w-8 text-right text-xs text-gray-600 tabular-nums">{val}</span>
                  <span className="w-14 text-right text-xs text-gray-400 tabular-nums">
                    {Math.round(w * 100)}% · +{contrib}
                  </span>
                </div>
              </button>
              {open && explanations?.[key] && (
                <div className="ml-44 mt-1 text-xs text-gray-500 bg-gray-50 rounded px-2 py-1.5 leading-relaxed">
                  {explanations[key]}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <p className="text-right text-xs text-gray-400">weight% · score×weight — click a row for details</p>
    </div>
  );
}
