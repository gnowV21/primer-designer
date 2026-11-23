/**
 * DesignPage — /design, the single designer.
 *
 * The page asks for one thing: the miRNA. Every parameter starts at its
 * documented default (constants/defaults.js) and sits folded away under
 * "Parameters"; the chips in its header say what will be used, so nothing is
 * applied silently. Opening it reveals the full editor — the same component the
 * results page uses to tune and re-run a design.
 */
import { useEffect, useMemo, useState } from 'react';
import useDesignForm from '../../hooks/useDesignForm.js';
import useDraftState from '../../hooks/useDraftState.js';
import SequenceGroup from '../SearchPage/SequenceGroup.jsx';
import ResultsSection from '../SearchPage/ResultsSection/index.jsx';
import ParameterEditor from '../../components/ParameterEditor.jsx';
import ParamChips from '../../components/ParamChips.jsx';
import {
  applySamplePreset, changedPaths, defaultParams, diffParams,
} from '../../utils/paramSummary.js';

export default function DesignPage() {
  useEffect(() => { document.title = 'HG Lab | Primer designer'; }, []);

  const {
    formData, setFormData,
    errors, handleChange, handleError, hasErrors, clearErrors,
    seqAnalysis,
    isSubmitting, canSubmit, handleSubmit,
    designError, errorRef,
  } = useDesignForm();

  // Open/closed survives a round trip to /results, like the draft itself.
  const [paramsOpen, setParamsOpen] = useDraftState('designDraft.paramsOpen', false);
  // Bumped on reset so every input remounts with the default value.
  const [editorKey, setEditorKey] = useState(0);

  const changes = useMemo(() => diffParams(defaultParams(), formData), [formData]);
  const isTaqMan = formData.detectionMethod.signalMethod === 'taqman';

  function resetToDefaults() {
    setFormData((prev) => ({ ...prev, ...defaultParams() }));
    clearErrors();
    setEditorKey((k) => k + 1);
  }

  return (
    <div className="max-w-2xl mx-auto space-y-5 pb-12">

      {/* ── Header ── */}
      <div>
        <h1 className="text-xl font-semibold text-slate-700">Design your primers</h1>
        <p className="text-sm text-slate-500 mt-1">
          Enter a miRNA. Everything else starts at validated defaults.
        </p>
      </div>

      {/* ── miRNA ── */}
      <SequenceGroup
        data={formData.sequence}
        errors={errors}
        onChange={(field, value) => handleChange('sequence', field, value)}
        onError={handleError}
        seqAnalysis={seqAnalysis}
        openRequested={0}
        bare
      />

      {/* ── Parameters (folded by default) ── */}
      {/* One trigger: the whole header row is the button (Show / Hide on the right). */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <button
          type="button"
          onClick={() => setParamsOpen((v) => !v)}
          aria-expanded={paramsOpen}
          aria-controls="design-parameters"
          className="w-full flex items-center gap-2 sm:gap-2.5 px-3 sm:px-4 py-3 text-left hover:bg-slate-50 transition-colors"
        >
          <span aria-hidden className={`text-teal-700 text-sm font-bold leading-none transition-transform duration-200 ${paramsOpen ? 'rotate-90' : ''}`}>
            ▸
          </span>
          <span className="min-w-0 flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-sm font-semibold text-slate-800">Parameters</span>
            {hasErrors ? (
              <span className="whitespace-nowrap text-xs font-semibold rounded-full px-2.5 py-0.5 bg-red-50 text-red-700 border border-red-300">
                Needs a fix
              </span>
            ) : (
              <span className={`whitespace-nowrap text-xs font-semibold rounded-full px-2.5 py-0.5 border ${changes.length
                  ? 'bg-teal-600 text-white border-teal-600'
                : 'bg-teal-50 text-teal-700 border-teal-300'}`}>
                {changes.length ? `${changes.length} changed` : 'Defaults'}
              </span>
            )}
          </span>
          <span className="ml-auto shrink-0 text-xs font-semibold text-teal-700">
            {paramsOpen ? 'Hide' : 'Show'}
          </span>
        </button>

        {!paramsOpen && (
          <ParamChips params={formData} highlight={changedPaths(changes)} className="px-3 sm:px-4 pb-3 -mt-0.5" />
        )}

        {paramsOpen && (
          <div id="design-parameters" className="border-t border-slate-100 bg-slate-50/60 p-3 space-y-3">
            <ParameterEditor
              key={editorKey}
              params={formData}
              errors={errors}
              onChange={handleChange}
              onError={handleError}
              onApplyPreset={(preset) => setFormData((prev) => applySamplePreset(prev, preset))}
              seqAnalysis={seqAnalysis}
              groupsOpen
            />
            {changes.length > 0 && (
              <div className="flex items-center justify-between gap-3 px-1">
                <p className="text-xs text-slate-500 truncate">
                  Changed: {changes.map((c) => c.label).join(', ')}
                </p>
                <button
                  type="button"
                  onClick={resetToDefaults}
                  className="shrink-0 text-xs font-medium text-teal-700 hover:underline"
                >
                  Reset to defaults
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Submit ── */}
      <div className="space-y-2 pt-1">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className={`w-full py-3 px-6 rounded-xl text-sm font-semibold transition-all ${!canSubmit
            ? 'bg-slate-200 text-slate-700 cursor-not-allowed'
            : 'bg-teal-600 text-white shadow-md hover:bg-teal-700 active:scale-[0.99]'}`}
        >
          {isSubmitting ? (
            <span className="flex items-center justify-center gap-2">
              <span className="animate-spin inline-block" aria-hidden>⟳</span> Processing…
            </span>
          ) : hasErrors ? (
            'Fix errors to continue'
          ) : !seqAnalysis ? (
            'Enter a miRNA to continue'
          ) : (
            'Design primers'
          )}
        </button>
        <p className="text-center text-xs text-slate-600">
          Designs the stem-loop RT primer, the forward primer and the universal reverse
          primer{isTaqMan ? ', plus a TaqMan probe' : ''}. You can change parameters again on the results page.
        </p>
      </div>

      {/* ── Design error ── */}
      {designError && (
        <div ref={errorRef}>
          <ResultsSection results={null} error={designError} />
        </div>
      )}
    </div>
  );
}
