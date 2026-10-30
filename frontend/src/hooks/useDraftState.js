/**
 * useDraftState — a useState whose value survives route changes but NOT a reload.
 *
 * Backed by a module-level in-memory Map (`_store`). Because the module lives for
 * the whole app session, the value persists when a page component unmounts on
 * navigation and is restored when the user returns. A full page reload resets the
 * JS heap, so the draft is intentionally cleared — matching "kept unless reloaded".
 *
 * This is deliberately NOT sessionStorage/localStorage: those survive a reload,
 * which is the opposite of the desired lifetime.
 *
 *   const [formData, setFormData] = useDraftState('designDraft.formData', () => ({...}));
 *
 * `initial` may be a value or a lazy factory (used only when no draft exists yet).
 */
import { useEffect, useState } from 'react';

const _store = new Map();

/** Remove one draft (e.g. an explicit "reset" action). */
export function clearDraft(key) {
  _store.delete(key);
}

/** Remove every draft (rarely needed; here for completeness). */
export function clearAllDrafts() {
  _store.clear();
}

export default function useDraftState(key, initial) {
  const [value, setValue] = useState(() =>
    _store.has(key)
      ? _store.get(key)
      : (typeof initial === 'function' ? initial() : initial)
  );

  // Write-through: keep the store in sync so the latest value is available the
  // next time this key mounts. Runs after commit, and pending passive effects
  // are flushed before unmount, so the store is current when we navigate away.
  useEffect(() => {
    _store.set(key, value);
  }, [key, value]);

  return [value, setValue];
}
