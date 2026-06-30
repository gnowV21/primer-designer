// ScoreBreakdown — horizontal bar chart for all 11 scoring criteria.

import { useState } from 'react';

const LABELS = {
  tm_accuracy:         'Tm accuracy',
  tm_binding_accuracy: 'Binding Tm',
  gc_content:          'GC content',
  gc_skew:             'GC skew',
  mfe_stemloop:        'Stem-loop MFE',
  hairpin_penalty:     'Hairpin',
  dimer_penalty:       'Dimers',
  end_stability:       '3\' stability',
  primer_size:         'Primer size',
  amplicon_size:       'Amplicon size',
  tm_pair_match:       'Tm pair match',
};

export default function ScoreBreakdown({ scores, weights, explanations }) {
  const [activeKey, setActiveKey] = useState(null);

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Score breakdown</p>
      <div className="space-y-1.5">
        {Object.entries(scores).map(([key, val]) => {
          const w        = weights?.[key] ?? 0;
          const contrib  = (val * w).toFixed(1);
          const barColor = val >= 80 ? '#0d9488' : val >= 60 ? '#2563eb' : val >= 40 ? '#d97706' : '#dc2626';
          return (
            <div key={key}>
              <button
                type="button"
                className="w-full text-left group"
                onClick={() => setActiveKey(activeKey === key ? null : key)}
              >
                <div className="flex items-center gap-2">
                  <span className="w-28 shrink-0 text-xs text-gray-600 truncate group-hover:text-teal-700 transition-colors">
                    {LABELS[key] || key}
                  </span>
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${val}%`, backgroundColor: barColor }}
                    />
                  </div>
                  <span className="w-8 text-right text-xs text-gray-500 tabular-nums">{val}</span>
                  <span className="w-10 text-right text-xs text-gray-400 tabular-nums">+{contrib}</span>
                </div>
              </button>
              {activeKey === key && explanations?.[key] && (
                <div className="ml-28 mt-1 text-xs text-gray-500 bg-gray-50 rounded px-2 py-1.5 leading-relaxed">
                  {explanations[key]}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <p className="text-right text-xs text-gray-400">Score × weight · click row for details</p>
    </div>
  );
}
