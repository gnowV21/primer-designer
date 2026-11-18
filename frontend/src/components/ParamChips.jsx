/**
 * ParamChips — the key parameters of a design, as a row of small chips.
 *
 * Shows what a design used (or will use) at a glance. Chips whose `path` is in
 * `highlight` are tinted, so a changed value stands out from the defaults.
 */
import { summarizeParams } from '../utils/paramSummary.js';

export default function ParamChips({ params, highlight = new Set(), className = '', layout = 'chips' }) {
  if (layout === 'list') {
    // Vertical: one parameter per line, label left, value right (results page).
    return (
      <dl className={`divide-y divide-slate-100 text-xs ${className}`} data-testid="param-list">
        {summarizeParams(params).map(({ path, label, value }) => {
          const changed = highlight.has(path);
          return (
            <div key={path} className="flex items-baseline justify-between gap-4 py-1">
              <dt className="font-semibold text-slate-700">{label}</dt>
              <dd className={`tabular-nums text-right ${changed ? 'text-teal-800 font-semibold' : 'text-slate-700'}`}>{value}</dd>
            </div>
          );
        })}
      </dl>
    );
  }
  return (
    <div className={`flex flex-wrap gap-1.5 ${className}`}>
      {summarizeParams(params).map(({ path, text }) => {
        const changed = highlight.has(path);
        return (
          <span
            key={path}
            className={`text-xs rounded-md px-2 py-0.5 border tabular-nums ${
              changed
                ? 'bg-teal-50 border-teal-300 text-teal-800 font-medium'
                : 'bg-slate-50 border-slate-200 text-slate-600'
            }`}
          >
            {text}
          </span>
        );
      })}
    </div>
  );
}
