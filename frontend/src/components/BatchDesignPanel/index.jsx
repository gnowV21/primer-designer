/**
 * BatchDesignPanel — Batch primer design UI (Phase 8 PART A)
 *
 * Accepts 1-50 miRNA IDs (one per line or comma-separated).
 * ≤10 → sync NDJSON streaming with incremental results.
 * >10 → async job + 2-second polling.
 *
 * Shares ion-condition params with the single-design form.
 */

import { useState, useEffect } from 'react';
import useBatchDesign from '../../hooks/useBatchDesign';

const RE_MIRNA = /^[a-z]{3}-(miR|let|lin|bantam)-/i;

function parseMirnaInput(raw) {
  return raw
    .split(/[\n,\t]+/)
    .map(s => s.trim())
    .filter(s => s.length > 0)
    .filter((s, i, arr) => arr.indexOf(s) === i); // dedupe
}

function classifyEntry(id) {
  return RE_MIRNA.test(id) ? 'valid' : 'warn';
}

/** Compact result card for a single miRNA in the batch */
function BatchResultCard({ item }) {
  const top = item.data?.top3?.[0];
  if (item.status === 'error') {
    return (
      <div className="border border-red-200 rounded-lg p-3 bg-red-50 text-sm">
        <div className="font-mono font-medium text-red-800">{item.mirna}</div>
        <div className="text-xs text-red-600 mt-1">{item.error}</div>
      </div>
    );
  }
  return (
    <div className="border border-gray-200 rounded-lg p-3 bg-white text-sm space-y-1">
      <div className="flex items-center justify-between">
        <span className="font-mono font-medium text-gray-800">{item.mirna}</span>
        {top && (
          <span className="text-xs bg-teal-100 text-teal-700 font-semibold px-2 py-0.5 rounded">
            Score {(top.total_score * 100).toFixed(0)}
          </span>
        )}
      </div>
      {top && (
        <>
          <div className="text-xs text-gray-600 font-mono">{top.sequence}</div>
          <div className="flex gap-3 text-xs text-gray-500">
            <span>Fwd Tm {top.tm?.toFixed(1)}°C</span>
            <span>GC {top.gc_percent?.toFixed(0)}%</span>
            <span>{top.sequence?.length} nt</span>
          </div>
        </>
      )}
    </div>
  );
}

/** Progress bar */
function ProgressBar({ completed, total }) {
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-500">
        <span>{completed} / {total} miRNAs</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-teal-500 rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/**
 * @param {{
 *   params: object,           — shared ion conditions from main form
 *   onBatchDone?: function,   — callback(results) when batch completes
 * }} props
 */
export default function BatchDesignPanel({ params = {}, onBatchDone }) {
  const [inputText, setInputText] = useState('');
  const [mirnas,    setMirnas]    = useState([]);
  const [warning,   setWarning]   = useState('');

  const { status, progress, results, errors, run, reset } = useBatchDesign();

  useEffect(() => {
    const ids = parseMirnaInput(inputText);
    setMirnas(ids);
    if (ids.length > 50) {
      setWarning(`Only the first 50 of ${ids.length} entries will be processed.`);
    } else {
      setWarning('');
    }
  }, [inputText]);

  // Auto-save & notify parent when done
  useEffect(() => {
    if (status === 'done' && onBatchDone) {
      onBatchDone(results);
    }
  }, [status, results, onBatchDone]);

  function handleRun() {
    if (mirnas.length === 0) return;
    run(mirnas.slice(0, 50), params);
  }

  const isRunning = status === 'streaming' || status === 'polling';
  const isDone    = status === 'done';
  const isError   = status === 'error';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800">Batch Design</h2>
        <p className="text-sm text-gray-500">
          Design primers for multiple miRNAs at once using shared reaction conditions.
        </p>
      </div>

      {/* Shared-params notice */}
      <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
        All miRNAs in this batch use shared ion conditions from the Designer tab.
        Tm values are comparable only when conditions are identical across assays.
      </div>

      {/* Input */}
      <div className="space-y-1">
        <label className="text-sm font-medium text-gray-700">
          miRNA IDs <span className="text-gray-400 font-normal">(one per line, or comma-separated)</span>
        </label>
        <textarea
          className="w-full h-36 border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-teal-500"
          placeholder={"hsa-miR-21-5p\nhsa-let-7a-5p\nhsa-miR-155-5p"}
          value={inputText}
          onChange={e => setInputText(e.target.value)}
          disabled={isRunning}
        />
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            {mirnas.length} miRNA{mirnas.length !== 1 ? 's' : ''} detected
            {mirnas.length > 10 && <span className="ml-1 text-blue-600">(async mode)</span>}
          </span>
          {warning && <span className="text-amber-600">{warning}</span>}
        </div>
      </div>

      {/* Input preview with validity hints */}
      {mirnas.length > 0 && mirnas.length <= 15 && status === 'idle' && (
        <div className="flex flex-wrap gap-1">
          {mirnas.map(id => (
            <span
              key={id}
              className={`text-xs font-mono px-2 py-0.5 rounded border ${
                classifyEntry(id) === 'valid'
                  ? 'bg-teal-50 border-teal-200 text-teal-700'
                  : 'bg-yellow-50 border-yellow-200 text-yellow-700'
              }`}
            >
              {id}
            </span>
          ))}
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-2">
        <button
          onClick={handleRun}
          disabled={mirnas.length === 0 || isRunning}
          className="flex-1 py-2 rounded-lg bg-teal-600 hover:bg-teal-700 text-white text-sm font-medium disabled:opacity-40 transition-colors"
        >
          {isRunning
            ? `Designing… (${progress.completed}/${progress.total})`
            : `Design ${Math.min(mirnas.length, 50)} miRNA${mirnas.length !== 1 ? 's' : ''}`}
        </button>
        {(isRunning || isDone || isError) && (
          <button
            onClick={reset}
            className="px-4 py-2 rounded-lg border border-gray-300 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Reset
          </button>
        )}
      </div>

      {/* Progress */}
      {isRunning && (
        <ProgressBar completed={progress.completed} total={progress.total} />
      )}

      {/* Status badges */}
      {(isDone || isError) && (
        <div className="flex gap-3 text-sm">
          <span className="text-green-700 font-medium">{progress.succeeded} succeeded</span>
          {progress.failed > 0 && (
            <span className="text-red-600 font-medium">{progress.failed} failed</span>
          )}
          {isDone && status === 'done' && (
            <span className="text-gray-400 text-xs self-center">Complete</span>
          )}
        </div>
      )}

      {/* Results grid */}
      {results.length > 0 && (
        <div className="space-y-2">
          <div className="text-sm font-medium text-gray-700">Results</div>
          <div className="grid gap-2 sm:grid-cols-2">
            {results.map((item, i) => (
              <BatchResultCard key={i} item={item} />
            ))}
          </div>
        </div>
      )}

      {/* Error cards */}
      {errors.length > 0 && (
        <div className="space-y-2">
          <div className="text-sm font-medium text-red-700">Errors</div>
          {errors.map((e, i) => (
            <div key={i} className="text-xs border border-red-200 bg-red-50 rounded p-2 text-red-700">
              <span className="font-mono">{e.mirna}</span>: {e.error}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
