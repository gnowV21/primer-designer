// MultiplexPanel — user adds assay sets, triggers /api/multiplex-check,
// displays NxN risk heatmap + HIGH pair list + recommendations (Phase 6 §B.4).
// Checks multiplex RT/preamp panel — NOT qPCR duplexing.

import { useState } from 'react';
import axios from 'axios';

const RISK_COLOR = {
  HIGH:   'bg-red-500 text-white',
  MEDIUM: 'bg-amber-400 text-white',
  LOW:    'bg-yellow-200 text-slate-700',
  SAFE:   'bg-teal-100 text-teal-800',
};

const RISK_BORDER = {
  HIGH:   'border-red-200 bg-red-50 text-red-800',
  MEDIUM: 'border-amber-400 bg-amber-50 text-amber-800',
  LOW:    'border-yellow-300 bg-yellow-50 text-yellow-800',
  SAFE:   'border-teal-300 bg-teal-50 text-teal-700',
};

function RiskCell({ risk }) {
  return (
    <div
      className={`w-8 h-8 flex items-center justify-center text-xs font-bold rounded ${
        RISK_COLOR[risk] ?? 'bg-slate-100 text-slate-400'
      }`}
      title={risk ?? '—'}
    >
      {risk === 'SAFE' ? '✓' : (risk ?? '—').charAt(0)}
    </div>
  );
}

export default function MultiplexPanel() {
  const [assays, setAssays] = useState([{ mirna_id: '', forward: '', probe: '' }]);
  const [state, setState]   = useState('idle'); // idle | loading | done | error
  const [result, setResult] = useState(null);
  const [errMsg, setErrMsg] = useState('');

  function addAssay() {
    setAssays((prev) => [...prev, { mirna_id: '', forward: '', probe: '' }]);
  }

  function removeAssay(i) {
    setAssays((prev) => prev.filter((_, idx) => idx !== i));
  }

  function updateAssay(i, field, value) {
    setAssays((prev) =>
      prev.map((a, idx) => (idx === i ? { ...a, [field]: value } : a))
    );
  }

  async function runCheck() {
    const validSets = assays.filter((a) => a.forward.trim());
    if (validSets.length < 2) {
      setErrMsg('Add at least 2 assays with forward primer sequences.');
      return;
    }
    setState('loading');
    setErrMsg('');
    setResult(null);

    try {
      const payload = {
        primer_sets: validSets.map((a) => ({
          mirna_id: a.mirna_id.trim() || `assay_${assays.indexOf(a) + 1}`,
          forward:  a.forward.trim(),
          probe:    a.probe.trim() || null,
        })),
        params: {},
      };
      const resp = await axios.post('/api/multiplex-check', payload, { timeout: 30000 });
      setResult(resp.data);
      setState('done');
    } catch (err) {
      const status = err.response?.status;
      if (status === 429) {
        setErrMsg('Rate limit reached. Wait a minute before retrying.');
      } else if (status === 400) {
        setErrMsg(err.response?.data?.error ?? 'Invalid input.');
      } else if (err.code === 'ECONNABORTED') {
        setErrMsg('Request timed out.');
      } else {
        setErrMsg(err.response?.data?.error ?? 'Multiplex check failed.');
      }
      setState('error');
    }
  }

  // ── Build unique assay labels for heatmap axes ─────────────────────────
  const assayLabels = result
    ? [...new Set(result.pairs.flatMap((p) => [p.assay_a, p.assay_b]))]
    : [];

  // Build a lookup: "a||b" → risk
  const riskMap = {};
  if (result) {
    for (const p of result.pairs) {
      riskMap[`${p.assay_a}||${p.assay_b}`] = p.risk;
      riskMap[`${p.assay_b}||${p.assay_a}`] = p.risk;
    }
  }

  const highPairs = result ? result.pairs.filter((p) => p.risk === 'HIGH') : [];

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <p className="text-sm font-semibold text-slate-700">
          Multiplex Panel Check
          <span className="ml-2 text-xs font-normal text-slate-400">
            RT/preamp — not qPCR duplexing
          </span>
        </p>
        <span className="text-xs text-slate-400 bg-slate-50 border border-slate-200 rounded-full px-2 py-0.5">
          Max 20 assays/tube [Bell17]
        </span>
      </div>

      {/* Assay inputs */}
      <div className="space-y-2">
        {assays.map((a, i) => (
          <div key={i} className="grid grid-cols-[1fr_2fr_2fr_auto] gap-2 items-start">
            <input
              className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs placeholder-slate-300 focus:outline-none focus:ring-1 focus:ring-teal-400"
              placeholder={`ID (e.g. miR-21)`}
              value={a.mirna_id}
              onChange={(e) => updateAssay(i, 'mirna_id', e.target.value)}
            />
            <input
              className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-mono placeholder-slate-300 focus:outline-none focus:ring-1 focus:ring-teal-400"
              placeholder="Forward primer sequence"
              value={a.forward}
              onChange={(e) => updateAssay(i, 'forward', e.target.value)}
            />
            <input
              className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-mono placeholder-slate-300 focus:outline-none focus:ring-1 focus:ring-teal-400"
              placeholder="Probe sequence (optional)"
              value={a.probe}
              onChange={(e) => updateAssay(i, 'probe', e.target.value)}
            />
            <button
              onClick={() => removeAssay(i)}
              disabled={assays.length <= 1}
              className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs text-slate-400 hover:text-red-500 hover:border-red-200 disabled:opacity-30"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      {/* Controls */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={addAssay}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:border-teal-400 hover:text-teal-700 transition"
        >
          + Add assay
        </button>
        <button
          onClick={runCheck}
          disabled={state === 'loading'}
          className="rounded-lg bg-teal-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-teal-700 disabled:opacity-50 transition"
        >
          {state === 'loading' ? '⟳ Checking…' : 'Check panel'}
        </button>
      </div>

      {/* Error */}
      {errMsg && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
          ⚠ {errMsg}
        </div>
      )}

      {/* Results */}
      {state === 'done' && result && (
        <div className="space-y-3 border-t border-slate-100 pt-3">
          {/* Panel status banner */}
          <div className={`rounded-lg border px-3 py-2 text-sm font-semibold ${RISK_BORDER[result.worst_risk] ?? RISK_BORDER.SAFE}`}>
            {result.panel_ok
              ? '✓ Panel OK — no blocking cross-dimers detected.'
              : `Panel issue — worst risk: ${result.worst_risk}`}
          </div>

          {/* Heatmap */}
          {assayLabels.length > 0 && (
            <div className="overflow-x-auto">
              <p className="text-xs font-medium text-slate-500 mb-1">Cross-dimer risk matrix</p>
              <table className="text-xs border-separate" style={{ borderSpacing: 2 }}>
                <thead>
                  <tr>
                    <th />
                    {assayLabels.map((lbl) => (
                      <th key={lbl} className="text-slate-400 font-normal px-1 pb-1 text-center max-w-[60px] truncate">
                        {lbl.length > 8 ? lbl.slice(0, 7) + '…' : lbl}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {assayLabels.map((rowLbl) => (
                    <tr key={rowLbl}>
                      <td className="text-slate-400 font-normal pr-2 text-right max-w-[60px] truncate">
                        {rowLbl.length > 8 ? rowLbl.slice(0, 7) + '…' : rowLbl}
                      </td>
                      {assayLabels.map((colLbl) => {
                        if (rowLbl === colLbl) {
                          return (
                            <td key={colLbl}>
                              <div className="w-8 h-8 flex items-center justify-center text-slate-200">—</div>
                            </td>
                          );
                        }
                        const risk = riskMap[`${rowLbl}||${colLbl}`] ?? 'SAFE';
                        return (
                          <td key={colLbl}>
                            <RiskCell risk={risk} />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-1 text-xs text-slate-400">
                H = HIGH · M = MEDIUM · L = LOW · ✓ = SAFE
              </p>
            </div>
          )}

          {/* HIGH pairs list */}
          {highPairs.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-red-700">HIGH-risk pairs</p>
              {highPairs.map((p, i) => (
                <div key={i} className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs text-red-800">
                  <span className="font-semibold">{p.assay_a}</span> × <span className="font-semibold">{p.assay_b}</span>
                  {' '}— {p.primer_type_a} × {p.primer_type_b}
                  {p.dg != null && <span className="ml-2 font-mono">ΔG {p.dg.toFixed(1)} kcal/mol</span>}
                </div>
              ))}
            </div>
          )}

          {/* Recommendations */}
          {result.recommendations?.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-slate-600">Recommendations</p>
              {result.recommendations.map((r, i) => (
                <div key={i} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-600">
                  • {r}
                </div>
              ))}
            </div>
          )}

          {/* Warnings */}
          {result.warnings?.length > 0 && (
            <div className="space-y-1">
              {result.warnings.map((w, i) => (
                <div key={i} className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-700">
                  ⚑ {w}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
