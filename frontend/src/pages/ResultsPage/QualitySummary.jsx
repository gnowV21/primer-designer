// QualitySummary — unified quality warnings panel (Phase 4 §6).
// Gathers: global_warnings, per-set structure flags, edge_cases (info level), off-target async.

import { useState } from 'react';
import axios from 'axios';

const SEV_STYLE = {
  critical: 'bg-red-50 border-red-200 text-red-800',
  warning:  'bg-amber-50 border-amber-200 text-amber-800',
  info:     'bg-teal-50 border-teal-200 text-teal-800',
};

const SEV_ICON = { critical: '⚠', warning: '⚑', info: 'ℹ' };

export default function QualitySummary({ results }) {
  const {
    global_warnings = [],
    edge_cases      = [],
    top3            = [],
    metadata        = {},
  } = results;

  const [blastState, setBlastState] = useState('idle'); // idle | running | done | error
  const [blastError, setBlastError] = useState(null);
  const [blastResult, setBlastResult] = useState(null);

  // ── Collect items ──────────────────────────────────────────────
  const items = [];

  // 1. global_warnings
  for (const w of global_warnings) {
    items.push({ severity: w.severity ?? 'warning', message: w.message, source: 'system' });
  }

  // 2. edge_cases — info level only (critical/warning shown by EdgeCaseBanner)
  for (const e of edge_cases) {
    if (e.severity === 'info') {
      items.push({ severity: 'info', message: `[${e.code}] ${e.message}`, source: 'edge' });
    }
  }

  // 3. Per-set structure flags — show rank badges for sets with issues
  for (const set of top3) {
    const sc = set.structure_checks ?? {};
    if (sc.has_critical_flag) {
      items.push({
        severity: 'critical',
        message: `Rank ${set.rank} forward primer: critical secondary structure flag (hairpin or self-dimer ΔG too negative).`,
        source: 'structure',
      });
    } else if (!sc.overall_pass) {
      items.push({
        severity: 'warning',
        message: `Rank ${set.rank} forward primer: secondary structure check did not fully pass.`,
        source: 'structure',
      });
    }
  }

  // 4. Off-target BLAST result (when done)
  if (blastState === 'done' && blastResult) {
    const risk = blastResult.risk_level;
    if (risk === 'HIGH' || risk === 'CRITICAL') {
      items.push({
        severity: risk === 'CRITICAL' ? 'critical' : 'warning',
        message: `Off-target BLAST: ${risk} — ${blastResult.summary ?? 'significant off-target hits detected.'}`,
        source: 'blast',
      });
    } else if (risk === 'LOW' || risk === 'SAFE') {
      items.push({
        severity: 'info',
        message: `Off-target BLAST: ${risk} — no significant off-target hits.`,
        source: 'blast',
      });
    }
  }

  const critCount = items.filter((i) => i.severity === 'critical').length;
  const warnCount = items.filter((i) => i.severity === 'warning').length;

  // ── Run BLAST check ────────────────────────────────────────────
  async function runBlast() {
    const mirnaId = metadata?.mirna_id;
    if (!mirnaId) return;
    const fwd = top3[0]?.sequence;
    if (!fwd) return;

    setBlastState('running');
    setBlastError(null);
    try {
      const resp = await axios.post('/api/blast-check', {
        mirna_id: mirnaId,
        forward_primer: fwd,
      }, { timeout: 30000 });
      setBlastResult(resp.data);
      setBlastState('done');
    } catch (err) {
      const status = err.response?.status;
      if (status === 429) {
        setBlastError('Rate limit reached. Please wait a minute before retrying.');
      } else if (status === 503) {
        setBlastError('BLAST database not available on this server.');
      } else if (err.code === 'ECONNABORTED') {
        setBlastError('BLAST check timed out.');
      } else {
        setBlastError(err.response?.data?.error ?? 'BLAST check failed.');
      }
      setBlastState('error');
    }
  }

  // ── Render ─────────────────────────────────────────────────────
  const allClear = items.length === 0 && blastState === 'idle';

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-slate-700">
          Quality Summary
          {!allClear && (
            <span className="ml-2 font-normal text-slate-500">
              — {items.length} issue{items.length !== 1 ? 's' : ''}
              {critCount > 0 && <span className="ml-1 text-red-600">({critCount} critical)</span>}
              {warnCount > 0 && <span className="ml-1 text-amber-600">({warnCount} warning{warnCount > 1 ? 's' : ''})</span>}
            </span>
          )}
        </p>
      </div>

      {/* All-clear */}
      {allClear && blastState === 'idle' && (
        <div className="text-sm text-teal-700 bg-teal-50 border border-teal-200 rounded-lg px-3 py-2">
          ✓ All automated checks passed.
        </div>
      )}

      {/* Issues */}
      {items.length > 0 && (
        <div className="space-y-1.5">
          {items.map((item, i) => (
            <div
              key={i}
              className={`rounded-lg border px-3 py-2 text-sm ${SEV_STYLE[item.severity] ?? SEV_STYLE.info}`}
            >
              <span className="mr-1.5">{SEV_ICON[item.severity]}</span>
              {item.message}
            </div>
          ))}
        </div>
      )}

      {/* [RESEARCH_QUESTIONS_UX C1] predicted design quality — not efficiency */}
      {metadata?.output_note && (
        <p className="text-[11px] text-slate-400 italic border-t border-slate-100 pt-2">
          {metadata.output_note}
        </p>
      )}

      {/* Off-target async section */}
      <div className="border-t border-slate-100 pt-3">
        {blastState === 'idle' && (
          <div className="flex items-center justify-between text-xs text-teal-700 bg-teal-50 border border-teal-200 rounded-lg px-3 py-2">
            <span>ℹ Off-target (BLAST) not run yet.</span>
            <button
              onClick={runBlast}
              className="ml-3 font-semibold underline underline-offset-2 hover:text-teal-900 transition"
            >
              Run check
            </button>
          </div>
        )}
        {blastState === 'running' && (
          <div className="flex items-center gap-2 text-xs text-slate-500 px-1">
            <span className="animate-spin">⟳</span> Running BLAST…
          </div>
        )}
        {blastState === 'error' && (
          <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            ⚑ {blastError}
            <button
              onClick={runBlast}
              className="ml-2 underline underline-offset-2 hover:text-amber-900"
            >
              Retry
            </button>
          </div>
        )}
        {blastState === 'done' && (
          <p className="text-xs text-slate-400">Off-target BLAST check complete — result shown above.</p>
        )}
      </div>
    </div>
  );
}
