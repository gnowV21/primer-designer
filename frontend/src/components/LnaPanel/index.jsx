/**
 * LnaPanel — LNA Tm calculator panel (Phase 8 PART B)
 *
 * Informational only — NOT used in scoring.
 * Triggered on-demand via "Suggest LNA (Tm)" or "Suggest LNA for discrimination" buttons.
 */

import { useState } from 'react';
import axios from 'axios';

const DISCLAIMER = 'Informational only — confirm Tm with synthesis provider. Not used in scoring.';

/**
 * @param {{
 *   sequence: string,          — primer sequence (DNA 5'→3')
 *   role: "forward"|"reverse", — primer role
 *   params: object,            — ion conditions
 *   mode?: "tm"|"discrimination",
 *   targetTm?: number,
 *   siblingMismatchPositions?: number[],
 *   onClose: () => void,
 * }} props
 */
export default function LnaPanel({
  sequence,
  role = 'forward',
  params = {},
  mode = 'tm',
  targetTm = 60.0,
  siblingMismatchPositions = [],
  onClose,
}) {
  const [loading, setLoading]   = useState(false);
  const [result,  setResult]    = useState(null);
  const [error,   setError]     = useState(null);

  async function handleSuggest() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body = {
        sequence,
        role,
        mode,
        target_tm: targetTm,
        sibling_mismatch_positions: siblingMismatchPositions,
        params,
      };
      const res = await axios.post('/api/lna-suggest', body);
      // Backend returns a nested shape; flatten it to what this panel renders.
      const d    = res.data ?? {};
      const lna  = d.lna_result ?? {};
      const calc = d.calc_at_suggestion ?? {};
      setResult({
        tm_dna:               calc.tm_dna,
        tm_lna:               calc.tm_lna,
        delta_tm:             calc.delta_tm,
        suggested_positions:  lna.suggested_positions ?? calc.lna_positions ?? [],
        search:               lna.search,
        target_met:           lna.target_met,
        discrimination_gain:  lna.discrimination_gain,
        method:               calc.method ?? [],
        tm_reference_primer3: d.tm_reference_primer3,
        warnings: [
          ...(lna.warnings  ?? []),
          ...(calc.warnings ?? []),
          ...(d.warnings    ?? []),
        ],
      });
    } catch (err) {
      setError(err.response?.data?.error ?? err.message ?? 'Request failed');
    } finally {
      setLoading(false);
    }
  }

  function renderSequence(seq, lnaPositions) {
    return (
      <span className="font-mono text-sm tracking-widest">
        {seq.split('').map((base, i) => (
          <span
            key={i}
            className={
              lnaPositions.includes(i)
                ? 'inline-block bg-amber-200 text-amber-900 font-bold rounded px-px mx-px'
                : 'text-gray-700'
            }
            title={lnaPositions.includes(i) ? `Position ${i}: LNA` : `Position ${i}: DNA`}
          >
            {base}
          </span>
        ))}
      </span>
    );
  }

  return (
    <div className="border border-amber-200 rounded-xl bg-amber-50 p-4 space-y-3 text-sm">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <span className="font-semibold text-amber-800">LNA Tm Calculator</span>
          <span className="ml-2 text-xs text-amber-600 uppercase tracking-wide">
            {mode === 'discrimination' ? 'discrimination mode' : 'Tm mode'}
          </span>
        </div>
        {onClose && (
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">&times;</button>
        )}
      </div>

      {/* Primer sequence preview */}
      <div className="bg-white border border-amber-100 rounded p-2 text-xs text-gray-500">
        <span className="font-medium text-gray-700">Primer ({role}):&nbsp;</span>
        <span className="font-mono">{sequence}</span>
      </div>

      {mode === 'tm' && (
        <div className="text-xs text-gray-600">
          Target Tm: <strong>{targetTm}°C</strong> — will suggest minimal LNA positions to reach target.
        </div>
      )}
      {mode === 'discrimination' && siblingMismatchPositions.length > 0 && (
        <div className="text-xs text-gray-600">
          Mismatch positions vs HIGH-risk sibling: <strong>[{siblingMismatchPositions.join(', ')}]</strong> — LNA prioritised here.
        </div>
      )}

      {/* Suggest button */}
      <button
        onClick={handleSuggest}
        disabled={loading}
        className="w-full py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium disabled:opacity-50 transition-colors"
      >
        {loading ? 'Calculating…' : 'Suggest LNA positions'}
      </button>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-2 text-xs text-red-700">{error}</div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-3">
          {/* Tm before/after */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="bg-gray-100 rounded px-2 py-1 text-xs font-mono">
              DNA: <strong>{result.tm_dna?.toFixed(1)}°C</strong>
            </span>
            <span className="text-gray-400">→</span>
            <span className="bg-amber-100 rounded px-2 py-1 text-xs font-mono">
              +LNA: <strong>{result.tm_lna?.toFixed(1)}°C</strong>
            </span>
            <span className={`text-xs font-semibold ${result.delta_tm >= 0 ? 'text-green-700' : 'text-red-700'}`}>
              Δ {result.delta_tm >= 0 ? '+' : ''}{result.delta_tm?.toFixed(1)}°C
            </span>
            {result.target_met && (
              <span className="text-xs text-green-700 font-medium">Target met</span>
            )}
          </div>

          {/* Sequence with LNA highlighted */}
          <div className="bg-white border border-gray-100 rounded p-2">
            <div className="text-xs text-gray-500 mb-1">LNA positions highlighted:</div>
            {renderSequence(sequence, result.suggested_positions ?? [])}
            <div className="mt-1 text-xs text-gray-500">
              Positions: [{(result.suggested_positions ?? []).join(', ')}] (0-based) &nbsp;·&nbsp;
              Search: {result.search ?? '–'}
            </div>
          </div>

          {/* Discrimination gain */}
          {result.discrimination_gain != null && (
            <div className="bg-blue-50 border border-blue-100 rounded p-2 text-xs text-blue-800">
              Discrimination gain (directional): <strong>{result.discrimination_gain?.toFixed(1)}°C</strong>
              <span className="ml-1 text-blue-600">(LNA at mismatch positions vs sibling)</span>
            </div>
          )}

          {/* method metadata */}
          <div className="text-xs text-gray-400">
            Params: {(result.method ?? []).join(' + ')} &nbsp;|&nbsp;
            Ref (primer3): {result.tm_reference_primer3?.toFixed(1)}°C
          </div>

          {/* Warnings */}
          {result.warnings?.length > 0 && (
            <div className="space-y-1">
              {result.warnings.map((w, i) => (
                <div key={i} className="bg-yellow-50 border border-yellow-200 rounded px-2 py-1 text-xs text-yellow-800">
                  {w}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Disclaimer */}
      <div className="text-[10px] text-gray-400 border-t border-amber-100 pt-2 leading-relaxed">
        {DISCLAIMER}
      </div>
    </div>
  );
}
