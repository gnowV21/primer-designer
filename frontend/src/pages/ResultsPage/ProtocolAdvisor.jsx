// ProtocolAdvisor.jsx — SPEC_phase5 §A.5
// Collapsible panel showing evidence-backed protocol suggestions from /api/design.protocol_advice.
// Descriptive only: never prescriptive. All items carry DOI links.

import { useState } from 'react';

const MATCH_STYLE = {
  high:   'bg-amber-50 border-amber-300 text-amber-800',
  medium: 'bg-blue-50  border-blue-200  text-blue-800',
  low:    'bg-slate-50 border-slate-200  text-slate-700',
};
const MATCH_BADGE = {
  high:   'bg-amber-100 text-amber-800',
  medium: 'bg-blue-100  text-blue-800',
  low:    'bg-slate-100 text-slate-600',
};

export default function ProtocolAdvisor({ advice = [] }) {
  const [open, setOpen] = useState(false);

  if (!advice || advice.length === 0) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      {/* ── Header (toggle) ── */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-50 transition"
      >
        <div className="flex items-center gap-2">
          <span className="text-base">💡</span>
          <span className="text-sm font-semibold text-slate-700">Protocol Advisor</span>
          <span className="text-xs text-slate-400 font-normal">
            {advice.length} suggestion{advice.length !== 1 ? 's' : ''} based on your assay parameters
          </span>
        </div>
        <span className="text-slate-400 text-sm">{open ? '▲' : '▼'}</span>
      </button>

      {/* ── Body (collapsed by default) ── */}
      {open && (
        <div className="border-t border-slate-100 px-4 py-3 space-y-3">
          {advice.map((item) => (
            <AdviceCard key={item.id} item={item} />
          ))}
          <p className="text-xs text-slate-400 italic border-t border-slate-100 pt-2 mt-1">
            Suggestions are based on published literature and your assay parameters. They are
            descriptive only and do not constitute clinical guidance. Validate all primers
            experimentally before use.
          </p>
          {advice[0]?.kb_version && (
            <p className="text-xs text-slate-400">
              Knowledge base v{advice[0].kb_version} · updated {advice[0].kb_updated}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function AdviceCard({ item }) {
  const [expanded, setExpanded] = useState(false);
  const match = item.match || 'low';

  return (
    <div className={`rounded-lg border px-3 py-2.5 ${MATCH_STYLE[match]}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${MATCH_BADGE[match]}`}>
              {match.toUpperCase()}
            </span>
            <span className="text-xs font-semibold opacity-60">{item.id}</span>
            {item.title && (
              <span className="text-xs font-medium truncate">{item.title}</span>
            )}
          </div>
          <p className="text-xs leading-relaxed">{item.recommendation}</p>
        </div>
        <button
          onClick={() => setExpanded(e => !e)}
          className="shrink-0 text-xs underline opacity-60 hover:opacity-100"
        >
          {expanded ? 'less' : 'details'}
        </button>
      </div>

      {expanded && (
        <div className="mt-2 space-y-2">
          {/* Pros */}
          {item.pros?.length > 0 && (
            <div>
              <p className="text-xs font-semibold mb-0.5">Advantages</p>
              <ul className="list-disc list-inside space-y-0.5">
                {item.pros.map((p, i) => (
                  <li key={i} className="text-xs">{p}</li>
                ))}
              </ul>
            </div>
          )}
          {/* Cons */}
          {item.cons?.length > 0 && (
            <div>
              <p className="text-xs font-semibold mb-0.5">Considerations</p>
              <ul className="list-disc list-inside space-y-0.5">
                {item.cons.map((c, i) => (
                  <li key={i} className="text-xs">{c}</li>
                ))}
              </ul>
            </div>
          )}
          {/* Sources */}
          {item.sources?.length > 0 && (
            <div>
              <p className="text-xs font-semibold mb-0.5">References</p>
              <div className="flex flex-wrap gap-1.5">
                {item.sources.map((s, i) => (
                  s.doi ? (
                    <a
                      key={i}
                      href={`https://doi.org/${s.doi}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs underline opacity-70 hover:opacity-100"
                      title={s.note || s.doi}
                    >
                      [{s.tag}]
                    </a>
                  ) : (
                    <span key={i} className="text-xs opacity-70" title={s.note || s.tag}>
                      [{s.tag}]
                    </span>
                  )
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
