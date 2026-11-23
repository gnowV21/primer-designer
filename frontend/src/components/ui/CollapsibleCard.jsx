/**
 * CollapsibleCard — a results-page disclosure that is COLLAPSED by default.
 *
 * The results page carries a lot of secondary analysis (specificity matrices,
 * seed-family maps, reaction schematics). Showing it all at once buries the
 * primers themselves, so these panels stay closed until the user asks for them.
 *
 * `summary` is rendered in the header and stays visible while collapsed — the
 * user should be able to tell whether a panel is worth opening (e.g. "SAFE",
 * "2 collisions") without opening it.
 *
 * `tone` only colours the header dot/summary, never hides anything: a panel with
 * a warning still has to be opened deliberately, but it advertises the warning.
 */
import { useState } from 'react';

const TONES = {
  neutral: { dot: 'bg-slate-400',  text: 'text-slate-600' },
  ok:      { dot: 'bg-green-600',  text: 'text-green-700' },
  warn:    { dot: 'bg-amber-500',  text: 'text-amber-700' },
  danger:  { dot: 'bg-red-600',    text: 'text-red-700'   },
};

export default function CollapsibleCard({
  title,
  summary = null,
  tone = 'neutral',
  defaultOpen = false,
  children,
}) {
  const [open, setOpen] = useState(defaultOpen);
  const t = TONES[tone] || TONES.neutral;

  // Narrow screens: the summary goes on its own line under the title, so neither is
  // truncated and the Show/Hide toggle always stays inside the card.
  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-start gap-2.5 px-4 py-3 text-left hover:bg-slate-50 transition-colors"
      >
        <span
          aria-hidden
          className={`text-teal-700 text-sm font-bold shrink-0 leading-5 transition-transform duration-200 ${open ? 'rotate-90' : ''}`}
        >
          ▸
        </span>
        <span className="flex-1 min-w-0 flex flex-col sm:flex-row sm:items-baseline sm:gap-2">
          <span className="text-sm font-semibold text-slate-800">{title}</span>
          {!open && summary && (
            <span className={`flex items-center gap-1.5 text-xs min-w-0 ${t.text}`}>
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${t.dot}`} />
              <span className="sm:truncate">{summary}</span>
            </span>
          )}
        </span>
        <span className="shrink-0 text-xs font-medium text-teal-700 leading-5">
          {open ? 'Hide' : 'Show'}
        </span>
      </button>

      {open && <div className="px-4 pb-4 pt-1">{children}</div>}
    </div>
  );
}
