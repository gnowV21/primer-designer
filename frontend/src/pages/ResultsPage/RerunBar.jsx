/**
 * RerunBar — the top of /results: what this result used, and how to change it.
 *
 * Collapsed, it is one line of parameter chips plus "Adjust". Opened, it shows
 * the same ParameterEditor as the designer, bound to a draft copy of the
 * active run's parameters. Nothing runs until the user presses Re-run: every
 * edit is listed as "Overhang 6 nt → 7 nt" beside the button, so they can see
 * exactly what the next run will change. A failed re-run (no candidates,
 * invalid value) is shown here and the current result stays on screen.
 *
 * Below the bar, once there is more than one run, a switcher lets the user go
 * back to any earlier run — labelled by what it changed and by its top score.
 */
import { useEffect, useMemo, useState } from 'react';
import ParameterEditor from '../../components/ParameterEditor.jsx';
import ParamChips from '../../components/ParamChips.jsx';
import ResultsSection from '../SearchPage/ResultsSection/index.jsx';
import { computeSeqAnalysis } from '../../utils/seqAnalysis.js';
import { bodyToForm } from '../../utils/designRequest.js';
import { applySamplePreset, changedPaths, diffParams } from '../../utils/paramSummary.js';

/** Short label for a run: what it changed relative to the first run kept. */
function runLabel(run, baseForm) {
  const changes = diffParams(baseForm, bodyToForm(run.params));
  if (!changes.length) return 'original';
  const head = changes.slice(0, 2).map((c) => `${c.label} ${c.to}`).join(', ');
  return changes.length > 2 ? `${head} +${changes.length - 2}` : head;
}

function topScore(run) {
  const top = run.results?.top3?.[0];
  if (!top) return null;
  return { grade: top.grade, score: Math.round(top.total_score ?? 0) };
}

export default function RerunBar({ runs, activeRun, running, onRerun, onSelectRun }) {
  const baseForm = useMemo(() => bodyToForm(activeRun.params), [activeRun]);

  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(baseForm);
  const [errors, setErrors] = useState({});
  const [failure, setFailure] = useState(null);
  const [editorKey, setEditorKey] = useState(0);

  // A different run on screen → start the draft from its parameters.
  useEffect(() => {
    setDraft(baseForm);
    setErrors({});
    setFailure(null);
    setEditorKey((k) => k + 1);
  }, [baseForm]);

  const changes = useMemo(() => diffParams(baseForm, draft), [baseForm, draft]);
  const hasErrors = Object.keys(errors).length > 0;
  const canRerun = changes.length > 0 && !hasErrors && !running;

  const seqAnalysis = useMemo(
    () => computeSeqAnalysis(draft.sequence?.matureSequence, draft.primerConstraints?.bindingRegion3prime),
    [draft]
  );

  function handleChange(group, field, value) {
    setDraft((prev) => ({ ...prev, [group]: { ...prev[group], [field]: value } }));
  }

  function handleError(field, message) {
    setErrors((prev) => {
      if (!message) {
        if (!(field in prev)) return prev;
        const next = { ...prev };
        delete next[field];
        return next;
      }
      return prev[field] === message ? prev : { ...prev, [field]: message };
    });
  }

  function discard() {
    setDraft(baseForm);
    setErrors({});
    setFailure(null);
    setEditorKey((k) => k + 1);
  }

  async function rerun() {
    if (!canRerun) return;
    setFailure(null);
    try {
      await onRerun(draft);
      setOpen(false);
    } catch (err) {
      setFailure(err);
    }
  }

  const firstForm = bodyToForm(runs[0].params);
  // A star only means something when the runs actually differ in score.
  const scores = runs.map((r) => topScore(r)?.score ?? -1);
  const bestScore = Math.max(...scores);
  const scoresDiffer = bestScore > Math.min(...scores);

  return (
    <div className="space-y-2">
      <div className={`rounded-xl border bg-white ${open ? 'border-teal-300 shadow-sm' : 'border-slate-200'}`}>

        {/* ── Summary: label + action on one row, chips full width below (no squeeze on phones) ── */}
        <div className="px-4 py-3 space-y-2">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Parameters used</p>
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              className={`shrink-0 text-xs font-semibold px-3 py-1.5 rounded-lg border transition ${
                open
                  ? 'bg-slate-100 border-slate-200 text-slate-600 hover:bg-slate-200'
                  : 'bg-teal-600 border-teal-600 text-white hover:bg-teal-700'
              }`}
            >
              {open ? 'Close' : '✎ Adjust & re-run'}
            </button>
          </div>
          <ParamChips params={open ? draft : baseForm} highlight={open ? changedPaths(changes) : new Set()} />
        </div>

        {/* ── Editor ── */}
        {open && (
          <div className="border-t border-slate-100">
            <div className="bg-slate-50/60 p-3">
              <ParameterEditor
                key={editorKey}
                params={draft}
                errors={errors}
                onChange={handleChange}
                onError={handleError}
                onApplyPreset={(preset) => setDraft((prev) => applySamplePreset(prev, preset))}
                seqAnalysis={seqAnalysis}
                openRequests={{ constraints: 1 }}
              />
            </div>

            {/* Action row — sticks to the bottom of the viewport while the editor is long. */}
            <div className="sticky bottom-0 z-10 border-t border-slate-200 bg-white/95 backdrop-blur px-4 py-3 rounded-b-xl space-y-2">
              <div className="flex items-center gap-3">
                <div className="min-w-0 flex-1 flex flex-wrap items-center gap-1.5">
                  {changes.length === 0 ? (
                    <span className="text-xs text-slate-500">Change any parameter, then re-run.</span>
                  ) : (
                    changes.map((c) => (
                      <span
                        key={`${c.group}.${c.field}`}
                        className="text-xs rounded-md px-2 py-0.5 bg-teal-50 border border-teal-200 text-teal-800 tabular-nums"
                      >
                        {c.label} <span className="text-teal-600">{c.from} →</span> <strong>{c.to}</strong>
                      </span>
                    ))
                  )}
                </div>
                {changes.length > 0 && !running && (
                  <button
                    type="button"
                    onClick={discard}
                    className="shrink-0 text-xs font-medium text-slate-500 hover:text-slate-700"
                  >
                    Discard
                  </button>
                )}
                <button
                  type="button"
                  onClick={rerun}
                  disabled={!canRerun}
                  className={`shrink-0 text-sm font-semibold px-4 py-2 rounded-lg transition ${
                    canRerun
                      ? 'bg-gradient-to-r from-teal-600 to-teal-800 text-white hover:opacity-90 shadow-sm'
                      : 'bg-slate-200 text-slate-500 cursor-not-allowed'
                  }`}
                >
                  {running ? (
                    <span className="flex items-center gap-1.5">
                      <span className="animate-spin inline-block">⟳</span> Re-running…
                    </span>
                  ) : hasErrors ? 'Fix errors' : '↻ Re-run'}
                </button>
              </div>
              {failure && (
                <div>
                  <p className="text-xs text-slate-500 mb-1.5">
                    This run did not produce primers — the result below is unchanged.
                  </p>
                  <ResultsSection results={null} error={failure} />
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Run switcher ── */}
      {runs.length > 1 && (
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Design runs">
          <span className="text-xs text-slate-500 mr-0.5">Runs</span>
          {runs.map((run, i) => {
            const active = run.id === activeRun.id;
            const s = topScore(run);
            const best = scoresDiffer && s && s.score === bestScore;
            return (
              <button
                key={run.id}
                type="button"
                onClick={() => onSelectRun(run.id)}
                aria-pressed={active}
                disabled={running}
                title={best ? 'Highest top-set score among these runs' : undefined}
                className={`text-xs rounded-lg border px-2.5 py-1 transition tabular-nums ${
                  active
                    ? 'bg-teal-600 border-teal-600 text-white'
                    : 'bg-white border-slate-200 text-slate-600 hover:border-teal-300 hover:text-teal-700'
                }`}
              >
                <span className="font-semibold">#{i + 1}</span>
                <span className={active ? 'text-teal-50' : 'text-slate-500'}> · {runLabel(run, firstForm)}</span>
                {s && (
                  <span className={`ml-1.5 font-semibold ${active ? 'text-white' : best ? 'text-teal-700' : 'text-slate-600'}`}>
                    {s.grade} {s.score}{best ? ' ★' : ''}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
