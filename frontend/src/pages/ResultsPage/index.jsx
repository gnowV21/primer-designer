// ResultsPage — /results route (Phase 4 §4).
// State arrives via useLocation().state from SearchPage after POST /api/design.
// Empty-state fallback when accessed directly without state.

import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import EdgeCaseBanner from './EdgeCaseBanner.jsx';
import QualitySummary from './QualitySummary.jsx';
import ThermoTable from './ThermoTable.jsx';
import ExportBar from './ExportBar.jsx';
import ResultsSection from '../SearchPage/ResultsSection/index.jsx';

export default function ResultsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state;

  useEffect(() => { document.title = 'HG Lab | Primer Design Results'; }, []);

  // Empty-state: navigated here without results
  if (!state?.results) {
    return (
      <div className="max-w-lg mx-auto mt-20 text-center space-y-4">
        <p className="text-4xl">🔬</p>
        <h1 className="text-xl font-semibold text-gray-700">No results yet</h1>
        <p className="text-sm text-gray-500">Run a primer design first to see results here.</p>
        <button
          onClick={() => navigate('/')}
          className="mt-2 px-5 py-2.5 rounded-xl bg-teal-600 text-white text-sm font-semibold hover:bg-teal-700 transition"
        >
          Go to Designer →
        </button>
      </div>
    );
  }

  const { results } = state;
  const { top3, metadata, edge_cases = [] } = results;

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-12">

      {/* ── Page header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-800">Design Results</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            {metadata?.mirna_id && <span className="font-medium">{metadata.mirna_id} · </span>}
            {metadata?.mirna_length}-nt miRNA · {top3?.length} primer set{top3?.length !== 1 ? 's' : ''} found
            {metadata?.elapsed_seconds !== undefined && ` · ${metadata.elapsed_seconds}s`}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs bg-teal-50 text-teal-700 border border-teal-200 rounded-full px-3 py-1 font-medium">
            v{metadata?.algorithm_version}
          </span>
          <button
            onClick={() => navigate('/search')}
            className="text-xs px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200 font-medium transition"
          >
            ← Back
          </button>
        </div>
      </div>

      {/* ── Edge-case banners (critical + warning) ── */}
      <EdgeCaseBanner edgeCases={edge_cases} />

      {/* ── Quality summary ── */}
      <QualitySummary results={results} />

      {/* ── Primer set cards (reuse Phase 2/3 ResultsSection) ── */}
      <ResultsSection results={results} error={null} hideHeader />

      {/* ── Thermodynamics table (tabs) ── */}
      <div>
        <h2 className="text-sm font-semibold text-slate-600 mb-2 uppercase tracking-wide">
          Thermodynamic Parameters
        </h2>
        <ThermoTable results={results} />
      </div>

      {/* ── Export bar ── */}
      <ExportBar results={results} />
    </div>
  );
}
