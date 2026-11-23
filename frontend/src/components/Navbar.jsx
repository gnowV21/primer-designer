import { NavLink } from 'react-router-dom';

const tabs = [
  { to: '/home',    label: 'Home'     },
  { to: '/design',  label: 'Designer' },
  { to: '/analyze', label: 'Analyzer' },
  { to: '/history', label: 'History'  },
];

export default function Navbar() {
  return (
    <nav className="h-14 flex items-center justify-between gap-2 px-3 lg:px-6 border-b border-slate-200 bg-white sticky top-0 z-50 shrink-0">

      {/* Brand. Phones (≥ 360 px) keep the product name; the logo joins it from 460 px.
          Below 360 px only the logo fits next to the four tabs. */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        <img src="/logo.png" alt="HG Lab"
          className="w-8 h-8 rounded-full object-cover shrink-0 min-[360px]:max-[459px]:hidden" />
        <div className="hidden min-[360px]:block leading-tight">
          <span className="hidden min-[460px]:block text-sm font-bold text-slate-800">HG Lab</span>
          <span className="block text-xs text-teal-700 font-semibold leading-tight whitespace-nowrap">
            {/* Two short lines below 460 px so the four tabs still fit beside it. */}
            <span className="lg:hidden">
              <span className="block min-[460px]:inline">Primer</span>{' '}
              <span className="block min-[460px]:inline">designer</span>
            </span>
            <span className="hidden lg:inline">Stem-loop RT-qPCR primer designer</span>
          </span>
        </div>
      </div>

      {/* Nav links */}
      {/* Sized to fit at 320 px; overflow-x-auto is only a last-resort guard. */}
      <div className="flex items-center gap-0 min-[380px]:gap-0.5 sm:gap-1 min-w-0 overflow-x-auto">
        {tabs.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              isActive
                ? 'shrink-0 px-1.5 min-[380px]:px-2 sm:px-3 lg:px-4 py-1.5 rounded-lg text-[13px] sm:text-sm font-semibold text-teal-700 bg-teal-50 border border-teal-200 shadow-sm transition-all'
                : 'shrink-0 px-1.5 min-[380px]:px-2 sm:px-3 lg:px-4 py-1.5 rounded-lg text-[13px] sm:text-sm font-medium text-slate-500 border border-transparent hover:text-teal-700 hover:bg-teal-50 transition-all'
            }
          >
            {label}
          </NavLink>
        ))}

      </div>
    </nav>
  );
}
