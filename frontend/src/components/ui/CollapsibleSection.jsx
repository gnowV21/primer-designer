import { createContext, useContext, useState, useRef, useEffect } from 'react';
import Tooltip from './Tooltip.jsx';

// Set by ParameterEditor on /design: every group starts open once "Parameters" is
// open, so the form has one level of folding (UI review 2026-11-23).
export const SectionsOpenByDefault = createContext(false);

const ACCENTS = {
  gray:   { border: 'border-slate-200',   text: 'text-slate-800' },
  purple: { border: 'border-purple-200', text: 'text-slate-800' },
};

export default function CollapsibleSection({
  title,
  tooltip,
  accent = 'gray',
  actions = null,
  defaultOpen = false,
  hasError = false,
  hasWarning = false,
  onFirstOpen = null,
  openRequested = 0,
  children,
}) {
  const openByDefault = useContext(SectionsOpenByDefault);
  const [open, setOpen] = useState(defaultOpen || openByDefault);
  const { border, text } = ACCENTS[accent] || ACCENTS.gray;
  const firedRef = useRef(false);

  // External trigger: open this section whenever openRequested increments (e.g. nav click)
  useEffect(() => {
    if (openRequested > 0) setOpen(true);
  }, [openRequested]);

  function handleToggle() {
    if (!open && !firedRef.current) {
      firedRef.current = true;
      onFirstOpen?.();
    }
    setOpen((v) => !v);
  }

  return (
    <div className={`rounded-lg border ${border} bg-white overflow-hidden`}>
      <div className="flex items-center justify-between gap-2 px-5 py-4">
        <button
          type="button"
          onClick={handleToggle}
          className="flex items-center gap-2.5 flex-1 text-left min-w-0"
          aria-expanded={open}
        >
          <span
            aria-hidden
            className={`text-teal-700 text-base font-bold shrink-0 leading-none transition-transform duration-200 ${open ? 'rotate-90' : ''}`}
          >
            ▸
          </span>
          <span className={`text-sm font-semibold min-w-0 leading-snug ${text}`}>
            {title}
          </span>
          {tooltip && <Tooltip text={tooltip} />}
          {!open && hasError && (
            <span
              className="w-1.5 h-1.5 rounded-full bg-red-600 shrink-0"
              title="This section has an error"
            />
          )}
          {!open && !hasError && hasWarning && (
            <span
              className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0"
              title="This section has a warning"
            />
          )}
        </button>
        {actions}
      </div>

      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-in-out ${
          open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
        }`}
      >
        <div className="overflow-hidden">
          <div className="px-5 pb-5 space-y-4">{children}</div>
        </div>
      </div>
    </div>
  );
}
