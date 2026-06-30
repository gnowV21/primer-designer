import { NavLink } from 'react-router-dom';
import { useTheme, THEMES } from '../contexts/ThemeContext.jsx';

const tabs = [
  { to: '/home',    label: 'Home'     },
  { to: '/roadmap', label: 'Roadmap'  },
  { to: '/search',  label: 'Designer' },
];

export default function Navbar() {
  const { theme, setTheme } = useTheme();

  return (
    <nav className="h-14 flex items-center justify-between px-6 border-b border-gray-200 bg-white sticky top-0 z-50 shrink-0">

      {/* Brand */}
      <div className="flex items-center gap-3">
        <img src="/logo.png" alt="HG Lab logo" className="w-8 h-8 rounded-full object-cover shrink-0" />
        <div className="leading-tight">
          <span className="block text-sm font-bold text-slate-800 tracking-tight">HG Lab</span>
          <span className="block text-[11px] text-teal-600 font-medium leading-none">
            Stem-loop RT-qPCR Designer
          </span>
        </div>
      </div>

      {/* Nav links + Theme switcher */}
      <div className="flex items-center gap-1">
        {tabs.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              isActive
                ? 'px-4 py-1.5 rounded-lg text-sm font-semibold text-teal-700 bg-teal-50 border border-teal-200 shadow-sm transition-all'
                : 'px-4 py-1.5 rounded-lg text-sm font-medium text-gray-500 hover:text-teal-700 hover:bg-teal-50 transition-all'
            }
          >
            {label}
          </NavLink>
        ))}

        {/* Divider */}
        <div className="w-px h-5 bg-gray-200 mx-2" />

        {/* Theme swatches */}
        <div className="flex items-center gap-1.5" title="Color theme">
          {Object.entries(THEMES).map(([key, { label, swatch }]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTheme(key)}
              title={label}
              aria-label={`Switch to ${label} theme`}
              className={`w-4 h-4 rounded-full transition-all duration-150 ${
                theme === key
                  ? 'ring-2 ring-offset-1 ring-gray-400 scale-125'
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
