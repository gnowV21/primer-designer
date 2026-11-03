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
    // The LNA NN model covers DNA only; guard here so a bad input shows a clear
    // message instead of a raw 400 from /api/lna-suggest (which rejects non-DNA
    // bases and sequences > 60 nt).
    const seq = (sequence ?? '').toUpperCase();
    if (!/^[ATGC]{2,60}$/.test(seq)) {
      setResult(null);
      setError('LNA suggestion needs a DNA sequence of 2–60 nt (A/T/G/C only).');
      return;
    }
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
        // primer3 frame (same as the design Tm) when available; the LNA engine's own
        // absolute Tm reads ~3 °C low, only its ΔTm is used (audit SCI-12).
        tm_dna:               calc.tm_dna_primer3_frame ?? calc.tm_dna,
        tm_lna:               calc.tm_lna_primer3_frame ?? calc.tm_lna,
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
                : 'text-slate-700'
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
          <button onClick={onClose} className="text-slate-500 hover:text-slate-600 text-lg leading-none">&times;</button>
        )}
      </div>

      {/* Primer sequence preview */}
      <div className="bg-white border border-amber-100 rounded p-2 text-xs text-slate-500">
        <span className="font-medium text-slate-700">Primer ({role}):&nbsp;</span>
        <span className="font-mono">{sequence}</span>
      </div>

      {mode === 'tm' && (
        <div className="text-xs text-slate-600">
          Target Tm: <strong>{targetTm}°C</strong> — will suggest minimal LNA positions to reach target.
        </div>
      )}
      {mode === 'discrimination' && siblingMismatchPositions.length > 0 && (
        <div className="text-xs text-slate-600">
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
            <span className="bg-slate-100 rounded px-2 py-1 text-xs font-mono">
              DNA: <strong>{result.tm_dna?.toFixed(1)}°C</strong>
            </span>
            <span className="text-slate-500">→</span>
            <span className="bg-amber-100 rounded px-2 py-1 text-xs font-mono">
              +LNA: <strong>{result.tm_lna?.toFixed(1)}°C</strong>
            </span>
            <span className={`text-xs font-semibold ${result.delta_tm >= 0 ? 'text-teal-700' : 'text-red-700'}`}>
              Δ {result.delta_tm >= 0 ? '+' : ''}{result.delta_tm?.toFixed(1)}°C
            </span>
            {result.target_met && (
              <span className="text-xs text-teal-700 font-medium">Target met</span>
            )}
          </div>

          {/* Sequence with LNA highlighted */}
          <div className="bg-white border border-slate-100 rounded p-2">
            <div className="text-xs text-slate-500 mb-1">LNA positions highlighted:</div>
            {renderSequence(sequence, result.suggested_positions ?? [])}
            <div className="mt-1 text-xs text-slate-500">
              Positions: [{(result.suggested_positions ?? []).join(', ')}] (0-based) &nbsp;·&nbsp;
              Search: {result.search ?? '–'}
            </div>
          </div>

          {/* Discrimination gain */}
          {result.discrimination_gain != null && (
            <div className="bg-slate-50 border border-slate-100 rounded p-2 text-xs text-slate-800">
              Discrimination gain (directional): <strong>{result.discrimination_gain?.toFixed(1)}°C</strong>
              <span className="ml-1 text-slate-600">(LNA at mismatch positions vs sibling)</span>
            </div>
          )}

          {/* method metadata */}
          <div className="text-xs text-slate-500">
            Tm = primer3 DNA Tm + ΔTm from {(result.method ?? []).join(' + ')}
          </div>

          {/* Warnings */}
          {result.warnings?.length > 0 && (
            <div className="space-y-1">
              {result.warnings.map((w, i) => (
                <div key={i} className="bg-amber-50 border border-amber-200 rounded px-2 py-1 text-xs text-amber-800">
                  {w}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Disclaimer */}
      <div className="text-xs text-slate-500 border-t border-amber-100 pt-2 leading-relaxed">
        {DISCLAIMER}
      </div>
    </div>
  );
}
