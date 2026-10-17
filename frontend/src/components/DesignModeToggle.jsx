/**
 * DesignModeToggle — switches between the Basic (/design) and Advanced
 * (/design/advanced) designer pages.
 *
 * Both routes share one draft (see useDesignForm), so switching never loses
 * what the user has already entered — Advanced simply exposes the parameters
 * Basic kept at their defaults.
 */
import { useNavigate } from 'react-router-dom';

const MODES = [
  { key: 'basic',    label: 'Basic',    path: '/design',          hint: 'Enter a miRNA, pick sample type and chemistry' },
  { key: 'advanced', label: 'Advanced', path: '/design/advanced', hint: 'Full control over every thermodynamic parameter' },
];

export default function DesignModeToggle({ current }) {
  const navigate = useNavigate();

  return (
    <div
      className="inline-flex items-center gap-1 p-1 rounded-xl bg-slate-100 border border-slate-200"
      role="tablist"
      aria-label="Designer mode"
    >
      {MODES.map(({ key, label, path, hint }) => {
        const isActive = current === key;
        return (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={isActive}
            title={hint}
            onClick={() => { if (!isActive) navigate(path); }}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150 ${
              isActive
                ? 'bg-white text-teal-700 shadow-sm ring-1 ring-slate-200'
                : 'text-slate-500 hover:text-teal-700'
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
