import { useEffect, useState } from 'react';
import { fetchPapers, ingestPapers } from '../api/chatApi.js';

/**
 * KnowledgeBase — populate and inspect the paper corpus [SPEC_Phase1 §3, §6].
 *
 * Without this the corpus is empty, and an empty corpus means the assistant can only ever
 * answer "Not enough data to conclude" (§0). Ingesting is therefore the first thing a new
 * user has to do, so it lives on the same page as the chat.
 */

// The topics SPEC_Phase1 §3.1 names as the target corpus.
const PRESETS = [
  'stem-loop RT-qPCR microRNA quantification',
  'high resolution melting analysis genotyping',
  'miRNA primer design specificity',
  'HRM melting curve primer-dimer non-specific product',
];

export default function KnowledgeBase() {
  const [query, setQuery]     = useState('');
  const [papers, setPapers]   = useState([]);
  const [total, setTotal]     = useState(0);
  const [loading, setLoading] = useState(false);
  const [status, setStatus]   = useState(null);   // { kind: 'ok'|'err', title, detail }
  const [expanded, setExpanded] = useState(false);

  async function refresh() {
    try {
      const data = await fetchPapers({ perPage: 50 });
      setPapers(data.papers);
      setTotal(data.total);
    } catch {
      /* The list is a convenience; a failure here must not block ingesting. */
    }
  }

  useEffect(() => { refresh(); }, []);

  async function ingest(q) {
    const term = (q ?? query).trim();
    if (!term || loading) return;

    setLoading(true);
    setStatus(null);
    try {
      const res = await ingestPapers({ query: term, maxResults: 20 });
      setStatus({
        kind:  'ok',
        title: `${res.n_added} paper${res.n_added === 1 ? '' : 's'} added`,
        detail: [
          `${res.n_found ?? 0} found on PubMed`,
          res.n_skipped ? `${res.n_skipped} already in the base` : null,
          res.total_chunks ? `${res.total_chunks} chunks embedded` : null,
          res.n_failed ? `${res.n_failed} failed` : null,
        ].filter(Boolean).join(' · '),
      });
      await refresh();
    } catch (err) {
      setStatus({ kind: 'err', title: err.error, detail: err.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700">
          Knowledge base{' '}
          <span className="font-normal text-gray-400">
            ({total} paper{total === 1 ? '' : 's'})
          </span>
        </h2>
        {papers.length > 0 && (
          <button type="button" onClick={() => setExpanded((v) => !v)}
                  className="text-[11px] text-gray-400 hover:text-gray-600 underline">
            {expanded ? 'Hide' : 'Show'} papers
          </button>
        )}
      </div>

      <form onSubmit={(e) => { e.preventDefault(); ingest(); }} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={loading}
          placeholder="PubMed search, e.g. stem-loop RT-qPCR microRNA"
          className="flex-1 text-xs border border-gray-200 rounded-lg px-3 py-2
                     focus:outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-200
                     disabled:bg-gray-50"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="px-4 py-2 rounded-lg bg-teal-600 text-white text-xs font-semibold
                     hover:bg-teal-800 disabled:bg-gray-200 disabled:text-gray-400
                     disabled:cursor-not-allowed transition-colors whitespace-nowrap"
        >
          {loading ? 'Ingesting…' : 'Ingest'}
        </button>
      </form>

      {total === 0 && !loading && (
        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => { setQuery(p); ingest(p); }}
              className="text-[11px] text-gray-500 border border-gray-200 rounded-full px-2.5 py-1
                         hover:border-teal-300 hover:text-teal-700 hover:bg-teal-50 transition-colors"
            >
              + {p}
            </button>
          ))}
        </div>
      )}

      {loading && (
        <p className="text-[11px] text-gray-400">
          Searching PubMed and embedding abstracts. The first run also downloads the
          embedding model (~440 MB) — it can take several minutes.
        </p>
      )}

      {status && (
        <div className={`border rounded-lg px-3 py-2 ${
          status.kind === 'ok'
            ? 'border-teal-200 bg-teal-50'
            : 'border-red-200 bg-red-50'
        }`}>
          <p className={`text-xs font-semibold ${
            status.kind === 'ok' ? 'text-teal-800' : 'text-red-600'
          }`}>
            {status.title}
          </p>
          {status.detail && (
            <p className={`text-[11px] mt-0.5 ${
              status.kind === 'ok' ? 'text-teal-700' : 'text-red-500'
            }`}>
              {status.detail}
            </p>
          )}
        </div>
      )}

      {expanded && papers.length > 0 && (
        <ul className="border border-gray-200 rounded-xl divide-y divide-gray-100 max-h-64 overflow-y-auto">
          {papers.map((p) => (
            <li key={p.pmid} className="px-3 py-2 hover:bg-gray-50">
              <a href={p.url} target="_blank" rel="noopener noreferrer"
                 className="text-[12px] text-gray-700 hover:text-teal-700 hover:underline leading-snug block">
                {p.title}
              </a>
              <p className="text-[10px] text-gray-400 mt-0.5">
                {[p.journal, p.year, `${p.n_chunks} chunk${p.n_chunks === 1 ? '' : 's'}`]
                  .filter(Boolean).join(' · ')}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
