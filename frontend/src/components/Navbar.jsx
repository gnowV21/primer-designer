import { NavLink } from 'react-router-dom';
import { useTheme, THEMES } from '../contexts/ThemeContext.jsx';

const tabs = [
  { to: '/home',    label: 'Home'     },
  // Not `end` — stays highlighted on /design/advanced too.
  { to: '/design',  label: 'Designer' },
  { to: '/analyze', label: 'Analyzer' },
  { to: '/history', label: 'History'  },
];

export default function Navbar() {
  const { theme, setTheme } = useTheme();

  return (
    <nav className="h-14 flex items-center justify-between gap-2 px-3 sm:px-6 border-b border-slate-200 bg-white sticky top-0 z-50 shrink-0">

      {/* Brand */}
      <div className="flex items-center gap-3 shrink-0">
        <img src="/logo.png" alt="HG Lab logo" className="w-8 h-8 rounded-full object-cover shrink-0" />
        <div className="leading-tight">
          <span className="block text-sm font-bold text-slate-800 tracking-tight">HG Lab</span>
          <span className="hidden sm:block text-xs text-teal-600 font-medium leading-none">
            Stem-loop RT-qPCR Designer
          </span>
        </div>
      </div>

      {/* Nav links + Theme switcher */}
      {/* Tabs scroll sideways on narrow screens instead of widening the page. */}
      <div className="flex items-center gap-1 min-w-0 overflow-x-auto">
        {tabs.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              isActive
                ? 'shrink-0 px-2.5 sm:px-4 py-1.5 rounded-lg text-sm font-semibold text-teal-700 bg-teal-50 border border-teal-200 shadow-sm transition-all'
                : 'shrink-0 px-2.5 sm:px-4 py-1.5 rounded-lg text-sm font-medium text-slate-500 hover:text-teal-700 hover:bg-teal-50 transition-all'
            }
          >
            {label}
          </NavLink>
        ))}

        {/* Divider */}
        <div className="hidden sm:block w-px h-5 bg-slate-200 mx-2" />

        {/* Theme swatches */}
        <div className="hidden sm:flex items-center gap-1.5" title="Color theme">
          {Object.entries(THEMES).map(([key, { label, swatch }]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTheme(key)}
              title={label}
              aria-label={`Switch to ${label} theme`}
              className={`w-4 h-4 rounded-full transition-all duration-150 ${
                theme === key
                  ? 'ring-2 ring-offset-1 ring-slate-400 scale-125'
                  : 'opacity-60 hover:opacity-100 hover:scale-110'
              }`}
              style={{ backgroundColor: swatch }}
            />
          ))}
        </div>
      </div>
    </nav>
  );
}
