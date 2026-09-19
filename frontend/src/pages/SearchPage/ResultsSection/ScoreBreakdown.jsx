// ScoreBreakdown — the scored criteria (V4: 14 scored; cycle-1 occupancy is informational).
//
// Only keys present in `weights` are rendered, so display-only helper keys
// (e.g. *_pct raw percentages) never leak into the list. Rows stay ordered by
// weight, because that is what actually drives the total.
//
// Design note: on a good design most criteria sit at 100, so drawing
// 15 identical full-width bars hides the one row that matters. At-target rows
// are therefore muted and the sub-target ones keep full contrast, with a count
// in the header and a filter for scanning straight to the exceptions.

import { useState } from 'react';
import { severityColor, severityOf, AT_TARGET, CRITERION_LABELS as LABELS } from '../../../utils/scoreSeverity.js';

// Label column width, shared by the row and its expanded explanation so the
// two can never drift apart.
const LABEL_W = 'w-44';
const LABEL_INDENT = 'ml-44';

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
  const [onlyBelow, setOnlyBelow] = useState(false);

  // Render only real weighted criteria, ordered by weight (most influential first).
  const allRows = Object.keys(weights || {})
    .filter((key) => key in scores)
    .sort((a, b) => (weights[b] ?? 0) - (weights[a] ?? 0));

  const belowKeys = allRows.filter((k) => scores[k] < AT_TARGET);
  const rows = onlyBelow ? belowKeys : allRows;

  return (
    <div className="space-y-2">
      {/* Header: what the list contains, before the user reads any row */}
      <div className="flex items-baseline gap-2 flex-wrap">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Score breakdown</p>
        <span className="text-xs text-slate-500">
          {allRows.length} criteria
          {belowKeys.length === 0
            ? ' · all at target'
            : ` · ${allRows.length - belowKeys.length} at target`}
        </span>
        {belowKeys.length > 0 && (
          <button
            type="button"
            onClick={() => setOnlyBelow((v) => !v)}
            aria-pressed={onlyBelow}
            className={`text-xs font-medium px-2 py-0.5 rounded-full border transition-colors ${
              onlyBelow
                ? 'bg-amber-50 border-amber-200 text-amber-700'
                : 'bg-white border-slate-200 text-slate-500 hover:border-amber-200 hover:text-amber-700'
            }`}
          >
            {belowKeys.length} below target
          </button>
        )}
      </div>

      <div className="space-y-1.5">
        {rows.map((key) => {
          const val      = scores[key];
          const w        = weights?.[key] ?? 0;
          const contrib  = (val * w).toFixed(1);
          const label    = LABELS[key] || prettify(key);
          const sev      = severityOf(val);
          const atTarget = val >= AT_TARGET;
          const open     = activeKey === key;
          return (
            <div key={key}>
              <button
                type="button"
                className="w-full text-left group"
                onClick={() => setActiveKey(open ? null : key)}
                aria-expanded={open}
                title={atTarget ? `${label} — ${sev.label}` : `${label} — ${sev.label} (${val})`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`${LABEL_W} shrink-0 text-xs truncate transition-colors group-hover:text-teal-700 ${
                      atTarget ? 'text-slate-500' : 'text-slate-800 font-medium'
                    }`}
                  >
                    {label}
                  </span>
                  <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${val}%`,
                        backgroundColor: severityColor(val),
                        // Perfect rows recede so the exceptions carry the contrast.
                        opacity: atTarget ? 0.45 : 1,
                      }}
                    />
                  </div>
                  <span
                    className={`w-9 text-right text-xs tabular-nums ${
                      atTarget ? 'text-slate-500' : 'text-slate-900 font-semibold'
                    }`}
                  >
                    {val}
                  </span>
                  {/* w-20 + nowrap: "20% · +20.0" wrapped onto two lines at w-14 */}
                  <span className="w-20 text-right text-xs text-slate-500 tabular-nums whitespace-nowrap">
                    {Math.round(w * 100)}% · +{contrib}
                  </span>
                </div>
              </button>
              {open && explanations?.[key] && (
                <div className={`${LABEL_INDENT} mt-1 text-xs text-slate-500 bg-slate-50 rounded px-2 py-1.5 leading-relaxed`}>
                  {explanations[key]}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-right text-xs text-slate-500">weight% · score×weight — click a row for details</p>
    </div>
  );
}
