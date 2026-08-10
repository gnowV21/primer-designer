// ResultsPage — /results route (Phase 4 §4).
// State arrives via useLocation().state from SearchPage after POST /api/design.
// Empty-state fallback when accessed directly without state.

import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import EdgeCaseBanner from './EdgeCaseBanner.jsx';
import QualitySummary from './QualitySummary.jsx';
import ThermoTable from './ThermoTable.jsx';
import ExportBar from './ExportBar.jsx';
import ProtocolAdvisor from './ProtocolAdvisor.jsx';
import ResultsSection from '../SearchPage/ResultsSection/index.jsx';
import ProbeCard from '../../components/ProbeCard.jsx';
import MultiplexPanel from '../../components/MultiplexPanel.jsx';
import NormalizationAdvisor from '../../components/NormalizationAdvisor.jsx';

export default function ResultsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state;
  // Lifted so the page-level BLAST result (run inside QualitySummary) can be
  // handed to ExportBar and embedded in the exported report.
  const [blastResult, setBlastResult] = useState(null);

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

  const { results, params } = state;
  const signalMethod = params?.detectionMethod?.signalMethod ?? 'taqman';
  const isTaqMan = signalMethod === 'taqman';
  const { top3, metadata, edge_cases = [], protocol_advice = [], lna_hints = null, probe, probe_note, normalization_advice = null } = results;

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-12">

      {/* ── Page header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-800">Design Results</h1>
          <p className="text-xs text-gray-500 mt-0.5 tabular-nums">
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
      <QualitySummary results={results} onBlastResult={setBlastResult} />

      {/* ── Primer set cards (reuse Phase 2/3 ResultsSection) ── */}
      <ResultsSection results={results} error={null} hideHeader />

      {/* ── Detection mode section ── */}
      {isTaqMan && probe && (
        <div>
          <h2 className="text-sm font-semibold text-slate-600 mb-2 uppercase tracking-wide">
            TaqMan Probe
          </h2>
          <ProbeCard probe={probe} probeNote={probe_note} />
        </div>
      )}
      {!isTaqMan && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 flex items-start gap-3">
          <span className="text-xl mt-0.5">🧪</span>
          <div>
            <p className="text-sm font-semibold text-amber-800">SYBR Green mode — no probe designed</p>
            <p className="text-xs text-amber-700 mt-0.5">
              Amplicon size is constrained to ≤ 120 bp. Melting curve analysis is mandatory after every run to confirm product specificity.
            </p>
          </div>
        </div>
      )}

      {/* ── Thermodynamics table (tabs) ── */}
      <div>
        <h2 className="text-sm font-semibold text-slate-600 mb-2 uppercase tracking-wide">
          Thermodynamic Parameters
        </h2>
        <ThermoTable results={results} params={params} />
      </div>

      {/* ── Protocol Advisor (Phase 5 §A) — collapsed by default ── */}
      <ProtocolAdvisor advice={protocol_advice} />

      {/* ── Normalization Advisor (Phase 7 §D) — shown when sample_type provided ── */}
      {normalization_advice && (
        <NormalizationAdvisor advice={normalization_advice} />
      )}

      {/* ── LNA hints for difficult targets (Phase 5 §D) ── */}
      {lna_hints?.applicable && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 space-y-2">
          <p className="text-xs font-semibold text-amber-800 uppercase tracking-wide">LNA Assist Suggestion</p>
          <p className="text-xs text-amber-800">{lna_hints.rationale}</p>
          <div className="flex gap-2 text-xs text-amber-700">
            {lna_hints.sources?.map((s, i) => (
              <a key={i} href={`https://doi.org/${s.doi}`} target="_blank" rel="noopener noreferrer"
                 className="underline hover:text-amber-900">
                [{s.tag}]
              </a>
            ))}
          </div>
          <p className="text-xs italic text-amber-600">{lna_hints.disclaimer}</p>
        </div>
      )}

      {/* ── Export bar ── */}
      <ExportBar results={results} blastResult={blastResult} />

      {/* ── Multiplex panel check (Phase 6 §B) — standalone tool, always available ── */}
      <div>
        <h2 className="text-sm font-semibold text-slate-600 mb-2 uppercase tracking-wide">
          Multiplex Panel Check
        </h2>
        <MultiplexPanel />
      </div>
    </div>
  );
}
