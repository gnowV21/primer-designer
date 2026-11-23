// BenchmarkPage — Phase 7 PART F — route /benchmark
// Displays precomputed benchmark results (static JSON served by GET /api/benchmark).
// Banner "design-characteristic comparison, not experimental performance" is MANDATORY
// and cannot be hidden.

import { useState, useEffect } from 'react';
import axios from 'axios';
import NoBreak from '../components/ui/NoBreak.jsx';

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

// Metric keys → labels and units (UI review 2026-11-23: no auto-generated "Gc Percent Mean").
const METRIC_LABELS = {
  forward_tm_mean:     { label: 'Mean forward Tm', unit: '\u00a0°C' },
  gc_percent_mean:     { label: 'Mean GC', unit: '%' },
  design_success_rate: { label: 'Design success rate', unit: '%' },
  mean_design_time_s:  { label: 'Mean design time', unit: '\u00a0s' },
};
// mean_score is the old V4 0–100 score: not shown (algorithm 4.0.0 ranks by tiers).
const HIDDEN_METRICS = new Set(['mean_score']);

function MetricBar({ label, values, unit = '', lowerBetter = false }) {
  // Tools without a value (other tools were not run) are not drawn.
  const tools = Object.keys(values || {}).filter((t) => typeof values[t] === 'number');
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
      <p className="text-xs font-semibold text-slate-700">{label}</p>
      {tools.map((tool, i) => {
        const raw = values[tool];
        const num = nums[i];
        const isNA = raw == null || raw === 'N/A' || typeof raw !== 'number';
        const pct = isNA ? 0 : Math.abs(num) / maxVal * 100;
        const color = TOOL_COLORS[tool] || '#94A3B8';
        return (
          <div key={tool} className="flex items-center gap-2">
            <span className="text-xs text-slate-700 w-28 shrink-0">{TOOL_LABELS[tool] || tool}</span>
            {isNA ? (
              <span className="text-xs text-slate-700">Not run</span>
            ) : (
              <>
                <div className="flex-1 bg-slate-100 rounded-full h-3 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${pct}%`, background: color, opacity: lowerBetter ? 0.7 : 1 }}
                  />
                </div>
                <span className="text-xs text-slate-800 w-20 text-right shrink-0 tabular-nums whitespace-nowrap">
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
    document.title = 'HG Lab | Validation';
    axios.get('/api/benchmark')
      .then((r) => setData(r.data))
      .catch((e) => setError(e.message || 'Failed to load benchmark results.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-12">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">Validation</h1>
        <p className="text-sm text-slate-700 mt-0.5">
          In-silico checks of the design engine: agreement with published primer tables, a consistency
          check against the Chen 2005 rule, and a design-metric summary.
        </p>
      </div>

      {/* MANDATORY limitation banner — must always be visible */}
      <div
        className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 space-y-1"
        data-testid="benchmark-limitation-banner"
      >
        <p className="text-sm font-semibold text-amber-800">
          Design characteristics only, not experimental performance
        </p>
        <p className="text-xs text-amber-800 leading-relaxed">
          Everything on this page is computed in silico (Tm, GC, structure ΔG, predicted specificity,
          design success, speed). It says nothing about wet-lab amplification efficiency or sensitivity.
          Other tools (miRprimer, miPrimer) use linear RT primers, a different chemistry, and were not run.
        </p>
      </div>

      {/* Loading */}
      {loading && (
        <div className="text-sm text-slate-700 animate-pulse">Loading validation data…</div>
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
          <p className="text-sm font-semibold text-slate-700">Benchmark not yet run</p>
          <p className="text-xs text-slate-700">
            Run the benchmark offline to populate results:
          </p>
          <pre className="text-xs bg-white border border-slate-200 rounded px-3 py-2 font-mono text-slate-700 overflow-x-auto">
            cd benchmark{'\n'}python run_benchmark.py{'\n'}# Then commit benchmark_results.json
          </pre>
        </div>
      )}

      {/* Results */}
      {!loading && !error && data?._metadata && (
        <>
          {/* Metadata badges */}
          <div className="flex flex-wrap gap-2 text-xs">
            {data._metadata.verified === false && (
              <span className="px-2 py-1 rounded bg-amber-50 border border-amber-200 text-amber-800 font-medium">
                Preliminary, pending review
              </span>
            )}
          </div>

          {/* Metrics */}
          {data.metrics ? (
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-4 space-y-5" data-testid="design-metrics">
              <div>
                <h2 className="text-sm font-semibold text-slate-800">Design metrics</h2>
                {/* These numbers come from an older run of the engine: say which. */}
                <p className="text-xs text-slate-700 mt-0.5" data-testid="metrics-version">
                  Algorithm {String(data._metadata.tool_version || '').replace(/\s*\(.*\)/, '').replace(/^algo-/, '') || 'unknown'} result,
                  run {data._metadata.run_date}, {data._metadata.panel_size} miRNAs. Not re-run with algorithm 4.0.0.
                </p>
              </div>
              {Object.entries(data.metrics).filter(([k]) => !HIDDEN_METRICS.has(k)).map(([metricKey, metricData]) => (
                <MetricBar
                  key={metricKey}
                  label={METRIC_LABELS[metricKey]?.label
                    ?? metricKey.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())}
                  values={metricData}
                  unit={METRIC_LABELS[metricKey]?.unit ?? ''}
                  lowerBetter={metricKey.includes('dimer') || metricKey.includes('dg')}
                />
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-700">
              No metrics available yet. Run benchmark/run_benchmark.py to generate results.
            </div>
          )}

          {/* Scientific validation — real external check the null columns can't give */}
          {data.validation && (
            <div className="rounded-xl border border-teal-200 bg-white px-4 py-4 space-y-4">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <h2 className="text-sm font-semibold text-slate-800">
                  Consistency with the Chen 2005 rule (algorithm 4.0.0)
                </h2>
                <span className="px-2 py-1 rounded bg-green-50 border border-green-200 text-green-700 text-xs font-semibold">
                  {data.validation.checks_passed}/{data.validation.checks_total} checks pass
                </span>
              </div>
              <p className="text-xs text-slate-700 leading-relaxed" data-testid="consistency-note">
                A consistency check, not independent validation: the expected primers are recomputed with
                the same Chen 2005 rule the tool designs with. The independent evidence is the agreement
                with published primer tables below.
              </p>

              {/* Deterministic primer reconstruction */}
              {data.validation.deterministic_primer_targets?.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs font-semibold text-slate-700">
                    RT-primer overhang, expected (Chen 2005 rule) vs designed
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr className="text-slate-700 text-left">
                          <th className="py-1 pr-3 font-medium">miRNA</th>
                          <th className="py-1 pr-3 font-medium">Expected</th>
                          <th className="py-1 pr-3 font-medium">Designed</th>
                          <th className="py-1 pr-3 font-medium text-right whitespace-nowrap">Forward Tm</th>
                          <th className="py-1 pr-3 font-medium text-right whitespace-nowrap">Forward GC</th>
                          <th className="py-1 pr-3 font-medium text-right">Amplicon</th>
                          <th className="py-1 font-medium">Result</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-800 tabular-nums">
                        {data.validation.deterministic_primer_targets.map((t) => (
                          <tr key={t.id} className="border-t border-slate-100">
                            <td className="py-1 pr-3 whitespace-nowrap">{t.id}</td>
                            <td className="py-1 pr-3 seq">{t.rt_overhang_expected}</td>
                            <td className="py-1 pr-3 seq">{t.rt_overhang_actual}</td>
                            <td className="py-1 pr-3 text-right whitespace-nowrap">{t.forward_tm_c != null ? `${t.forward_tm_c}\u00a0°C` : '—'}</td>
                            <td className="py-1 pr-3 text-right whitespace-nowrap">{t.forward_gc_pct != null ? `${t.forward_gc_pct}%` : '—'}</td>
                            <td className="py-1 pr-3 text-right whitespace-nowrap">{t.amplicon_bp != null ? `${t.amplicon_bp}\u00a0bp` : '—'}</td>
                            <td className={`py-1 font-semibold ${t.rt_overhang_match ? 'text-green-700' : 'text-red-700'}`}>{t.rt_overhang_match ? 'Pass' : 'Fail'}</td>
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
                  <p className="text-xs font-semibold text-slate-800">
                    Agreement with published primer tables (independent evidence)
                  </p>
                  {data.validation.published_exact_match.map((p) => (
                    <div key={p.id} className="min-w-0 [overflow-wrap:anywhere] rounded-lg border border-teal-200 bg-teal-50/40 px-3 py-2 space-y-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-semibold text-slate-800 whitespace-nowrap">{p.id}</span>
                        {p.rt_exact_match === 'PASS' && (
                          <span className="px-1.5 py-0.5 rounded bg-green-50 border border-green-200 text-green-700 text-xs font-semibold">
                            RT primer identical
                          </span>
                        )}
                        {p.rt_overhang_match === 'PASS' && (
                          <span className="px-1.5 py-0.5 rounded bg-green-50 border border-green-200 text-green-700 text-xs font-semibold">
                            {p.rt_exact_match === 'PASS' ? 'Overhang matches' : 'RT overhang matches (other RT system)'}
                          </span>
                        )}
                        {p.forward_shares_specific === 'PASS' && (
                          <span className="px-1.5 py-0.5 rounded bg-green-50 border border-green-200 text-green-700 text-xs font-semibold">
                            Forward miRNA-specific region identical ({p.forward_specific_overlap_nt}{'\u00a0'}nt)
                          </span>
                        )}
                      </div>
                      {p.forward_tool_specific && (
                        <div className="text-xs text-slate-700 leading-relaxed space-y-0.5">
                          <div>
                            The forward miRNA-specific region (the part that matters biologically) is
                            identical over its full {p.forward_specific_overlap_nt}-nt overlap:
                          </div>
                          <div>
                            tool <span className="seq text-teal-800">{p.forward_tool_specific}</span>,
                            published <span className="seq text-teal-800">{p.forward_pub_specific}</span>
                          </div>
                          <div>
                            The full primers differ only in the 5′ Tm-raising tail and the specific-region
                            length (a design choice for the target Tm): tool{' '}
                            <span className="seq">{p.forward_tool}</span>, published{' '}
                            <span className="seq">{p.forward_published}</span>.
                          </div>
                        </div>
                      )}
                      {p.source && (
                        <p className="text-xs text-slate-700 overflow-x-auto"><NoBreak>{p.source}</NoBreak></p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Specificity concordance */}
              {data.validation.specificity_concordance && (
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-slate-700">
                    Family specificity concordance
                  </p>
                  <p className="text-xs text-slate-700">
                    <span className="whitespace-nowrap">{data.validation.specificity_concordance.target}</span>{' '}
                    correctly flags siblings{' '}
                    <span className="text-slate-700">
                      <NoBreak>{(data.validation.specificity_concordance.expected_cross_reactive_siblings || []).join(', ')}</NoBreak>
                    </span>{' '}
                    as cross-reactive ({data.validation.specificity_concordance.source}).
                  </p>
                </div>
              )}

              {/* Edge cases */}
              {data.validation.edge_cases?.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-slate-700">
                    Edge-case warnings fired
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {data.validation.edge_cases.map((e) => (
                      <span
                        key={e.label}
                        className="px-2 py-0.5 rounded bg-slate-100 text-slate-800 text-xs"
                      >
                        {e.label}: {e.expected}, {e.pass ? 'Pass' : 'Fail'}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {data.validation.sources?.length > 0 && (
                <details className="text-xs text-slate-700">
                  <summary className="cursor-pointer font-medium text-teal-700">Sources</summary>
                  <ul className="mt-1 space-y-0.5 pl-3 overflow-x-auto">
                    {data.validation.sources.map((s, i) => (
                      <li key={i} className="list-disc"><NoBreak>{s}</NoBreak></li>
                    ))}
                  </ul>
                </details>
              )}

              {data.validation.reproduce && (
                <pre className="text-xs bg-slate-50 border border-slate-200 rounded px-3 py-2 font-mono text-slate-700 overflow-x-auto">
                  {data.validation.reproduce}
                </pre>
              )}
            </div>
          )}

          {/* Limitations */}
          {data._metadata.limitations?.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 space-y-2">
              <p className="text-xs font-semibold text-slate-700">Known limitations</p>
              <ul className="space-y-1">
                {data._metadata.limitations.map((lim, i) => (
                  <li key={i} className="text-xs text-slate-700 flex gap-2">
                    <span className="text-slate-600 shrink-0" aria-hidden>•</span>
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
