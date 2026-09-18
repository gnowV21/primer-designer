// NormalizationAdvisor — Phase 7 PART D (UX B1 ★★★)
// Displays normalization advisory from /api/design response.normalization_advice.
// Advisory only — does NOT affect primer scoring.
// Collapsed by default (toggle on/off), consistent with the Protocol Advisor.

import { useState } from 'react';

const ROLE_STYLE = {
  'exogenous spike-in': 'bg-violet-50 border-violet-200 text-violet-700',
  'endogenous candidate': 'bg-teal-50 border-teal-200 text-teal-700',
  'hemolysis marker': 'bg-red-50 border-red-200 text-red-700',
};

function ReferenceChip({ item: r }) {
  const style = ROLE_STYLE[r.role] || 'bg-slate-50 border-slate-200 text-slate-600';
  return (
    <div className={`rounded-lg border px-3 py-2 space-y-0.5 ${style}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs font-semibold">{r.name}</span>
        <span className="text-[10px] font-medium capitalize opacity-75">{r.role}</span>
      </div>
      <p className="text-[11px] opacity-80 leading-snug">{r.note}</p>
      {r.source_doi && (
        <a
          href={`https://doi.org/${r.source_doi}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[10px] underline opacity-60 hover:opacity-100"
        >
          doi:{r.source_doi}
        </a>
      )}
    </div>
  );
}

export default function NormalizationAdvisor({ advice }) {
  const [open, setOpen] = useState(false);

  if (!advice) return null;

  const {
    sample_type,
    rule_label,
    recommended_strategy,
    reference_candidates = [],
    cautions = [],
    validation_note,
    disclaimer,
    sources = [],
    external_tools = [],
  } = advice;

  return (
    <div className="rounded-xl border border-purple-200 bg-purple-50 overflow-hidden">
      {/* Header (toggle) */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-2 px-4 py-3 text-left hover:bg-purple-100/40 transition"
      >
        <div>
          <p className="text-xs font-semibold text-purple-800 uppercase tracking-wide">
            Normalization Advisor
          </p>
          {sample_type && (
            <p className="text-[11px] text-purple-600 mt-0.5">
              Sample type: <span className="font-medium capitalize">{sample_type}</span>
              {rule_label && ` — ${rule_label}`}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[10px] px-2 py-0.5 rounded border border-purple-200 bg-white text-purple-600 font-medium">
            Advisory only
          </span>
          <span className="text-purple-400 text-sm">{open ? '▲' : '▼'}</span>
        </div>
      </button>

      {/* Body (collapsed by default) */}
      {open && (
      <div className="px-4 pb-3 space-y-3 border-t border-purple-200 pt-3">
      {/* Recommended strategy */}
      <div className="rounded-lg bg-white border border-purple-200 px-3 py-2">
        <p className="text-xs font-semibold text-purple-700 mb-1">Recommended Strategy</p>
        <p className="text-xs text-slate-700 leading-relaxed">{recommended_strategy}</p>
      </div>

      {/* Reference candidates */}
      {reference_candidates.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] font-semibold text-purple-700 uppercase tracking-wide">
            Reference Candidates
          </p>
          <div className="grid grid-cols-1 gap-2">
            {reference_candidates.map((ref) => (
              <ReferenceChip key={ref.name} item={ref} />
            ))}
          </div>
        </div>
      )}

      {/* Cautions */}
      {cautions.length > 0 && (
        <div className="space-y-1.5">
          {cautions.map((c, i) => (
            <div
              key={i}
              className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 flex gap-2"
            >
              <span className="text-amber-500 shrink-0 mt-0.5">⚠</span>
              <div className="space-y-0.5">
                <p className="text-xs text-amber-800">{c.text}</p>
                {c.source_doi && (
                  <a
                    href={`https://doi.org/${c.source_doi}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] text-amber-600 underline hover:text-amber-800"
                  >
                    doi:{c.source_doi}
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Validation note + external tools */}
      <div className="rounded-lg bg-white border border-purple-200 px-3 py-2 space-y-1.5">
        {validation_note && (
          <p className="text-xs text-slate-600">{validation_note}</p>
        )}
        {external_tools.length > 0 && (
          <div className="flex flex-wrap gap-3 text-[11px]">
            {external_tools.map((tool) => (
              <a
                key={tool.name}
                href={tool.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-teal-600 underline hover:text-teal-800 font-medium"
              >
                {tool.name} →
              </a>
            ))}
          </div>
        )}
      </div>

      {/* Source DOIs */}
      {sources.length > 0 && (
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-purple-600">
          {sources.map((doi) => (
            <a
              key={doi}
              href={`https://doi.org/${doi}`}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-purple-800"
            >
              doi:{doi}
            </a>
          ))}
        </div>
      )}

      {/* MIQE 2.0 normalization requirement */}
      <div className="rounded-lg bg-white border border-purple-200 px-3 py-2">
        <p className="text-[11px] font-semibold text-purple-700">MIQE 2.0 — normalization</p>
        <p className="text-xs text-slate-600 leading-relaxed">
          Use <span className="font-semibold">≥ 2 reference genes</span> and normalize by their{' '}
          <span className="font-semibold">geometric mean</span>; validate their expression stability
          in your own experimental context (do not take reference genes from the literature alone).
        </p>
      </div>

      {/* Disclaimer */}
      <p className="text-[10px] italic text-purple-500 border-t border-purple-200 pt-2">
        {disclaimer}
      </p>
      </div>
      )}
    </div>
  );
}
