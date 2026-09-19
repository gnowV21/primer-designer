// HistoryPage — /history. Past designs saved in this browser (IndexedDB).
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listDesigns, deleteDesign, clearDesigns } from '../../utils/historyDb.js';

export default function HistoryPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState(null);
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => { document.title = 'HG Lab | Design History'; }, []);
  useEffect(() => { listDesigns().then(setRows); }, []);

  async function remove(id) {
    await deleteDesign(id);
    setRows((r) => r.filter((d) => d.id !== id));
  }

  async function clearAll() {
    await clearDesigns();
    setRows([]);
    setConfirmClear(false);
  }

  return (
    <div className="max-w-3xl mx-auto space-y-5 pb-12">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Design history</h1>
          <p className="text-sm text-slate-500 mt-1">
            Your last 50 designs, stored only in this browser. Clearing browser data removes them.
          </p>
        </div>
        {rows?.length > 0 && (
          confirmClear ? (
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-slate-600">Delete all?</span>
              <button type="button" onClick={clearAll}
                className="text-xs px-3 py-1.5 rounded-lg bg-red-600 text-white font-medium hover:bg-red-700">
                Delete
              </button>
              <button type="button" onClick={() => setConfirmClear(false)}
                className="text-xs px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200">
                Cancel
              </button>
            </div>
          ) : (
            <button type="button" onClick={() => setConfirmClear(true)}
              className="text-xs px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200 shrink-0">
              Clear history
            </button>
          )
        )}
      </div>

      {rows === null && <p className="text-sm text-slate-500">Loading…</p>}
      {rows?.length === 0 && (
        <p className="text-sm text-slate-500 rounded-xl border border-slate-200 bg-slate-50 px-4 py-6 text-center">
          No saved designs yet. Every design you run is added here automatically.
        </p>
      )}

      {rows?.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {rows.map((d) => (
            <li key={d.id} className="flex items-center gap-3 px-4 py-3">
              <button
                type="button"
                onClick={() => navigate('/results', { state: { results: d.results, params: d.params } })}
                className="flex-1 min-w-0 text-left group"
              >
                <p className="text-sm font-medium text-slate-800 group-hover:text-teal-700 truncate">
                  {d.mirnaId || 'Unnamed miRNA'}
                  <span className="ml-2 font-mono text-xs text-slate-500">{d.sequence}</span>
                </p>
                <p className="text-xs text-slate-500 tabular-nums">
                  {new Date(d.createdAt).toLocaleString()}
                  {d.topScore != null && ` · best ${d.topScore} (${d.grade})`}
                  {d.algorithmVersion && ` · v${d.algorithmVersion}`}
                </p>
              </button>
              <button
                type="button"
                onClick={() => remove(d.id)}
                aria-label={`Delete ${d.mirnaId || 'design'} from history`}
                className="text-xs px-2 py-1 rounded text-slate-500 hover:text-red-700 hover:bg-red-50"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
