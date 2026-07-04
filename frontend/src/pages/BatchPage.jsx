/**
 * BatchPage — Batch design + session history (Phase 8 PART A + C)
 *
 * Left panel: BatchDesignPanel (input + progress + results)
 * Right panel: HistoryPanel (saved runs, load without re-compute)
 */

import { useEffect, useState } from 'react';
import BatchDesignPanel from '../components/BatchDesignPanel/index.jsx';
import HistoryPanel from '../components/HistoryPanel/index.jsx';
import useHistory from '../hooks/useHistory';

export default function BatchPage() {
  useEffect(() => { document.title = 'HG Lab | Batch Design'; }, []);

  const { save } = useHistory();
  const [loadedEntry, setLoadedEntry] = useState(null);

  async function handleBatchDone(results) {
    if (!results?.length) return;
    const succeeded = results.filter(r => r.status === 'ok');
    const bestScore = succeeded.reduce((best, r) => {
      const s = r.data?.top3?.[0]?.total_score ?? 0;
      return s > best ? s : best;
    }, 0);
    await save({
      type: 'batch',
      mirnas: results.map(r => r.mirna),
      params: {},
      results,
      summary: {
        count: results.length,
        succeeded: succeeded.length,
        failed: results.length - succeeded.length,
        best_score: bestScore,
      },
    });
  }

  function handleHistoryLoad(entry) {
    setLoadedEntry(entry);
  }

  return (
    <div className="flex gap-6 h-full min-h-0">
      {/* Left — batch design */}
      <div className="flex-1 min-w-0 overflow-y-auto">
        <div className="max-w-2xl mx-auto py-4 space-y-4">
          <BatchDesignPanel params={{}} onBatchDone={handleBatchDone} />

          {/* Loaded-from-history display */}
          {loadedEntry && (
            <div className="border border-blue-200 rounded-xl bg-blue-50 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-blue-800 text-sm">
                  Loaded from history —{' '}
                  {loadedEntry.type === 'batch'
                    ? `${loadedEntry.mirnas.length} miRNAs`
                    : loadedEntry.mirnas[0]}
                </span>
                <button
                  onClick={() => setLoadedEntry(null)}
                  className="text-blue-400 hover:text-blue-600 text-lg leading-none"
                >
                  &times;
                </button>
              </div>
              <p className="text-xs text-blue-600">
                Saved {new Date(loadedEntry.created_at).toLocaleString()} &nbsp;·&nbsp;
                {loadedEntry.summary?.succeeded ?? 0} / {loadedEntry.summary?.count ?? 0} succeeded &nbsp;·&nbsp;
                Best score {((loadedEntry.summary?.best_score ?? 0) * 100).toFixed(0)}
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {(loadedEntry.results ?? []).slice(0, 20).map((item, i) => {
                  const top = item.data?.top3?.[0];
                  return (
                    <div key={i} className="bg-white border border-blue-100 rounded-lg p-2.5 text-xs">
                      <div className="font-mono font-medium text-gray-800">{item.mirna}</div>
                      {top && (
                        <>
                          <div className="font-mono text-gray-600 truncate">{top.sequence}</div>
                          <div className="text-gray-400 flex gap-2 mt-0.5">
                            <span>Tm {top.tm?.toFixed(1)}°C</span>
                            <span>Score {(top.total_score * 100).toFixed(0)}</span>
                          </div>
                        </>
                      )}
                      {item.status === 'error' && (
                        <div className="text-red-600">{item.error}</div>
                      )}
                    </div>
                  );
                })}
                {(loadedEntry.results ?? []).length > 20 && (
                  <div className="text-xs text-gray-400 col-span-2 text-center">
                    + {loadedEntry.results.length - 20} more results
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right — history panel */}
      <div className="w-64 shrink-0 border-l border-gray-100 overflow-hidden">
        <HistoryPanel onLoad={handleHistoryLoad} className="h-full" />
      </div>
    </div>
  );
}
