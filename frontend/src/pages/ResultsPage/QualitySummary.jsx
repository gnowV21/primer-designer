// QualitySummary — unified quality warnings panel (Phase 4 §6).
// Gathers: global_warnings, per-set structure flags, edge_cases (info level), off-target async.

import { useState } from 'react';
import axios from 'axios';
import CollapsibleCard from '../../components/ui/CollapsibleCard.jsx';

const SEV_STYLE = {
  critical: 'bg-red-50 border-red-200 text-red-800',
  warning:  'bg-amber-50 border-amber-200 text-amber-800',
  info:     'bg-teal-50 border-teal-200 text-teal-800',
};

// Warnings that already have a dedicated, in-context display are not repeated
// in this summary — re-stating a deliberate user choice is noise:
//   signalMethod (SYBR)       → shown as its own note below the primer sets
//   bindingRegion3prime       → shown on the design page at the point of choice
//                               (still recorded in the exported report)
const DEDICATED_WARNING_FIELDS = new Set(['signalMethod', 'bindingRegion3prime']);

export default function QualitySummary({ results, onBlastResult }) {
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

  // 1. global_warnings (skip the ones with a dedicated in-context display)
  for (const w of global_warnings) {
    if (DEDICATED_WARNING_FIELDS.has(w.field)) continue;
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

  // 4. Off-target BLAST result — only a real HIGH/CRITICAL hit counts as an issue.
  // A SAFE/LOW result is not a problem, so it is shown inline in the off-target
  // section below instead of inflating the issue list.
  // /api/blast-check returns { summary: { overall_risk, ...counts }, ... } — there
  // is no top-level `risk_level`. Reading the wrong key made the panel render an
  // empty risk and never raise an issue, which looked like "BLAST didn't run".
  // OffTargetPanel.jsx reads the same `summary.overall_risk`.
  if (blastState === 'done' && blastResult) {
    const s = blastResult.summary ?? {};
    const risk = s.overall_risk;
    if (risk === 'HIGH' || risk === 'CRITICAL') {
      const counts = [
        s.critical_count ? `${s.critical_count} critical` : null,
        s.high_risk_count ? `${s.high_risk_count} high-risk` : null,
      ].filter(Boolean).join(', ');
      items.push({
        severity: risk === 'CRITICAL' ? 'critical' : 'warning',
        message: `Off-target BLAST: ${risk}`
          + (counts ? ` — ${counts} hit(s) across ${s.total_hits ?? '?'} total.` : ' — significant off-target hits detected.')
          + ' See the off-target panel in the primer-set cards.',
        source: 'blast',
      });
    }
  }

  const critCount = items.filter((i) => i.severity === 'critical').length;
  const warnCount = items.filter((i) => i.severity === 'warning').length;

  // ── Off-target BLAST preconditions ─────────────────────────────
  // The backend needs a forward primer, and a miRNA id WITH arm designation so it
  // can exclude the on-target (without it the target itself is reported as a hit,
  // i.e. a false CRITICAL). Previously these were silent `return`s, so the button
  // simply did nothing for miRNAs that were pasted as a raw sequence — the check
  // appeared to work "sometimes". Now the reason is always stated.
  const mirnaId = (metadata?.mirna_id || '').trim();
  const fwd = top3[0]?.sequence;
  const hasArm = mirnaId.endsWith('-5p') || mirnaId.endsWith('-3p');

  let blastBlockedReason = null;
  if (!fwd) {
    blastBlockedReason = 'No forward primer in this result — nothing to check.';
  } else if (!mirnaId) {
    blastBlockedReason =
      'miRNA name unknown (the sequence was not matched to miRBase). Without it the '
      + 'on-target cannot be excluded and would be reported as an off-target hit. '
      + 'Re-run the design using a miRNA name or miRBase accession.';
  } else if (!hasArm) {
    blastBlockedReason =
      `"${mirnaId}" has no arm designation (-5p / -3p). The check needs it to exclude `
      + 'the on-target, otherwise the target itself is counted as a hit.';
  }

  // ── Run BLAST check ────────────────────────────────────────────
  async function runBlast() {
    if (blastBlockedReason) {          // defensive — the button is disabled too
      setBlastError(blastBlockedReason);
      setBlastState('error');
      return;
    }

    setBlastState('running');
    setBlastError(null);
    try {
      const resp = await axios.post('/api/blast-check', {
        mirna_id: mirnaId,
        forward_primer: fwd,
        // On-target sequence + the design's salt conditions for the duplex-Tm gate,
        // so off-target and on-target Tm are computed exactly like the design's own.
        mirna_sequence: metadata?.mirna_sequence || undefined,
        conditions: metadata?.design_settings?.effective_p3 || undefined,
      }, { timeout: 65000 });   // backend allows the search itself up to 60 s
      setBlastResult(resp.data);
      setBlastState('done');
      onBlastResult?.(resp.data);  // lift to ResultsPage so ExportBar can embed it
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
  // Only real problems (critical/warning) surface the summary; a clean design
  // shows nothing but the (optional) off-target runner that feeds the report.
  const hasProblems = critCount > 0 || warnCount > 0;
  const blastRisk = blastState === 'done'
    ? (blastResult?.summary?.overall_risk ?? 'UNKNOWN')
    : null;
  const blastSafe = blastRisk === 'SAFE' || blastRisk === 'LOW';

  // Header summary stays visible while collapsed, so a critical issue is never
  // hidden behind a closed panel — only its detail is.
  const headerTone = critCount > 0 ? 'danger' : warnCount > 0 ? 'warn' : 'ok';
  const headerSummary = hasProblems
    ? `${items.length} issue${items.length !== 1 ? 's' : ''}`
      + (critCount > 0 ? ` · ${critCount} critical` : '')
      + (warnCount > 0 ? ` · ${warnCount} warning${warnCount > 1 ? 's' : ''}` : '')
    : blastRisk
      ? `No issues · BLAST ${blastRisk}`
      : 'No issues detected';

  return (
    <CollapsibleCard title="Quality Summary" tone={headerTone} summary={headerSummary}>
    <div className="space-y-3">
      {/* Issues — shown only when there is a real problem to report */}
      {hasProblems && (
        <>
          <p className="text-sm font-semibold text-slate-700">
            Quality Summary
            <span className="ml-2 font-normal text-slate-500">
              — {items.length} issue{items.length !== 1 ? 's' : ''}
              {critCount > 0 && <span className="ml-1 text-red-600">({critCount} critical)</span>}
              {warnCount > 0 && <span className="ml-1 text-amber-600">({warnCount} warning{warnCount > 1 ? 's' : ''})</span>}
            </span>
          </p>

          <div className="space-y-1.5">
            {items.map((item, i) => (
              <div
                key={i}
                className={`rounded-lg border px-3 py-2 text-sm ${SEV_STYLE[item.severity] ?? SEV_STYLE.info}`}
              >
                {item.message}
              </div>
            ))}
          </div>

          {/* [RESEARCH_QUESTIONS_UX C1] predicted design quality — not efficiency */}
          {metadata?.output_note && (
            <p className="text-xs text-slate-500 italic border-t border-slate-100 pt-2">
              {metadata.output_note}
            </p>
          )}
        </>
      )}

      {/* Off-target BLAST — always available; the result is embedded in the report */}
      <div className={hasProblems ? 'border-t border-slate-100 pt-3' : ''}>
        {blastState === 'idle' && !blastBlockedReason && (
          <div className="flex items-center justify-between text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
            <span>Off-target (BLAST) — run to include in the exported report.</span>
            <button
              onClick={runBlast}
              className="ml-3 font-semibold text-teal-700 underline underline-offset-2 hover:text-teal-900 transition"
            >
              Run check
            </button>
          </div>
        )}
        {blastState === 'idle' && blastBlockedReason && (
          <div className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 leading-relaxed">
            <span className="font-semibold text-slate-600">
              Off-target (BLAST) unavailable for this design.
            </span>{' '}
            {blastBlockedReason}
          </div>
        )}
        {blastState === 'running' && (
          <div className="flex items-center gap-2 text-xs text-slate-500 px-1">
            <span className="animate-spin">⟳</span> Running BLAST…
          </div>
        )}
        {blastState === 'error' && (
          <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            {blastError}
            <button
              onClick={runBlast}
              className="ml-2 underline underline-offset-2 hover:text-amber-900"
            >
              Retry
            </button>
          </div>
        )}
        {blastState === 'done' && (() => {
          const s = blastResult?.summary ?? {};
          const parts = [
            s.critical_count ? `${s.critical_count} critical` : null,
            s.high_risk_count ? `${s.high_risk_count} high` : null,
            s.medium_risk_count ? `${s.medium_risk_count} medium` : null,
          ].filter(Boolean).join(' · ');
          return (
            <p className={`text-xs ${blastSafe ? 'text-teal-700' : 'text-amber-700'}`}>
              Off-target BLAST: <span className="font-semibold">{blastRisk}</span>
              {s.total_hits != null && (
                <span className="text-slate-500">
                  {' '}— {s.total_hits} hit{s.total_hits !== 1 ? 's' : ''} screened
                  {parts && ` (${parts})`}
                  {s.cross_species_excluded ? `, ${s.cross_species_excluded} cross-species excluded` : ''}
                </span>
              )}
              <span className="text-slate-500">
                {blastSafe
                  ? '. No significant off-target hits. Included in the report.'
                  : '. See the off-target panel in the primer-set cards.'}
              </span>
            </p>
          );
        })()}
      </div>
    </div>
    </CollapsibleCard>
  );
}
