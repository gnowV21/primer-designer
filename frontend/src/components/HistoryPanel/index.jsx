/**
 * HistoryPanel — Session history sidebar (Phase 8 PART C)
 *
 * Displays IndexedDB-backed design history.
 * Load entry → re-renders results without re-computing.
 * Export/import: future-work (Phase 9).
 */

import { useState } from 'react';
import useHistory from '../../hooks/useHistory';

function formatDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

/** Single history entry row */
function HistoryEntry({ entry, onLoad, onDelete, active }) {
  const { id, type, created_at, mirnas, summary } = entry;
  const label = mirnas.length === 1
    ? mirnas[0]
    : `${mirnas[0]} +${mirnas.length - 1} more`;

  return (
    <div
      className={`border rounded-lg p-2.5 text-sm cursor-pointer transition-colors ${
        active
          ? 'border-teal-400 bg-teal-50'
          : 'border-gray-200 bg-white hover:bg-gray-50'
      }`}
      onClick={() => onLoad(id)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
              type === 'batch'
                ? 'bg-blue-100 text-blue-700'
                : 'bg-teal-100 text-teal-700'
            }`}>
              {type === 'batch' ? 'Batch' : 'Single'}
            </span>
            <span className="text-[10px] text-gray-400">{formatDate(created_at)}</span>
          </div>
          <div className="font-mono text-xs truncate text-gray-700">{label}</div>
          {summary && (
            <div className="text-[10px] text-gray-400 mt-0.5 flex gap-2">
              {summary.succeeded != null && (
                <span>{summary.succeeded}/{summary.count ?? mirnas.length} OK</span>
              )}
              {summary.best_score != null && (
                <span>Score {(summary.best_score * 100).toFixed(0)}</span>
              )}
            </div>
          )}
        </div>
        <button
          onClick={e => { e.stopPropagation(); onDelete(id); }}
          className="text-gray-300 hover:text-red-400 text-base leading-none shrink-0"
          title="Delete entry"
        >
          &times;
        </button>
      </div>
    </div>
  );
}

/**
 * @param {{
 *   onLoad: (fullEntry: object) => void,  — called with full result to re-render
 *   className?: string,
 * }} props
 */
export default function HistoryPanel({ onLoad, className = '' }) {
  const { entries, loading, error, remove, clearAll, load } = useHistory();
  const [activeId,    setActiveId]    = useState(null);
  const [clearing,    setClearing]    = useState(false);

  async function handleLoad(id) {
    const full = await load(id);
    if (full) {
      setActiveId(id);
      onLoad?.(full);
    }
  }

  async function handleDelete(id) {
    await remove(id);
    if (activeId === id) setActiveId(null);
  }

  async function handleClearAll() {
    if (!window.confirm('Delete all history entries? This cannot be undone.')) return;
    setClearing(true);
    await clearAll();
    setActiveId(null);
    setClearing(false);
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-gray-800">History</span>
          {entries.length > 0 && (
            <span className="text-[10px] bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded-full font-medium">
              {entries.length}
            </span>
          )}
        </div>
        {entries.length > 0 && (
          <button
            onClick={handleClearAll}
            disabled={clearing}
            className="text-xs text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
          >
            {clearing ? 'Clearing…' : 'Clear all'}
          </button>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {loading && (
          <div className="text-center text-sm text-gray-400 py-6">Loading…</div>
        )}
        {error && (
          <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">{error}</div>
        )}
        {!loading && entries.length === 0 && (
          <div className="text-center text-sm text-gray-400 py-8 px-2">
            No history yet.
            <br />
            <span className="text-xs">Design results appear here automatically.</span>
          </div>
        )}
        {entries.map(entry => (
          <HistoryEntry
            key={entry.id}
            entry={entry}
            active={entry.id === activeId}
            onLoad={handleLoad}
            onDelete={handleDelete}
          />
        ))}
      </div>

      {/* Future-work note */}
      {entries.length > 0 && (
        <div className="px-3 py-1.5 border-t border-gray-100 text-[10px] text-gray-400">
          Export/import history — coming in a future update.
        </div>
      )}
    </div>
  );
}
