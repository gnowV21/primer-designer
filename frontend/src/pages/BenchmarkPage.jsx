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
            <span className="text-[11px] text-slate-500 w-28 shrink-0">{TOOL_LABELS[tool] || tool}</span>
            {isNA ? (
              <span className="text-[11px] text-slate-400 italic">
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
                <span className="text-[11px] font-mono text-slate-700 w-16 text-right shrink-0">
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
        <h1 className="text-xl font-semibold text-gray-800">Tool Benchmark</h1>
        <p className="text-xs text-gray-500 mt-0.5">Design-characteristic comparison vs miRprimer / miPrimer</p>
      </div>

      {/* MANDATORY limitation banner — must always be visible */}
      <div
        className="rounded-xl border-2 border-amber-300 bg-amber-50 px-4 py-3 space-y-1"
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
          <p className="text-[11px] text-amber-600 border-t border-amber-200 pt-1 mt-1">
            {data._metadata.comparison_note}
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
          <div className="flex flex-wrap gap-2 text-[11px]">
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
              <span className="px-2 py-1 rounded bg-orange-50 border border-orange-200 text-orange-700 font-medium max-w-full break-all">
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

          {/* Limitations */}
          {data._metadata.limitations?.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 space-y-2">
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Known Limitations</p>
              <ul className="space-y-1">
                {data._metadata.limitations.map((lim, i) => (
                  <li key={i} className="text-xs text-slate-600 flex gap-2">
                    <span className="text-slate-400 shrink-0">•</span>
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
