/**
 * historyDB.js — IndexedDB wrapper for session history (Phase 8 PART C)
 *
 * Stores design results client-side — no server, no auth, full privacy.
 * Capacity: IndexedDB (hundreds MB) — handles batch >20 miRNA results.
 * Retention: MAX_ENTRIES most-recent entries (FIFO eviction).
 *
 * Schema (store "design_history"):
 *   id:         "hist_<timestamp_ms>_<uuid8>"  — keyPath (unique, collision-safe)
 *   type:       "single" | "batch"
 *   created_at: ISO8601 string
 *   mirnas:     string[]                — 1 for single, N for batch
 *   params:     {}                      — ion conditions used
 *   results:    []                      — full design output
 *   summary:    { count, succeeded, failed, best_score }
 */

const DB_NAME    = "hglab_primer_history";
const STORE      = "design_history";
const DB_VERSION = 1;
const MAX_ENTRIES = 100;   // FIFO eviction when exceeded

// ── DB open (singleton promise) ────────────────────────────────────────────────

let _dbPromise = null;

function _openDB() {
  if (_dbPromise) return _dbPromise;
  _dbPromise = new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      _dbPromise = null;
      reject(new Error("IndexedDB not available in this environment"));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "id" });
        store.createIndex("created_at", "created_at", { unique: false });
      }
    };
    req.onsuccess  = (e) => resolve(e.target.result);
    req.onerror    = (e) => { _dbPromise = null; reject(e.target.error); };
    req.onblocked  = ()  => { _dbPromise = null; reject(new Error("IndexedDB open blocked — close other tabs")); };
  });
  return _dbPromise;
}

// ── Low-level helpers ──────────────────────────────────────────────────────────

function _promisify(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror   = (e) => reject(e.target.error);
  });
}

// ── Public API ─────────────────────────────────────────────────────────────────

/**
 * Persist a design result entry.
 * Enforces MAX_ENTRIES by deleting oldest when limit is exceeded.
 * All operations (put + getAllKeys + delete) run inside a single readwrite
 * transaction — atomic, no race between concurrent tab saves.
 *
 * @param {{ type, mirnas, params, results, summary }} entry
 * @returns {Promise<string>} the assigned id
 */
export function saveHistory(entry) {
  // Append 8-char UUID fragment to guard against same-millisecond collisions.
  const id = `hist_${Date.now()}_${crypto.randomUUID().slice(0, 8)}`;
  const record = {
    id,
    type:       entry.type,
    created_at: new Date().toISOString(),
    mirnas:     entry.mirnas ?? [],
    params:     entry.params ?? {},
    results:    entry.results ?? [],
    summary:    entry.summary ?? {},
  };

  return _openDB().then(db => new Promise((resolve, reject) => {
    const tx    = db.transaction(STORE, "readwrite");
    const store = tx.objectStore(STORE);

    const putReq = store.put(record);
    putReq.onsuccess = () => {
      const keysReq = store.getAllKeys();
      keysReq.onsuccess = (e) => {
        const allKeys = e.target.result;
        if (allKeys.length > MAX_ENTRIES) {
          const sorted   = [...allKeys].sort();
          const toDelete = sorted.slice(0, allKeys.length - MAX_ENTRIES);
          for (const k of toDelete) store.delete(k);
        }
      };
      keysReq.onerror = (e) => reject(e.target.error);
    };
    putReq.onerror = (e) => reject(e.target.error);

    tx.oncomplete = () => resolve(id);
    tx.onerror    = (e) => reject(e.target.error);
    tx.onabort    = ()  => reject(new Error("Transaction aborted"));
  }));
}

/**
 * List all history summaries (without full results — fast render).
 * Returns newest first.
 *
 * @returns {Promise<Array<{ id, type, created_at, mirnas, summary }>>}
 */
export async function listHistory() {
  const db      = await _openDB();
  const records = await _promisify(db.transaction(STORE, "readonly").objectStore(STORE).getAll());
  return records
    .map(({ id, type, created_at, mirnas, summary }) =>
      ({ id, type, created_at, mirnas, summary }))
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
}

/**
 * Load a full history entry (including results) by id.
 *
 * @param {string} id
 * @returns {Promise<object|null>}
 */
export async function loadHistory(id) {
  const db = await _openDB();
  const record = await _promisify(db.transaction(STORE, "readonly").objectStore(STORE).get(id));
  return record ?? null;
}

/**
 * Delete a single history entry.
 *
 * @param {string} id
 */
export async function deleteHistory(id) {
  const db = await _openDB();
  await _promisify(db.transaction(STORE, "readwrite").objectStore(STORE).delete(id));
}

/**
 * Delete all history entries.
 */
export async function clearHistory() {
  const db = await _openDB();
  await _promisify(db.transaction(STORE, "readwrite").objectStore(STORE).clear());
}

/**
 * Return total number of history entries.
 *
 * @returns {Promise<number>}
 */
export async function countHistory() {
  const db = await _openDB();
  return _promisify(db.transaction(STORE, "readonly").objectStore(STORE).count());
}
