// OverhangComparison — shows 5 / 6 / 7 nt overhang evaluation side-by-side
// and highlights the recommended length.

export default function OverhangComparison({ comparison, recommended }) {
  if (!comparison || comparison.length === 0) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          Overhang Length Comparison (5 / 6 / 7 nt)
        </p>
        <span className="text-xs text-teal-700 bg-teal-50 border border-teal-200 rounded-full px-2 py-0.5 font-medium">
          Recommended: {recommended} nt
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {comparison.map((o) => (
          <OverhangCard key={o.length} data={o} />
        ))}
      </div>

      <p className="text-xs text-slate-500 pt-1 border-t border-slate-100">
        Composite score = 60 % best primer quality + 40 % stemloop MFE quality.
        Candidates found with default constraints.
      </p>
    </div>
  );
}

function OverhangCard({ data }) {
  const {
    length, overhang_rna, mfe, mfe_method, tm_full, gc_percent,
    candidates_found, best_primer_score, mfe_score, composite_score,
    is_recommended, viable, mfe_in_range,
  } = data;

  const border = is_recommended
    ? 'border-teal-400 bg-teal-50 shadow-sm shadow-teal-100'
    : viable
      ? 'border-slate-200 bg-slate-50'
      : 'border-red-200 bg-red-50 opacity-70';

  return (
    <div className={`rounded-lg border px-3 py-2.5 space-y-2 ${border}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className={`text-sm font-bold ${is_recommended ? 'text-teal-700' : 'text-slate-600'}`}>
          {length} nt
        </span>
        {is_recommended && (
          <span className="text-xs font-semibold text-teal-600">★ Best</span>
        )}
        {!viable && (
          <span className="text-xs font-semibold text-red-500">No candidates</span>
        )}
      </div>

      {/* Overhang sequence */}
      <div>
        <p className="text-xs text-slate-500 mb-0.5">3' overhang (miRNA)</p>
        <span className="font-mono text-xs text-slate-700 tracking-wider">{overhang_rna}</span>
      </div>

      {/* Stemloop metrics */}
      <div className="space-y-1 text-xs text-slate-600">
        <Row label="Stemloop MFE" value={`${mfe?.toFixed(2)} kcal/mol`}
          badge={mfe_in_range ? 'ok' : 'warn'}
          sub={mfe_method?.includes('primer3') ? 'DNA proxy' : mfe_method}
        />
        <Row label="Stemloop Tm" value={`${tm_full?.toFixed(1)}°C`} />
        <Row label="GC" value={`${gc_percent}%`} />
      </div>

      {/* Divider */}
      <div className="border-t border-slate-200" />

      {/* Forward primer metrics */}
      <div className="space-y-1 text-xs text-slate-600">
        <Row label="Candidates" value={candidates_found} />
        {viable && <Row label="Best primer" value={`${best_primer_score}`} unit="/100" />}
        {viable && <Row label="MFE quality" value={`${mfe_score?.toFixed(0)}`} unit="/100" />}
      </div>

      {/* Composite score bar */}
      {viable && (
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-slate-500">Composite</span>
            <span className={`font-bold ${is_recommended ? 'text-teal-700' : 'text-slate-600'}`}>
              {composite_score}
            </span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full ${is_recommended ? 'bg-teal-500' : 'bg-slate-400'}`}
              style={{ width: `${Math.min(100, composite_score)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value, unit = '', badge, sub }) {
  return (
    <div className="flex justify-between items-center gap-1">
      <span className="text-slate-500 shrink-0">{label}</span>
      <span className="flex items-center gap-1">
        {badge === 'ok' && <span className="text-teal-500 text-xs">✓</span>}
        {badge === 'warn' && <span className="text-amber-500 text-xs">⚠</span>}
        <strong className="tabular-nums">{value}{unit}</strong>
        {sub && <span className="text-slate-500 text-xs">({sub})</span>}
      </span>
    </div>
  );
}
