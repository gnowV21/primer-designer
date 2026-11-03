// EdgeCaseBanner — shows critical/warning edge-case alerts at top of ResultsPage.
// Info-level edge cases are shown in QualitySummary, not here.

const SEV_STYLE = {
  critical: 'bg-red-50 border-red-200 text-red-800',
  warning:  'bg-amber-50 border-amber-200 text-amber-800',
};

const ACTION_HINTS = {
  E4: 'Consider increasing the 5′ tail length in the primer constraints form.',
  E5: 'Review secondary structure with a dedicated folding tool before ordering.',
  E6: 'Inspect the homopolymer region manually; mispriming risk may be elevated.',
};

export default function EdgeCaseBanner({ edgeCases = [] }) {
  const visible = edgeCases.filter((e) => e.severity === 'critical' || e.severity === 'warning');
  if (visible.length === 0) return null;

  return (
    <div className="space-y-2">
      {visible.map((e) => (
        <div
          key={e.code}
          className={`rounded-xl border px-4 py-3 text-sm leading-relaxed space-y-0.5 ${SEV_STYLE[e.severity] ?? SEV_STYLE.warning}`}
        >
          <span className="font-semibold">[{e.code}] </span>
          {e.message}
          {ACTION_HINTS[e.code] && (
            <p className="mt-1 text-xs opacity-80">{ACTION_HINTS[e.code]}</p>
          )}
        </div>
      ))}
    </div>
  );
}
