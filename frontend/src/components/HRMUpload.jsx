import { useRef, useState } from 'react';
import { analyzeHrm } from '../api/chatApi.js';
import { useHrmSession } from '../contexts/HrmSessionContext.jsx';

/**
 * HRMUpload — upload a melt-curve file and show the numeric table it produced.
 *
 * The table is the contract of SPEC_Phase1 §4.3: these numbers, computed in Python,
 * are the only HRM facts the assistant is allowed to cite. Showing them next to the
 * chat is what lets the user check the model against the algorithm.
 */

const FLAG_STYLE = {
  match:   { cls: 'text-teal-700 bg-teal-50 border-teal-200',       label: 'match'   },
  shifted: { cls: 'text-amber-700 bg-amber-50 border-amber-200',    label: 'shifted' },
  suspect: { cls: 'text-red-600 bg-red-50 border-red-200',          label: 'suspect' },
  noise:   { cls: 'text-gray-500 bg-gray-50 border-gray-200',       label: 'noise'   },
  control: { cls: 'text-slate-600 bg-slate-100 border-slate-200',   label: 'control' },
};

export default function HRMUpload({ result, onResult, onClear }) {
  const { send } = useHrmSession();
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  async function handleFile(file) {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      onResult(await analyzeHrm(file));
    } catch (err) {
      setError(err);
      onClear();
    } finally {
      setLoading(false);
    }
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files?.[0]);
  }

  function clear() {
    if (inputRef.current) inputRef.current.value = '';
    setError(null);
    onClear();
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700">HRM data</h2>
        {result && (
          <button type="button" onClick={clear}
                  className="text-[11px] text-gray-400 hover:text-gray-600 underline">
            Clear
          </button>
        )}
      </div>

      {!result && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl px-4 py-8 text-center cursor-pointer transition-colors ${
            dragging ? 'border-teal-400 bg-teal-50' : 'border-gray-200 hover:border-teal-300 hover:bg-gray-50'
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.tsv,.txt,.xls,.xlsx"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          {loading ? (
            <p className="text-xs text-teal-700 font-medium">Analyzing melt curves…</p>
          ) : (
            <>
              <p className="text-xs font-medium text-gray-600">
                Drop a melt-curve file here, or click to browse
              </p>
              <p className="text-[11px] text-gray-400 mt-1">
                CSV / TSV / XLS / XLSX — a temperature column plus one column per well.
                Name a column <code className="text-gray-500">positive_ctrl</code> to get ΔTm.
              </p>
            </>
          )}
        </div>
      )}

      {error && (
        <div className="border border-red-200 bg-red-50 rounded-lg px-3 py-2">
          <p className="text-xs font-semibold text-red-600">{error.error}</p>
          {error.message && <p className="text-[11px] text-red-500 mt-0.5">{error.message}</p>}
        </div>
      )}

      {result && (
        <>
          {result.warnings?.length > 0 && (
            <div className="border border-amber-200 bg-amber-50 rounded-lg px-3 py-2 space-y-1">
              {result.warnings.map((w, i) => (
                <p key={i} className="text-[11px] text-amber-700 leading-snug">⚠ {w}</p>
              ))}
            </div>
          )}

          <p className="text-[11px] text-gray-400">
            Computed by the algorithm — T_pre {result.params.T_pre}°C, T_post{' '}
            {result.params.T_post}°C ({result.params.confidence} confidence).
            The assistant may only quote numbers from this table.{' '}
            <span className="text-teal-600 font-medium">Click any row to ask about that well.</span>
          </p>

          <div className="overflow-x-auto border border-gray-200 rounded-xl">
            <table className="w-full text-[11px] whitespace-nowrap">
              <thead className="bg-gray-50 text-gray-500">
                <tr>
                  <th className="text-left  font-semibold px-3 py-2">Sample</th>
                  <th className="text-right font-semibold px-3 py-2">Tm (°C)</th>
                  <th className="text-right font-semibold px-3 py-2">Peaks</th>
                  <th className="text-right font-semibold px-3 py-2">Height</th>
                  <th className="text-right font-semibold px-3 py-2">FWHM (°C)</th>
                  <th className="text-right font-semibold px-3 py-2">ΔTm (°C)</th>
                  <th className="text-left  font-semibold px-3 py-2">Flag</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {Object.entries(result.features).map(([name, f]) => {
                  const style = FLAG_STYLE[f.flag] ?? FLAG_STYLE.noise;
                  return (
                    <tr
                      key={name}
                      // f.question comes from the backend — the same string the follow-up chips
                      // use, so asking from here dedups the chip correctly.
                      onClick={() => send(f.question)}
                      title={`${f.reason}\n\nClick to ask the assistant about ${name}.`}
                      className="hover:bg-teal-50 cursor-pointer transition-colors"
                    >
                      <td className="px-3 py-1.5 font-medium text-gray-700">{name}</td>
                      <td className="px-3 py-1.5 text-right text-gray-600">{fmt(f.Tm)}</td>
                      <td className="px-3 py-1.5 text-right text-gray-600">{fmt(f.num_peaks)}</td>
                      <td className="px-3 py-1.5 text-right text-gray-600">{fmt(f.peak_height)}</td>
                      <td className="px-3 py-1.5 text-right text-gray-600">{fmt(f.fwhm)}</td>
                      <td className="px-3 py-1.5 text-right text-gray-600">{fmt(f.delta_Tm_vs_pos)}</td>
                      <td className="px-3 py-1.5">
                        <span className={`inline-block px-1.5 py-0.5 rounded border text-[10px] font-semibold ${style.cls}`}>
                          {style.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

function fmt(v) {
  return v === null || v === undefined ? '—' : v;
}
