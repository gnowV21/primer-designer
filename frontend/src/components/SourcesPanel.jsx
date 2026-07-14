/**
 * SourcesPanel — the papers behind the last answer [SPEC_Phase1 §5.1 step 6].
 *
 * The citation numbers here are the same [1], [2] the model used in its answer, which makes
 * "grounded or silent" (§0) something the user can actually verify: every bracket in the
 * text resolves to a real PubMed link on this panel.
 */
export default function SourcesPanel({ sources }) {
  if (!sources?.length) return null;

  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold text-gray-700">
        Sources <span className="font-normal text-gray-400">({sources.length})</span>
      </h2>

      <ol className="space-y-2">
        {sources.map((s) => (
          <li key={s.n}
              className="border border-gray-200 rounded-lg px-3 py-2 hover:border-teal-300 transition-colors">
            <div className="flex gap-2">
              <span className="text-[11px] font-bold text-teal-700 shrink-0">[{s.n}]</span>
              <div className="min-w-0">
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[12px] font-medium text-gray-700 hover:text-teal-700 hover:underline leading-snug block"
                >
                  {s.title || 'Untitled'}
                </a>
                <p className="text-[11px] text-gray-400 mt-0.5">
                  {[s.authors, s.journal, s.year].filter(Boolean).join(' · ')}
                </p>
                <p className="text-[10px] text-gray-300 mt-0.5">PMID {s.pmid}</p>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
