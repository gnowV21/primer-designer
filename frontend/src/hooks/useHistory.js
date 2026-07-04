/**
 * useHistory.js — React hook for session history (Phase 8 PART C)
 *
 * Manages IndexedDB-backed design history via historyDB.js.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  saveHistory as dbSave,
  listHistory as dbList,
  loadHistory as dbLoad,
  deleteHistory as dbDelete,
  clearHistory as dbClear,
} from '../lib/historyDB';

export default function useHistory() {
  const [entries, setEntries]   = useState([]);   // summaries list
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);

  // Load summary list on mount
  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await dbList();
      setEntries(list);
    } catch (err) {
      setError(err.message ?? "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  /**
   * Save a new design result.
   * @param {{ type, mirnas, params, results, summary }} entry
   * @returns {Promise<string>} id
   */
  const save = useCallback(async (entry) => {
    try {
      const id = await dbSave(entry);
      await refresh();
      return id;
    } catch (err) {
      setError(err.message ?? "Failed to save history");
      return null;
    }
  }, [refresh]);

  /**
   * Load full result for a history entry (without re-computing).
   * @param {string} id
   * @returns {Promise<object|null>}
   */
  const load = useCallback(async (id) => {
    try {
      return await dbLoad(id);
    } catch (err) {
      setError(err.message ?? "Failed to load history entry");
      return null;
    }
  }, []);

  /**
   * Delete a single entry.
   * @param {string} id
   */
  const remove = useCallback(async (id) => {
    try {
      await dbDelete(id);
      await refresh();
    } catch (err) {
      setError(err.message ?? "Failed to delete history entry");
    }
  }, [refresh]);

  /**
   * Delete all entries (shows native confirm).
   */
  const clearAll = useCallback(async () => {
    try {
      await dbClear();
      await refresh();
    } catch (err) {
      setError(err.message ?? "Failed to clear history");
    }
  }, [refresh]);

  return { entries, loading, error, refresh, save, load, remove, clearAll };
}
