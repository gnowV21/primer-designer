// StructureChecks — pass/warn/fail badges for 4 structure checks.

const SEV_STYLES = {
  safe:       'bg-teal-50  border-teal-200  text-teal-700',
  acceptable: 'bg-slate-50  border-slate-200  text-slate-700',
  warning:    'bg-amber-50 border-amber-200 text-amber-700',
  critical:   'bg-red-50   border-red-200   text-red-700',
};

const SEV_ICONS = {
  safe:       '✓',
  acceptable: '~',
  warning:    '⚠',
  critical:   '✕',
};

export default function StructureChecks({ checks }) {
  if (!checks) return null;

  const rows = [
    {
      key:   'hairpin',
      label: 'Hairpin',
      data:  checks.hairpin,
      detail: (d) => d?.dg != null ? `ΔG = ${d.dg.toFixed(2)} kcal/mol` : '—',
    },
    {
      key:   'self_dimer',
      label: 'Self-dimer',
      data:  checks.self_dimer,
      detail: (d) => d?.dg_overall != null
        ? `Overall ${d.dg_overall.toFixed(2)}, 3' ${d.dg_3prime?.toFixed(2)} kcal/mol`
        : '—',
    },
    {
      key:   'hetero_dimer',
      label: 'Hetero-dimer',
      data:  checks.hetero_dimer,
      detail: (d) => d?.dg_overall != null
        ? `Overall ${d.dg_overall.toFixed(2)}, 3' ${d.dg_3prime?.toFixed(2)} kcal/mol`
        : '—',
    },
    {
      key:   'end_stability',
      label: '3\' Stability',
      data:  checks.end_stability,
      detail: (d) => d?.stability_kcal_mol != null
        ? `${d.stability_kcal_mol.toFixed(2)} kcal/mol (last 5: ${d.last_5_bases || '—'})`
        : '—',
    },
  ];

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Structure checks</p>
      <div className="space-y-1.5">
        {rows.map(({ key, label, data, detail }) => {
          const sev  = data?.severity ?? (data?.pass === false ? 'warning' : 'safe');
          const icon = SEV_ICONS[sev] ?? '?';
          const cls  = SEV_STYLES[sev] ?? SEV_STYLES.safe;
          return (
            <div key={key} className={`flex items-start justify-between rounded-lg border px-3 py-2 gap-2 ${cls}`}>
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-bold shrink-0">{icon}</span>
                <div className="min-w-0">
                  <p className="text-xs font-semibold">{label}</p>
                  <p className="text-xs opacity-75 leading-tight">{detail(data)}</p>
                </div>
              </div>
              <span className="text-xs font-medium capitalize shrink-0">{sev}</span>
            </div>
          );
        })}
      </div>
      {checks.has_critical_flag && (
        <p className="text-xs text-red-600 font-semibold mt-1">
          ✕ One or more critical structure issues detected — this primer may form primer-dimers that mimic template.
        </p>
      )}
    </div>
  );
}
