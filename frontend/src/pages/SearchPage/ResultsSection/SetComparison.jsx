// SetComparison — the returned tiered sets side by side (review panel 2026-11-18).
// One row per set: grade, the group totals (Required S, Flexible P and F), the forward primer and the values a
// bench scientist compares first. Every value is already on the cards; this table is
// the overview that replaces opening three cards.

import { GradeBadge } from './TierSummary.jsx';
import { hasTiers } from '../../../utils/tierRank.js';

const fmt = (v, d = 1) => (v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d));

/** Closest off-target of a set: the assay ΔCq one, else the worst BLAST hit. */
export function closestOffTarget(sp) {
  if (sp?.assay_dcq?.worst_target) {
    const dcq = sp.assay_dcq.min_delta_cq;
    return `${sp.assay_dcq.worst_target} (ΔCq ${dcq == null ? '> 10' : fmt(dcq)})`;
  }
  if (sp?.blast?.worst_hit) return `${sp.blast.worst_hit} (BLAST ${sp.blast.overall_risk})`;
  return 'None within 10 Cq';
}

/** The closest off-target when it is the same for every set (then it is shown once,
 *  in "Shared by all sets"), else null. */
export function sharedClosestOffTarget(top3) {
  const sets = (top3 || []).filter(hasTiers);
  if (!sets.length) return null;
  const all = sets.map((s) => closestOffTarget(s.ranking.specificity));
  return all.every((x) => x === all[0]) ? all[0] : null;
}

const NB = '\u00a0';

export default function SetComparison({ top3, blastAvailable = true }) {
  const sets = (top3 || []).filter(hasTiers);
  if (sets.length < 2) return null;
  const showClosest = sharedClosestOffTarget(sets) === null;
  return (
    <div className="rounded-xl border border-slate-200 overflow-hidden" data-testid="set-comparison">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 border-b border-slate-200 text-slate-700">
            <tr>
              <th className="text-left px-2 py-1.5 font-semibold">Set</th>
              <th className="text-left px-2 py-1.5 font-semibold">Grade</th>
              <th className="text-right px-2 py-1.5 font-semibold" title="Specificity: BLAST off-target + assay ΔCq + Tm margin (S1 + S2 + S3)">S</th>
              <th className="text-right px-2 py-1.5 font-semibold" title="PCR: forward Tm vs annealing temperature (P2)">P</th>
              <th className="text-right px-2 py-1.5 font-semibold" title="Composition and structure: GC, 3′ GC clamp, binding Tm, secondary structure (F1, F2, F4, F5)">F</th>
              <th className="text-left px-2 py-1.5 font-semibold whitespace-nowrap">Forward primer 5′→3′</th>
              <th className="text-right px-2 py-1.5 font-semibold whitespace-nowrap" title="Tm of the miRNA-binding region (cycle 1)">Binding Tm</th>
              <th className="text-right px-2 py-1.5 font-semibold whitespace-nowrap">Tm</th>
              {showClosest && <th className="text-left px-2 py-1.5 font-semibold whitespace-nowrap">Closest off-target</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white text-slate-800 tabular-nums">
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
                  <td className="px-2 py-1.5 seq">{s.sequence}</td>
                  <td className={`px-2 py-1.5 text-right whitespace-nowrap ${r.binding_floor_fail ? 'text-amber-800 font-semibold' : ''}`}>
                    {fmt(bt)}{NB}°C
                  </td>
                  <td className="px-2 py-1.5 text-right whitespace-nowrap">{fmt(s.tm_full)}{NB}°C</td>
                  {showClosest && <td className="px-2 py-1.5 whitespace-nowrap">{closestOffTarget(r.specificity)}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="px-3 py-2 border-t border-slate-200 bg-slate-50 text-xs text-slate-700" data-testid="spf-legend">
        <strong>S</strong> specificity (BLAST, assay ΔCq, Tm margin) ranks first, then <strong>P</strong> PCR
        (forward Tm vs Ta), then <strong>F</strong> composition and structure.
      </p>
    </div>
  );
}
