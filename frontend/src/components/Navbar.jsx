import { NavLink } from 'react-router-dom';

const tabs = [
  { to: '/home',    label: 'Home'     },
  { to: '/roadmap', label: 'Roadmap'  },
  { to: '/search',  label: 'Designer' },
];

export default function Navbar() {
  return (
    <nav className="h-14 flex items-center justify-between px-6 border-b border-gray-200 bg-white shrink-0">

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

      {/* Nav links */}
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
      </div>
    </nav>
  );
}
