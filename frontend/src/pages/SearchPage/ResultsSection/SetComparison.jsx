// SetComparison — the returned tiered sets side by side (review panel 2026-11-18).
// One row per set: grade, the group totals (Required S, Flexible P and F), the forward primer and the values a
// bench scientist compares first. Every value is already on the cards; this table is
// the overview that replaces opening three cards.

import { GradeBadge } from './TierSummary.jsx';
import { hasTiers } from '../../../utils/tierRank.js';

const fmt = (v, d = 1) => (v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d));

/** Closest off-target of a set: the assay ΔCq one, else the worst BLAST hit. */
function closestOffTarget(sp) {
  if (sp?.assay_dcq?.worst_target) {
    const dcq = sp.assay_dcq.min_delta_cq;
    return `${sp.assay_dcq.worst_target} (ΔCq ${dcq == null ? '> 10' : fmt(dcq)})`;
  }
  if (sp?.blast?.worst_hit) return `${sp.blast.worst_hit} (BLAST ${sp.blast.overall_risk})`;
  return 'none within 10 Cq';
}

export default function SetComparison({ top3, blastAvailable = true }) {
  const sets = (top3 || []).filter(hasTiers);
  if (sets.length < 2) return null;
  return (
    <div className="rounded-xl border border-slate-200 overflow-hidden" data-testid="set-comparison">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 border-b border-slate-200 text-slate-600">
            <tr>
              <th className="text-left px-2 py-1.5 font-semibold">Set</th>
              <th className="text-left px-2 py-1.5 font-semibold">Grade</th>
              <th className="text-right px-2 py-1.5 font-semibold" title="Required: specificity S1 + S2 + S3">S</th>
              <th className="text-right px-2 py-1.5 font-semibold" title="Flexible 2: PCR (P2)">P</th>
              <th className="text-right px-2 py-1.5 font-semibold" title="Flexible 3: composition & structure (F1 + F2 + F4 + F5)">F</th>
              <th className="text-left px-2 py-1.5 font-semibold">Forward primer 5′→3′</th>
              <th className="text-right px-2 py-1.5 font-semibold whitespace-nowrap" title="Tm of the miRNA-binding region (cycle 1)">Binding Tm</th>
              <th className="text-right px-2 py-1.5 font-semibold whitespace-nowrap">Tm</th>
              <th className="text-left px-2 py-1.5 font-semibold whitespace-nowrap">Closest off-target</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white text-slate-700 tabular-nums">
            {sets.map((s) => {
              const r = s.ranking;
              const bt = r.flexible?.binding_tm?.tm_binding;
              return (
                <tr key={s.rank}>
                  <td className="px-2 py-1.5 font-semibold">#{s.rank}</td>
                  <td className="px-2 py-1.5"><GradeBadge set={s} blastAvailable={blastAvailable} withTooltip={false} size="sm" /></td>
                  <td className="px-2 py-1.5 text-right">{r.specificity.total}/{r.specificity.max}</td>
                  <td className="px-2 py-1.5 text-right">{r.pcr.total}/{r.pcr.max}</td>
                  <td className="px-2 py-1.5 text-right">{r.flexible.total}/{r.flexible.max}</td>
                  <td className="px-2 py-1.5 font-mono break-all min-w-[11rem]">{s.sequence}</td>
                  <td className={`px-2 py-1.5 text-right whitespace-nowrap ${r.binding_floor_fail ? 'text-amber-800 font-semibold' : ''}`}>
                    {fmt(bt)} °C
                  </td>
                  <td className="px-2 py-1.5 text-right whitespace-nowrap">{fmt(s.tm_full)} °C</td>
                  <td className="px-2 py-1.5 whitespace-nowrap">{closestOffTarget(r.specificity)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
