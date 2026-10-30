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
  neutral: { dot: 'bg-slate-300',  text: 'text-slate-500' },
  ok:      { dot: 'bg-teal-500',   text: 'text-teal-700'  },
  warn:    { dot: 'bg-amber-400',  text: 'text-amber-700' },
  danger:  { dot: 'bg-red-500',    text: 'text-red-700'   },
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

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center gap-2.5 px-4 py-3 text-left hover:bg-slate-50 transition-colors"
      >
        <span
          className={`text-teal-600 text-sm font-bold shrink-0 leading-none transition-transform duration-200 ${
            open ? 'rotate-90' : ''
          }`}
        >
          ▸
        </span>
        <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide shrink-0">
          {title}
        </span>
        {!open && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${t.dot}`} />}
        {!open && summary && (
          <span className={`text-xs truncate min-w-0 ${t.text}`}>{summary}</span>
        )}
        <span className="ml-auto text-xs text-slate-500 shrink-0">
          {open ? 'hide' : 'show'}
        </span>
      </button>

      {open && <div className="px-4 pb-4 pt-1">{children}</div>}
    </div>
  );
}
