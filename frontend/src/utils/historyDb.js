// Design history in the browser's IndexedDB (audit ENG-03 / Gap B4).
// Native API only — no dependency. Stays on this device; never sent to the server.
// Every call resolves (never throws): private windows or blocked storage just
// mean "no history", and a failed save must never break a design.

const DB_NAME = 'hglab-primer-designer';
const STORE = 'designs';
const MAX_ENTRIES = 50;   // ponytail: oldest pruned past this; add export/import if users need more

function openDb() {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') { reject(new Error('IndexedDB unavailable')); return; }
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// Run `fn(store)` in one transaction; resolves with the request's result (if any).
function run(mode, fn) {
  return openDb().then((db) => new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    const req = fn(tx.objectStore(STORE));
    tx.oncomplete = () => { db.close(); resolve(req?.result); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  }));
}

/** All designs, newest first. */
export async function listDesigns() {
  try {
    const rows = await run('readonly', (store) => store.getAll());
    return (rows || []).sort((a, b) => b.createdAt - a.createdAt);
  } catch {
    return [];
  }
}

/** Save one design. `params` is the POST body, `results` the /api/design response. */
export async function saveDesign(params, results) {
  try {
    const top = results?.top3?.[0];
    await run('readwrite', (store) => store.add({
      createdAt: Date.now(),
      mirnaId: results?.metadata?.mirna_id || '',
      sequence: params?.sequence?.matureSequence || '',
      topScore: top?.total_score ?? null,
      grade: top?.grade ?? null,
      algorithmVersion: results?.metadata?.algorithm_version ?? null,
      params,
      results,
    }));
    const extra = (await listDesigns()).slice(MAX_ENTRIES);
    if (extra.length) await run('readwrite', (store) => { extra.forEach((d) => store.delete(d.id)); });
  } catch { /* history is best-effort */ }
}

export async function deleteDesign(id) {
  try { await run('readwrite', (store) => store.delete(id)); } catch { /* ignore */ }
}

export async function clearDesigns() {
  try { await run('readwrite', (store) => store.clear()); } catch { /* ignore */ }
}
