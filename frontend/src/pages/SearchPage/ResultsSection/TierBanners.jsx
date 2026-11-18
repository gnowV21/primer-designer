// TierBanners — design-level notices of the tiered ranking (SPEC_ui_tiered_4.0.0 §2.3).
// Reads `ranking_summary`, `global_warnings` and `overhang_suggestion` of /api/design.
// The same warnings are skipped in the generic warning lists (TIER_WARNING_FIELDS).

/** global_warnings fields shown here; the generic lists skip them. */
export const TIER_WARNING_FIELDS = new Set(['specificity_fallback', 'fewer_than_3_sets', 'blast_unavailable']);

/** Off-targets that caused the elimination, from the returned sets: S2 worst_target and
 *  S1 worst_hit, de-duplicated, in rank order. */
export function fallbackOffTargets(top3) {
  const out = [];
  for (const s of top3 || []) {
    const sp = s.ranking?.specificity;
    if (!sp) continue;
    for (const name of [sp.assay_dcq?.worst_target, sp.blast?.worst_hit]) {
      if (name && !out.includes(name)) out.push(name);
    }
  }
  return out;
}

export default function TierBanners({ results }) {
  const rs = results?.ranking_summary;
  if (!rs || rs.system !== 'tiered') return null;
  const top3 = results.top3 || [];
  const warnings = results.global_warnings || [];
  const has = (f) => warnings.some((w) => w.field === f);
  const os = results.overhang_suggestion;
  const offTargets = rs.specificity_fallback ? fallbackOffTargets(top3) : [];

  return (
    <div className="space-y-2">
      {rs.specificity_fallback && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 space-y-1" data-testid="banner-fallback">
          <p className="font-semibold">No candidate passed the specificity screen.</p>
          <p>
            Every forward candidate fails on BLAST (CRITICAL) or on the assay ΔCq (CO-AMPLIFIED). The sets
            below are the least bad ones (grade C); the assay will likely co-detect
            {offTargets.length ? <> <span className="font-mono">{offTargets.join(', ')}</span>.</> : ' another miRNA.'}
          </p>
          <p className="font-medium">Include a cross-reactivity control (synthetic off-target) in the wet-lab run.</p>
        </div>
      )}
      {rs.blast_available === false && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800" data-testid="banner-blast-unavailable">
          Specificity ranking reduced to S2 + S3 (BLAST not run)
          {rs.blast_unavailable_reason && <span className="text-amber-700"> · {rs.blast_unavailable_reason}</span>}
        </div>
      )}
      {rs.screen_species_assumed && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800" data-testid="banner-species-assumed">
          Specificity screened against <span className="font-semibold">human (hsa)</span> miRNAs:
          no miRBase species was given. The grade holds for a human sample only; pick the
          species, or enter a miRBase name, to screen against the right miRNAs.
        </div>
      )}
      {has('fewer_than_3_sets') && (
        <div className="rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-800" data-testid="banner-fewer-sets">
          {rs.returned_sets ?? top3.length} primer set{(rs.returned_sets ?? top3.length) === 1 ? '' : 's'} returned:
          the other candidates were eliminated on specificity, or too few were generated.
        </div>
      )}
      {os && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 space-y-1" data-testid="overhang-suggestion">
          <p className="font-semibold">
            Overhang suggestion: {os.length} nt
            {os.length !== 6 && (
              <span className="ml-2 text-xs font-medium text-amber-800 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5">
                off-label · not wet-lab verified
              </span>
            )}
          </p>
          <p className="text-xs font-medium text-slate-600">Suggestion only — the primer sets below were not changed.</p>
          <p className="text-xs text-slate-600">{os.note}</p>
        </div>
      )}
    </div>
  );
}
