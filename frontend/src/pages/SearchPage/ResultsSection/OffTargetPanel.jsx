// OffTargetPanel — per-card BLAST off-target check (§13, Phase 3)

import { useState, useEffect } from 'react';
import useBlastCheck from '../../../hooks/useBlastCheck.js';

const BLAST_RISK_STYLE = {
  CRITICAL: 'text-red-700 bg-red-50 border-red-300',
  HIGH:     'text-orange-700 bg-orange-50 border-orange-300',
  MEDIUM:   'text-amber-700 bg-amber-50 border-amber-200',
  SAFE:     'text-teal-700 bg-teal-50 border-teal-200',
};

export default function OffTargetPanel({ forwardPrimer, reversePrimer, mirnaId, mirnaSequence, conditions }) {
  const { status, result, error, run, reset, dbAvailable, dbMessage } = useBlastCheck();

  function handleRun() {
    run(forwardPrimer, reversePrimer, mirnaId, { mirnaSequence, conditions });
  }

  // DB unavailable (Phase 7 PART A) — show disabled state with explanation
  const dbNotReady = dbAvailable === false;

  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      <div className="px-3 py-2 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          Off-target Check (BLAST)
        </p>
        {status === 'done' && (
          <button
            type="button"
            onClick={handleRun}
            className="text-xs text-slate-500 hover:text-slate-600 underline"
          >
            Re-check
          </button>
        )}
      </div>

      <div className="px-3 py-3 space-y-3">
        {/* ── DB not ready (Phase 7 PART A) ── */}
        {dbNotReady && status === 'idle' && (
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-slate-500">
              {dbMessage || 'Off-target database is being prepared. Please try again shortly.'}
            </p>
            <button
              type="button"
              disabled
              title="Off-target database is being prepared. Please try again shortly."
              className="shrink-0 flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border
                bg-slate-100 border-slate-200 text-slate-500 cursor-not-allowed"
            >
              Check off-target
            </button>
          </div>
        )}

        {/* ── idle (DB ready or unknown) ── */}
        {!dbNotReady && status === 'idle' && (
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-slate-500">
              Checks primer against miRBase (all species) for miRNA family cross-reactivity using Primer-BLAST rules (Ye 2012).
            </p>
            <BlastCheckButton status={status} onClick={handleRun} />
          </div>
        )}

        {/* ── loading ── */}
        {status === 'loading' && (
          <div className="flex items-center gap-3">
            <BlastCheckButton status={status} onClick={() => {}} />
            <p className="text-xs text-slate-500">Running BLAST… (up to 70 s)</p>
          </div>
        )}

        {/* ── error ── */}
        {status === 'error' && error && (
          <ErrorDisplay error={error} onRetry={handleRun} onReset={reset} />
        )}

        {/* ── done ── */}
        {status === 'done' && result && (
          <ResultDisplay result={result} />
        )}
      </div>
    </div>
  );
}

// ── Button ────────────────────────────────────────────────────────

function BlastCheckButton({ status, onClick }) {
  const loading = status === 'loading';
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className={`shrink-0 flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border transition-colors
        ${loading
          ? 'bg-slate-100 border-slate-200 text-slate-500 cursor-not-allowed'
          : 'bg-teal-50 border-teal-300 text-teal-700 hover:bg-teal-100'
        }`}
    >
      {loading && (
        <svg className="animate-spin w-3 h-3" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {loading ? 'Running…' : 'Check off-target'}
    </button>
  );
}

// ── Error displays ────────────────────────────────────────────────

function ErrorDisplay({ error, onRetry, onReset }) {
  if (error.type === '429') return <RateLimitError error={error} onRetry={onReset} />;
  if (error.type === '503') return <CircuitOpenError error={error} />;
  return <GenericBlastError error={error} onRetry={onRetry} />;
}

function RateLimitError({ error, onRetry }) {
  const [seconds, setSeconds] = useState(error.retryAfter ?? 60);

  useEffect(() => {
    if (seconds <= 0) { onRetry(); return; }
    const t = setTimeout(() => setSeconds((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [seconds, onRetry]);

  return (
    <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 space-y-1">
      <p className="text-xs font-semibold text-amber-700">Rate limit reached</p>
      <p className="text-xs text-amber-700">{error.message}</p>
      <p className="text-xs text-amber-500">Auto-retrying in {seconds}s…</p>
    </div>
  );
}

function CircuitOpenError({ error }) {
  return (
    <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 space-y-1">
      <p className="text-xs font-semibold text-amber-700">BLAST temporarily unavailable</p>
      <p className="text-xs text-amber-700">{error.message}</p>
      {error.retryAfter && (
        <p className="text-xs text-amber-500">Try again in ~{error.retryAfter}s.</p>
      )}
      <p className="text-xs text-slate-500 mt-1">Primer design results above are unaffected.</p>
    </div>
  );
}

function GenericBlastError({ error, onRetry }) {
  return (
    <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 flex items-start justify-between gap-3">
      <div className="space-y-0.5">
        <p className="text-xs font-semibold text-red-700">BLAST error</p>
        <p className="text-xs text-red-700">{error.message}</p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="shrink-0 text-xs font-semibold px-2 py-1 rounded border border-red-300 bg-white text-red-600 hover:bg-red-50"
      >
        Retry
      </button>
    </div>
  );
}

// ── Result display ────────────────────────────────────────────────

function ResultDisplay({ result }) {
  const summary = result.summary ?? {};
  const dbInfo  = result.database_info ?? {};
  const fwdHits = result.forward_primer_hits ?? [];
  const revHits = result.reverse_primer_hits ?? [];
  const clf     = result.classification ?? {};

  return (
    <div className="space-y-3">
      <OverallRiskRow summary={summary} />

      {summary.hits_truncated && (
        <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1">
          Showing top 200 hits per primer. {summary.total_hits.toLocaleString()} total hits found.
        </p>
      )}

      {fwdHits.length > 0 && (
        <HitsAccordion label="Forward primer hits" hits={fwdHits} />
      )}
      {revHits.length > 0 && (
        <HitsAccordion label="Reverse primer hits" hits={revHits} />
      )}
      {fwdHits.length === 0 && revHits.length === 0 && summary.overall_risk === 'SAFE' && (
        <p className="text-xs text-teal-700">No significant off-target hits detected.</p>
      )}

      {/* Footnote */}
      <div className="text-xs text-slate-500 border-t border-slate-100 pt-2 space-y-0.5">
        <p>
          {clf.tm_gate_applied
            ? `Forward primer on its target: duplex Tm ${clf.tm_ontarget?.toFixed(1)} °C. `
              + `Hits more than ${clf.safe_margin_c} °C weaker are SAFE; within `
              + `${clf.critical_margin_c} °C are CRITICAL.`
            : 'Target sequence unknown — classified by mismatch rules only (no duplex-Tm gate).'}
        </p>
        {result.reverse_primer_skipped && <p>{result.reverse_primer_skipped}</p>}
        <p>
        {result.cache?.hit ? 'Cached result · ' : ''}
        DB: miRBase {dbInfo.mirbase_version} (all species)
        {dbInfo.outdated_warning && ' · DB may be outdated'}
        {' · built '}{dbInfo.build_date}
        </p>
      </div>
    </div>
  );
}

function OverallRiskRow({ summary }) {
  const risk  = summary.overall_risk ?? 'SAFE';
  const style = BLAST_RISK_STYLE[risk] ?? BLAST_RISK_STYLE.SAFE;

  return (
    <div className="flex items-center justify-between gap-3 flex-wrap">
      <div className="flex items-center gap-2">
        <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${style}`}>
          {risk}
        </span>
        <span className="text-xs text-slate-500">off-target risk</span>
      </div>
      <div className="flex gap-2 text-xs flex-wrap">
        {summary.critical_count > 0 && (
          <span className="text-red-600 font-medium">{summary.critical_count.toLocaleString()} critical</span>
        )}
        {summary.high_risk_count > 0 && (
          <span className="text-orange-600 font-medium">{summary.high_risk_count.toLocaleString()} high</span>
        )}
        {summary.medium_risk_count > 0 && (
          <span className="text-amber-600 font-medium">{summary.medium_risk_count.toLocaleString()} medium</span>
        )}
        {summary.safe_count > 0 && (
          <span className="text-slate-500">{summary.safe_count.toLocaleString()} safe</span>
        )}
        {summary.same_family_count > 0 && (
          <span className="text-purple-600" title="Same seed-family members that share the primer's binding region. This cross-reactivity is expected for this miRNA family and is analysed separately in the Family Cross-reactivity panel — it is not counted as an out-of-family off-target here.">
            {summary.same_family_count.toLocaleString()} same-family
          </span>
        )}
        {summary.cross_species_excluded > 0 && (
          <span className="text-slate-500" title="Cross-species miRBase orthologs excluded (not relevant for this species' assay)">
            {summary.cross_species_excluded.toLocaleString()} excluded
          </span>
        )}
      </div>
    </div>
  );
}

function HitsAccordion({ label, hits }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? hits : hits.slice(0, 5);

  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold text-slate-600">{label}</p>
      <div className="rounded-lg border border-slate-200 overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-slate-100 border-b border-slate-200">
            <tr>
              <th className="text-left px-2 py-1.5 font-semibold text-slate-600">Target</th>
              <th
                className="text-center px-2 py-1.5 font-semibold text-slate-600"
                title="Duplex Tm of the primer on this off-target's cDNA, compared with the primer on its own target (same salt conditions as the design)"
              >
                Tm °C
              </th>
              <th className="text-center px-2 py-1.5 font-semibold text-slate-600">Mismatch</th>
              <th className="text-center px-2 py-1.5 font-semibold text-slate-600">3′ mm</th>
              <th className="text-center px-2 py-1.5 font-semibold text-slate-600">3′ type</th>
              <th className="text-center px-2 py-1.5 font-semibold text-slate-600">Risk</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {visible.map((h, i) => {
              const aln   = h.alignment ?? {};
              const style = BLAST_RISK_STYLE[h.risk] ?? BLAST_RISK_STYLE.SAFE;
              const termCat = aln.terminal_category ?? '—';
              // primer:template (Kwok 1990) — template is the strand the primer anneals to,
              // so a match is a Watson-Crick pair (A:T), not two equal letters.
              const termMm  = termCat !== 'MATCH' && aln.primer_3prime_base && aln.template_3prime_base
                ? `${aln.primer_3prime_base}:${aln.template_3prime_base}`
                : '—';
              const tm = aln.tm_offtarget != null
                ? `${aln.tm_offtarget.toFixed(1)} / ${aln.tm_ontarget.toFixed(1)}`
                : '—';
              return (
                <tr key={i} title={h.risk_reason}>
                  <td className="px-2 py-1.5 font-mono text-slate-700 truncate max-w-[160px]">{h.subject_id}</td>
                  <td className="px-2 py-1.5 text-center tabular-nums text-slate-500">{tm}</td>
                  <td className="px-2 py-1.5 text-center tabular-nums text-slate-600">{aln.mismatches ?? '—'}</td>
                  <td className="px-2 py-1.5 text-center font-mono text-slate-600">{termMm}</td>
                  <td className="px-2 py-1.5 text-center text-slate-500">{termCat}</td>
                  <td className="px-2 py-1.5 text-center">
                    <span className={`font-bold px-1.5 py-0.5 rounded-full border ${style}`}>{h.risk}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {hits.length > 5 && (
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          className="text-xs text-teal-600 hover:underline"
        >
          {showAll ? `Show top 5 ▲` : `Show all ${hits.length} hits ▼`}
        </button>
      )}
    </div>
  );
}
