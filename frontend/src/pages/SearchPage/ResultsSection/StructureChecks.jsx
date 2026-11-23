// StructureChecks — Pass / Warning / Fail rows for the 4 structure checks.
import { fmtDg, STATUS_CLASSES } from '../../../utils/format.js';

// API severity → the one status vocabulary.
const STATUS_OF = { safe: 'Pass', acceptable: 'Pass', warning: 'Warning', critical: 'Fail' };

export default function StructureChecks({ checks }) {
  if (!checks) return null;

  const rows = [
    {
      key:   'hairpin',
      label: 'Hairpin',
      data:  checks.hairpin,
      detail: (d) => (d?.dg != null ? `ΔG ${fmtDg(d.dg, { unit: true })}` : '—'),
    },
    {
      key:   'self_dimer',
      label: 'Self-dimer',
      data:  checks.self_dimer,
      detail: (d) => (d?.dg_overall != null
        ? `ΔG overall ${fmtDg(d.dg_overall)}, 3′ end ${fmtDg(d.dg_3prime)} kcal/mol`
        : '—'),
    },
    {
      key:   'hetero_dimer',
      label: 'Hetero-dimer',
      data:  checks.hetero_dimer,
      detail: (d) => (d?.dg_overall != null
        ? `ΔG overall ${fmtDg(d.dg_overall)}, 3′ end ${fmtDg(d.dg_3prime)} kcal/mol`
        : '—'),
    },
    {
      key:   'end_stability',
      // Primer3 reports 3′-end stability as a positive number: the −ΔG of the last 5 nt.
      label: '3′-end stability (−ΔG)',
      data:  checks.end_stability,
      detail: (d) => (d?.stability_kcal_mol != null
        ? `${fmtDg(d.stability_kcal_mol)} kcal/mol (last 5 nt: ${d.last_5_bases || '—'})`
        : '—'),
    },
  ];

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-slate-700">Structure checks</p>
      <div className="space-y-1.5">
        {rows.map(({ key, label, data, detail }) => {
          const sev = data?.severity ?? (data?.pass === false ? 'warning' : 'safe');
          const st = STATUS_OF[sev] ?? 'Pass';
          return (
            <div key={key} className={`flex items-start justify-between rounded-lg border px-3 py-2 gap-2 ${STATUS_CLASSES[st]}`}>
                <div className="min-w-0">
                  <p className="text-xs font-semibold">{label}</p>
                <p className="text-xs leading-tight text-slate-700">{detail(data)}</p>
                </div>
              <span className="text-xs font-semibold shrink-0">{st}</span>
            </div>
          );
        })}
      </div>
      {checks.has_critical_flag && (
        <p className="text-xs text-red-700 font-semibold mt-1">
          One or more critical structure issues: this primer may form primer-dimers that mimic the template.
        </p>
      )}
    </div>
  );
}
