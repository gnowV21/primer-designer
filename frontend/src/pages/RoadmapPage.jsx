const weeks = [
  {
    week: 'Week 1',
    title: 'Setup · Input form · miRBase API',
    status: 'current',
    tasks: [
      'Project structure (Flask + React + Tailwind)',
      'Overall layout: Navbar, Footer, Chatbot panel',
      'Form with 6 parameter groups and RangeSlider',
      'miRBase API integration — auto-fill sequence',
      'Client-side form validation (English)',
    ],
  },
  {
    week: 'Week 2',
    title: 'Primer design algorithm',
    status: 'upcoming',
    tasks: [
      'Stem-loop RT primer algorithm (hairpin + 3′ overhang)',
      'Forward qPCR primer algorithm (miRNA + 5′ tail)',
      'Tm calculation via nearest-neighbor thermodynamics',
      'GC clamp check, avoid self-complementarity',
      'API endpoint POST /api/design',
    ],
  },
  {
    week: 'Week 3',
    title: 'Results page & quality checks',
    status: 'upcoming',
    tasks: [
      'ResultsPage displaying 3 primers',
      'Detailed thermodynamic parameter table',
      'Quality warnings (dimer, hairpin, off-target)',
      'Export results as PDF / CSV',
      'Edge case handling: short miRNA, extreme GC content',
    ],
  },
  {
    week: 'Week 4+',
    title: 'AI Chatbot & Deploy',
    status: 'upcoming',
    tasks: [
      'Real AI chatbot integration (explain results)',
      'Full responsive design for tablet/mobile',
      'Deploy backend to Render.com',
      'Deploy frontend to Vercel',
      'Full E2E testing with Playwright',
    ],
  },
];

const statusConfig = {
  current:  { dot: 'bg-blue-600',  line: 'border-blue-200', badge: 'bg-blue-50 text-blue-700 border border-blue-200', label: 'In progress' },
  upcoming: { dot: 'bg-gray-300',  line: 'border-gray-200', badge: 'bg-gray-100 text-gray-500 border border-gray-200', label: 'Upcoming' },
  done:     { dot: 'bg-blue-400',  line: 'border-blue-100', badge: 'bg-blue-50 text-blue-600 border border-blue-100', label: 'Done' },
};

export default function RoadmapPage() {
  if (typeof document !== 'undefined') document.title = 'HG Lab | Roadmap';
  return (
    <div className="max-w-2xl mx-auto space-y-2">

      <div className="mb-6">
        <h1 className="text-lg font-semibold text-gray-800">Development roadmap</h1>
        <p className="text-sm text-gray-500 mt-1">
          4-week plan to build HG Lab Primer Designer from scaffold to production.
        </p>
      </div>

      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-[19px] top-6 bottom-6 w-px bg-gray-200" />

        <div className="space-y-6">
          {weeks.map((w) => {
            const cfg = statusConfig[w.status];
            return (
              <div key={w.week} className="flex gap-5">
                {/* Dot */}
                <div className="flex flex-col items-center shrink-0 pt-1">
                  <div className={`w-5 h-5 rounded-full border-2 border-white shadow-sm ${cfg.dot} z-10`} />
                </div>

                {/* Card */}
                <div className="flex-1 rounded-lg border border-gray-200 bg-white px-5 py-4 space-y-3 mb-1">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div>
                      <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                        {w.week}
                      </span>
                      <h3 className="text-sm font-semibold text-gray-800 mt-0.5">{w.title}</h3>
                    </div>
                    <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${cfg.badge}`}>
                      {cfg.label}
                    </span>
                  </div>

                  <ul className="space-y-1.5">
                    {w.tasks.map((task) => (
                      <li key={task} className="flex items-start gap-2 text-xs text-gray-600">
                        <span className={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${w.status === 'current' ? 'bg-blue-500' : 'bg-gray-300'}`} />
                        {task}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>
      </div>

    </div>
  );
}
