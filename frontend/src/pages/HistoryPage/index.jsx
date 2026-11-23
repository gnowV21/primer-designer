// HistoryPage — /history. Past designs saved in this browser (IndexedDB).
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listDesigns, deleteDesign, clearDesigns } from '../../utils/historyDb.js';

/** "#1 grade A · specificity 14/15" (4.0.0) or "best 93.1 (Excellent)" for older records (U5). */
function historySummary(d) {
  if (d.scoringSystem === 'tiered' && d.topSpecificity) {
    return `#1 grade ${d.grade} · specificity ${d.topSpecificity.total}/${d.topSpecificity.max}`;
  }
  // Records saved before 4.0.0 name their algorithm: their score is not comparable to a grade.
  const old = d.algorithmVersion && Number.parseInt(d.algorithmVersion, 10) < 4
    ? ` · algorithm v${d.algorithmVersion}` : '';
  if (d.topScore != null) return `best ${d.topScore} (${d.grade})${old}`;
  return old.slice(3);
}

/** "2026-11-23 08:59": the same date format as the PDF export, local time. */
function isoMinute(ms) {
  const t = new Date(ms);
  const p = (n) => String(n).padStart(2, '0');
  return `${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())} ${p(t.getHours())}:${p(t.getMinutes())}`;
}

export default function HistoryPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState(null);
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => { document.title = 'HG Lab | Design history'; }, []);
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
          <p className="text-sm text-slate-600 mt-1">
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
                className="text-xs px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200">
                Cancel
              </button>
            </div>
          ) : (
            <button type="button" onClick={() => setConfirmClear(true)}
              className="text-xs px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 shrink-0">
              Clear history
            </button>
          )
        )}
      </div>

      {rows === null && <p className="text-sm text-slate-600">Loading…</p>}
      {rows?.length === 0 && (
        <p className="text-sm text-slate-700 rounded-xl border border-slate-200 bg-slate-50 px-4 py-6 text-center">
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
                {/* Name and sequence are separate elements (screen readers read them apart). */}
                <p className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-sm font-medium text-slate-800 group-hover:text-teal-700 whitespace-nowrap">
                  {d.mirnaId || 'Unnamed miRNA'}
                  </span>
                  <span className="seq text-xs text-slate-600" aria-label={`sequence ${d.sequence}`}>{d.sequence}</span>
                </p>
                {d.results?.top3?.[0]?.sequence && (
                  <p className="text-xs text-slate-700">
                    #1 forward <span className="seq">{d.results.top3[0].sequence}</span>
                  </p>
                )}
                <p className="text-xs text-slate-600 tabular-nums">
                  <time dateTime={new Date(d.createdAt).toISOString()}>{isoMinute(d.createdAt)}</time>
                  {historySummary(d) && ` · ${historySummary(d)}`}
                </p>
              </button>
              <button
                type="button"
                onClick={() => remove(d.id)}
                aria-label={`Delete ${d.mirnaId || 'design'} from history`}
                className="text-xs px-2 py-1 rounded text-slate-700 hover:text-red-700 hover:bg-red-50"
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
