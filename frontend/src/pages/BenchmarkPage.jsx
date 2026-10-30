// BenchmarkPage — Phase 7 PART F — route /benchmark
// Displays precomputed benchmark results (static JSON served by GET /api/benchmark).
// Banner "design-characteristic comparison, not experimental performance" is MANDATORY
// and cannot be hidden.

import { useState, useEffect } from 'react';
import axios from 'axios';

// ── Grouped bar chart (SVG, no lib) ──────────────────────────────────────────

const TOOL_COLORS = {
  this_tool: '#0F6E56',
  mirprimer: '#3B82F6',
  miprimer:  '#8B5CF6',
};
const TOOL_LABELS = {
  this_tool: 'HG Lab (this tool)',
  mirprimer: 'miRprimer',
  miprimer:  'miPrimer',
};

function MetricBar({ label, values, unit = '', lowerBetter = false }) {
  const tools = Object.keys(values || {});
  if (tools.length === 0) return null;

  // Normalize bar widths to percentage of max
  const nums = tools.map((t) => {
    const v = values[t];
    if (v == null || v === 'N/A' || typeof v !== 'number') return null;
    return v;
  });
  const validNums = nums.filter((n) => n !== null);
  const maxVal = validNums.length > 0 ? Math.max(...validNums.map(Math.abs)) : 1;

  return (
    <div className="space-y-1.5">
      <p className="text-xs font-semibold text-slate-600">{label}</p>
      {tools.map((tool, i) => {
        const raw = values[tool];
        const num = nums[i];
        const isNA = raw == null || raw === 'N/A' || typeof raw !== 'number';
        const pct = isNA ? 0 : Math.abs(num) / maxVal * 100;
        const color = TOOL_COLORS[tool] || '#94A3B8';
        return (
          <div key={tool} className="flex items-center gap-2">
            <span className="text-xs text-slate-500 w-28 shrink-0">{TOOL_LABELS[tool] || tool}</span>
            {isNA ? (
              <span className="text-xs text-slate-500 italic">
                N/A (compared via published examples)
              </span>
            ) : (
              <>
                <div className="flex-1 bg-slate-100 rounded-full h-3 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${pct}%`, background: color, opacity: lowerBetter ? 0.7 : 1 }}
                  />
                </div>
                <span className="text-xs font-mono text-slate-700 w-16 text-right shrink-0">
                  {typeof num === 'number' ? num.toFixed(1) : raw}{unit}
                </span>
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function BenchmarkPage() {
  const [data, setData]   = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.title = 'HG Lab | Benchmark';
    axios.get('/api/benchmark')
      .then((r) => setData(r.data))
      .catch((e) => setError(e.message || 'Failed to load benchmark results.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-12">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">Tool Benchmark</h1>
        <p className="text-xs text-slate-500 mt-0.5">Design-characteristic comparison vs miRprimer / miPrimer</p>
      </div>

      {/* MANDATORY limitation banner — must always be visible */}
      <div
        className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 space-y-1"
        data-testid="benchmark-limitation-banner"
      >
        <p className="text-sm font-semibold text-amber-800">
          ⚠ Important: Design characteristics only — not experimental performance
        </p>
        <p className="text-xs text-amber-700 leading-relaxed">
          This comparison evaluates <strong>in-silico design metrics</strong> (Tm, GC%, structure ΔG,
          predicted specificity, design success rate, speed). It does <strong>NOT</strong> compare
          wet-lab PCR amplification efficiency or experimental sensitivity. Tools use{' '}
          <strong>different RT chemistries</strong>: HG Lab uses Chen 2005 stem-loop RT-qPCR;
          miRprimer and miPrimer use linear RT primers — direct efficiency comparison is not valid.
        </p>
        {data?._metadata?.comparison_note && (
          <p className="text-xs text-amber-600 border-t border-amber-200 pt-1 mt-1">
            {data._metadata.comparison_note}
          </p>
        )}
        {data?._metadata?.validation_note && (
          <p className="text-xs text-amber-700 pt-1">
            {data._metadata.validation_note}
          </p>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="text-sm text-slate-500 animate-pulse">Loading benchmark data…</div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Data unavailable */}
      {!loading && !error && (!data || data.available === false || !data._metadata) && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-4 space-y-2">
          <p className="text-sm font-semibold text-slate-600">Benchmark not yet run</p>
          <p className="text-xs text-slate-500">
            Run the benchmark offline to populate results:
          </p>
          <pre className="text-xs bg-white border border-slate-200 rounded px-3 py-2 font-mono text-slate-700">
            cd benchmark{'\n'}python run_benchmark.py{'\n'}# Then commit benchmark_results.json
          </pre>
        </div>
      )}

      {/* Results */}
      {!loading && !error && data?._metadata && (
        <>
          {/* Metadata badges */}
          <div className="flex flex-wrap gap-2 text-xs">
            {data._metadata.run_date && (
              <span className="px-2 py-1 rounded bg-slate-100 text-slate-600 font-medium">
                Run: {data._metadata.run_date}
              </span>
            )}
            {data._metadata.panel_size > 0 && (
              <span className="px-2 py-1 rounded bg-slate-100 text-slate-600 font-medium">
                Panel: {data._metadata.panel_size} miRNAs
              </span>
            )}
            {data._metadata.tool_version && (
              <span className="px-2 py-1 rounded bg-teal-50 border border-teal-200 text-teal-700 font-medium">
                {data._metadata.tool_version}
              </span>
            )}
            {data._metadata.verified === false && (
              <span className="px-2 py-1 rounded bg-amber-50 border border-amber-200 text-amber-700 font-medium">
                Preliminary — pending review
              </span>
            )}
            {data._metadata.status && (
              <span className="px-2 py-1 rounded bg-amber-50 border border-amber-200 text-amber-700 font-medium max-w-full break-all">
                {data._metadata.status}
              </span>
            )}
          </div>

          {/* Metrics */}
          {data.metrics ? (
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-4 space-y-5">
              <h2 className="text-sm font-semibold text-slate-700">Design Metrics Comparison</h2>
              {Object.entries(data.metrics).map(([metricKey, metricData]) => (
                <MetricBar
                  key={metricKey}
                  label={metricKey.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  values={metricData}
                  unit={metricKey.includes('tm') ? '°C' : metricKey.includes('dg') ? ' kcal/mol' : ''}
                  lowerBetter={metricKey.includes('dimer') || metricKey.includes('dg')}
                />
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500 italic">
              No metrics available yet. Run benchmark/run_benchmark.py to generate results.
            </div>
          )}

          {/* Scientific validation — real external check the null columns can't give */}
          {data.validation && (
            <div className="rounded-xl border border-teal-200 bg-white px-4 py-4 space-y-4">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <h2 className="text-sm font-semibold text-slate-700">
                  Scientific Validation — vs published methodology
                </h2>
                <span className="px-2 py-1 rounded bg-teal-50 border border-teal-200 text-teal-700 text-xs font-semibold">
                  {data.validation.checks_passed}/{data.validation.checks_total} checks passed
                  {typeof data.validation.success_rate === 'number' &&
                    ` (${(data.validation.success_rate * 100).toFixed(0)}%)`}
                </span>
              </div>

              {data.validation.method && (
                <p className="text-xs text-slate-500 leading-relaxed">{data.validation.method}</p>
              )}

              {/* Deterministic primer reconstruction */}
              {data.validation.deterministic_primer_targets?.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                    RT-primer overhang — expected vs designed (Chen 2005 deterministic)
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr className="text-slate-500 text-left">
                          <th className="py-1 pr-3 font-medium">miRNA</th>
                          <th className="py-1 pr-3 font-medium">Expected</th>
                          <th className="py-1 pr-3 font-medium">Designed</th>
                          <th className="py-1 pr-3 font-medium">Fwd Tm</th>
                          <th className="py-1 pr-3 font-medium">Fwd GC%</th>
                          <th className="py-1 pr-3 font-medium">Amplicon</th>
                          <th className="py-1 font-medium">Match</th>
                        </tr>
                      </thead>
                      <tbody className="font-mono text-slate-700">
                        {data.validation.deterministic_primer_targets.map((t) => (
                          <tr key={t.id} className="border-t border-slate-100">
                            <td className="py-1 pr-3">{t.id}</td>
                            <td className="py-1 pr-3">{t.rt_overhang_expected}</td>
                            <td className="py-1 pr-3">{t.rt_overhang_actual}</td>
                            <td className="py-1 pr-3">{t.forward_tm_c != null ? `${t.forward_tm_c}°C` : '—'}</td>
                            <td className="py-1 pr-3">{t.forward_gc_pct != null ? `${t.forward_gc_pct}%` : '—'}</td>
                            <td className="py-1 pr-3">{t.amplicon_bp != null ? `${t.amplicon_bp} bp` : '—'}</td>
                            <td className="py-1">{t.rt_overhang_match ? '✓' : '✗'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Published exact-match — the strongest external check */}
              {data.validation.published_exact_match?.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                    Exact match vs a published primer table
                  </p>
                  {data.validation.published_exact_match.map((p) => (
                    <div key={p.id} className="rounded-lg border border-teal-200 bg-teal-50/40 px-3 py-2 space-y-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-xs font-semibold text-slate-700">{p.id}</span>
                        {p.rt_exact_match === 'PASS' && (
                          <span className="px-1.5 py-0.5 rounded bg-teal-100 text-teal-800 text-xs font-semibold">
                            RT primer byte-identical ✓
                          </span>
                        )}
                        {p.rt_overhang_match === 'PASS' && (
                          <span className="px-1.5 py-0.5 rounded bg-teal-100 text-teal-800 text-xs font-semibold">
                            {p.rt_exact_match === 'PASS' ? 'overhang ✓' : 'RT overhang ✓ (cross-system)'}
                          </span>
                        )}
                        {p.forward_shares_specific === 'PASS' && (
                          <span className="px-1.5 py-0.5 rounded bg-teal-100 text-teal-800 text-xs font-semibold">
                            forward specific-region identical ({p.forward_specific_overlap_nt} nt) ✓
                          </span>
                        )}
                      </div>
                      {p.forward_tool_specific && (
                        <div className="text-xs text-slate-500 leading-relaxed space-y-0.5">
                          <div>
                            Forward miRNA-specific region (the biologically meaningful part) is
                            byte-identical over its full {p.forward_specific_overlap_nt}-nt overlap:
                          </div>
                          <div className="font-mono text-slate-600">
                            tool <span className="text-teal-700">{p.forward_tool_specific}</span> ·
                            published <span className="text-teal-700">{p.forward_pub_specific}</span>
                          </div>
                          <div className="text-slate-500">
                            The two full primers differ only by the 5′ Tm-raising tail and specific-region
                            length (design choice for the target Tm, not scored): tool{' '}
                            <span className="font-mono">{p.forward_tool}</span> vs published{' '}
                            <span className="font-mono">{p.forward_published}</span>.
                          </div>
                        </div>
                      )}
                      {p.source && (
                        <p className="text-xs text-slate-500 italic">{p.source}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Specificity concordance */}
              {data.validation.specificity_concordance && (
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                    Family specificity concordance
                  </p>
                  <p className="text-xs text-slate-600">
                    <span className="font-mono">{data.validation.specificity_concordance.target}</span>{' '}
                    correctly flags siblings{' '}
                    <span className="font-mono text-slate-500">
                      {(data.validation.specificity_concordance.expected_cross_reactive_siblings || []).join(', ')}
                    </span>{' '}
                    as cross-reactive — {data.validation.specificity_concordance.source}
                  </p>
                </div>
              )}

              {/* Edge cases */}
              {data.validation.edge_cases?.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                    Edge-case warnings fired
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {data.validation.edge_cases.map((e) => (
                      <span
                        key={e.label}
                        className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-xs font-mono"
                      >
                        {e.label} → {e.expected} {e.pass ? '✓' : '✗'}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {data.validation.sources?.length > 0 && (
                <details className="text-xs text-slate-500">
                  <summary className="cursor-pointer font-medium text-slate-600">Sources</summary>
                  <ul className="mt-1 space-y-0.5 pl-3">
                    {data.validation.sources.map((s, i) => (
                      <li key={i} className="list-disc">{s}</li>
                    ))}
                  </ul>
                </details>
              )}

              {data.validation.reproduce && (
                <pre className="text-xs bg-slate-50 border border-slate-200 rounded px-3 py-2 font-mono text-slate-600 overflow-x-auto">
                  {data.validation.reproduce}
                </pre>
              )}
            </div>
          )}

          {/* Limitations */}
          {data._metadata.limitations?.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 space-y-2">
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Known Limitations</p>
              <ul className="space-y-1">
                {data._metadata.limitations.map((lim, i) => (
                  <li key={i} className="text-xs text-slate-600 flex gap-2">
                    <span className="text-slate-500 shrink-0">•</span>
                    {lim}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
