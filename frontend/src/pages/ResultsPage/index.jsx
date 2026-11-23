// ResultsPage — /results route (Phase 4 §4).
// State arrives via useLocation().state as a run history (utils/designRuns):
// the first design, plus every re-run made from the RerunBar on this page.
// Empty-state fallback when accessed directly without state.

import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import EdgeCaseBanner from './EdgeCaseBanner.jsx';
import ThermoTable from './ThermoTable.jsx';
import ExportBar from './ExportBar.jsx';
import RerunBar from './RerunBar.jsx';
import ResultsSection from '../SearchPage/ResultsSection/index.jsx';
import ProbeCard from '../../components/ProbeCard.jsx';
import VisualizationPanel from '../../components/VisualizationPanel.jsx';
import CollapsibleCard from '../../components/ui/CollapsibleCard.jsx';
import useDraftState, { setDraft } from '../../hooks/useDraftState.js';
import { saveDesign } from '../../utils/historyDb.js';
import { bodyToForm, buildDesignBody, legacySaltNote, requestDesign } from '../../utils/designRequest.js';
import { DESIGN_DRAFT_KEY, addRun, readRunsState } from '../../utils/designRuns.js';

export default function ResultsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { runs, activeId } = readRunsState(location.state);
  const activeRun = runs.find((r) => r.id === activeId);

  const [rerunning, setRerunning] = useState(false);
  // The scientific panels start folded; once opened they stay open for the session.
  const [showDetails, setShowDetails] = useDraftState('results.showDetails', false);

  useEffect(() => { document.title = 'HG Lab | Design results'; }, []);

  // Empty-state: navigated here without results
  if (!activeRun) {
    return (
      <div className="max-w-lg mx-auto mt-20 text-center space-y-4">
        <h1 className="text-xl font-semibold text-slate-700">No results yet</h1>
        <p className="text-sm text-slate-500">Run a primer design first to see results here.</p>
        <button
          onClick={() => navigate('/design')}
          className="mt-2 px-5 py-2.5 rounded-xl bg-teal-600 text-white text-sm font-semibold hover:bg-teal-700 transition"
        >
          Go to the designer
        </button>
      </div>
    );
  }

  const { results, params } = activeRun;
  const signalMethod = params?.detectionMethod?.signalMethod ?? 'taqman';
  const isTaqMan = signalMethod === 'taqman';
  // normalization_advice and the quality summary stay in the API and the PDF/CSV
  // export; they are not on the page (review 2026-11-18, owner's request).
  const { top3, metadata, edge_cases = [], lna_hints = null, probe, probe_note } = results;

  /** Run the design again with tuned parameters; on success it becomes the active run. */
  async function handleRerun(form) {
    setRerunning(true);
    try {
      const body = buildDesignBody(form);
      const data = await requestDesign(body);          // throws a displayable error object
      saveDesign(body, data);                          // best-effort, not awaited
      setDraft(DESIGN_DRAFT_KEY, form);                // the designer now opens with these values
      navigate(location.pathname, { replace: true, state: addRun(runs, body, data) });
    } finally {
      setRerunning(false);
    }
  }

  function selectRun(id) {
    navigate(location.pathname, { replace: true, state: { runs, activeId: id } });
  }

  function backToDesigner() {
    if (params?.sequence) setDraft(DESIGN_DRAFT_KEY, bodyToForm(params));
    navigate('/design');
  }

  return (
    // Wide screens: "Parameters used" is a fixed left column (sticky inside the <main>
    // scroll container) and the results are the column on the right. Phones and
    // tablets: the parameters sit on top, as before.
    <div className="max-w-6xl mx-auto pb-12 space-y-6 lg:space-y-0 lg:flex lg:items-start lg:gap-6">
      <RerunBar
        runs={runs}
        activeRun={activeRun}
        running={rerunning}
        onRerun={handleRerun}
        onSelectRun={selectRun}
        sidebar
      />

      <div className="min-w-0 flex-1 max-w-3xl mx-auto space-y-6">

      {/* ── Page header (wraps under the title on phones) ── */}
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Design results</h1>
          <p className="text-xs text-slate-600 mt-0.5 tabular-nums">
            {metadata?.mirna_id && <span className="font-medium whitespace-nowrap">{metadata.mirna_id} · </span>}
            <span className="whitespace-nowrap">{metadata?.mirna_length}-nt miRNA</span> · {top3?.length} primer set{top3?.length !== 1 ? 's' : ''} found
            {metadata?.elapsed_seconds !== undefined && <span className="whitespace-nowrap">{` · ${metadata.elapsed_seconds} s`}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={backToDesigner}
            className="text-xs px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-800 hover:bg-slate-50 font-medium transition"
          >
            Back to designer
          </button>
        </div>
      </div>

      {/* Keyed by run: switching runs remounts every panel, so no state leaks across. */}
      <div
        key={activeRun.id}
        className={`space-y-6 transition-opacity duration-200 ${rerunning ? 'opacity-40 pointer-events-none' : ''}`}
        aria-busy={rerunning}
      >
        {/* Run designed with extra K⁺ (History records before 2026-11-22 sent K⁺ 50 mM
            and an applied pH): say what it was designed with. Stored data is not changed. */}
        {legacySaltNote(params?.thermodynamic) && (
          <p data-testid="legacy-salt-note"
            className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            {legacySaltNote(params.thermodynamic)}
          </p>
        )}

        {/* ── Edge-case banners (critical + warning) ── */}
        <EdgeCaseBanner edgeCases={edge_cases} />

        {/* ── Primer set cards (reuse Phase 2/3 ResultsSection) ── */}
        <ResultsSection results={results} error={null} hideHeader />

        {/* ── Detection mode section ── */}
        {isTaqMan && probe && (
          <div>
            <h2 className="text-sm font-semibold text-slate-800 mb-2">
              TaqMan probe
            </h2>
            <ProbeCard probe={probe} probeNote={probe_note} />
          </div>
        )}
        {/* SYBR Green: no card — the mode is in "Parameters used" and the melt-curve
            check is in the protocol advice (review panel 2026-11-18). */}

        {/* ── Reaction / Melting / Gel visualization (SPEC_visualization) ──
             Outside the scientific-details toggle so it opens in one click; still
             collapsed by default because three large SVGs otherwise dominate the page. */}
        <CollapsibleCard
          title="Reaction and product visualization"
          summary="Reaction, melting curve, gel"
        >
          <VisualizationPanel results={results} params={params} />
        </CollapsibleCard>

        {/* Scientific detail — folded by default so the primers read at a glance. */}
        <button
          type="button"
          onClick={() => setShowDetails((v) => !v)}
          aria-expanded={showDetails}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-sm font-semibold text-slate-700 hover:bg-slate-100 hover:text-teal-700 transition"
        >
          <span aria-hidden className={`text-teal-700 transition-transform duration-200 ${showDetails ? 'rotate-90' : ''}`}>▸</span>
          {showDetails ? 'Hide scientific details' : 'Show scientific details'}
          <span className="text-xs font-normal text-slate-600">(thermodynamic parameters)</span>
        </button>

        {showDetails && (
          <>
            {/* ── Thermodynamics table (tabs) ── */}
            <div>
              <h2 className="text-sm font-semibold text-slate-800 mb-2">
                Thermodynamic parameters
              </h2>
              <ThermoTable results={results} params={params} />
            </div>

            {/* ── LNA hints for difficult targets (Phase 5 §D) ── */}
            {lna_hints?.applicable && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 space-y-2">
                <p className="text-xs font-semibold text-amber-800">LNA assist suggestion</p>
                <p className="text-xs text-amber-800">{lna_hints.rationale}</p>
                <div className="flex gap-2 text-xs text-amber-800">
                  {lna_hints.sources?.map((s, i) => (
                    <a key={i} href={`https://doi.org/${s.doi}`} target="_blank" rel="noopener noreferrer"
                       className="underline hover:text-amber-900">
                      [{s.tag}]
                    </a>
                  ))}
                </div>
                <p className="text-xs italic text-amber-800">{lna_hints.disclaimer}</p>
              </div>
            )}
          </>
        )}

        {/* ── Export bar — always available ── */}
        <ExportBar results={results} />
      </div>
      </div>
    </div>
  );
}
