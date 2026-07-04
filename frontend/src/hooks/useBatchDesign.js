/**
 * useBatchDesign.js — React hook for batch primer design (Phase 8 PART A)
 *
 * Automatically selects sync (NDJSON streaming) or async (job polling)
 * based on the number of miRNA IDs submitted.
 *
 * status: idle | streaming | polling | done | error
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import axios from 'axios';

const BATCH_ASYNC_THRESHOLD = 10;   // must match backend constant
const POLL_INTERVAL_MS = 2000;

export default function useBatchDesign() {
  const [status,   setStatus]   = useState('idle');
  const [progress, setProgress] = useState({ completed: 0, total: 0, succeeded: 0, failed: 0 });
  const [results,  setResults]  = useState([]);
  const [errors,   setErrors]   = useState([]);
  const [jobId,    setJobId]    = useState(null);
  const pollRef = useRef(null);

  // Clear the polling interval on unmount to prevent memory leaks and stale setState calls.
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const reset = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    setStatus('idle');
    setProgress({ completed: 0, total: 0, succeeded: 0, failed: 0 });
    setResults([]);
    setErrors([]);
    setJobId(null);
  }, []);

  // ── Sync streaming (NDJSON) ──────────────────────────────────────────────────
  const _runSync = useCallback(async (mirnas, params) => {
    setStatus('streaming');
    setProgress({ completed: 0, total: mirnas.length, succeeded: 0, failed: 0 });
    setResults([]);
    setErrors([]);

    try {
      const res = await fetch('/api/batch-design', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mirnas, params }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error ?? 'Batch request failed');
      }

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let   buf     = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();   // keep incomplete last line

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const msg = JSON.parse(line);
            if (msg.type === 'result') {
              const upd = (prev) => {
                const next = { ...prev };
                next.completed += 1;
                if (msg.status === 'ok') next.succeeded += 1;
                else                     next.failed    += 1;
                return next;
              };
              setProgress(upd);
              if (msg.status === 'ok') setResults(r => [...r, msg]);
              else                     setErrors(e => [...e, { mirna: msg.mirna, error: msg.error }]);
            }
          } catch { /* ignore malformed line */ }
        }
      }
      setStatus('done');
    } catch (err) {
      setErrors(e => [...e, { mirna: 'batch', error: err.message }]);
      setStatus('error');
    }
  }, []);

  // ── Async job + polling ──────────────────────────────────────────────────────
  const _runAsync = useCallback(async (mirnas, params) => {
    setStatus('polling');
    setProgress({ completed: 0, total: mirnas.length, succeeded: 0, failed: 0 });
    setResults([]);
    setErrors([]);

    let jid;
    try {
      const res = await axios.post('/api/batch-design', { mirnas, params });
      jid = res.data.job_id;
      setJobId(jid);
    } catch (err) {
      setErrors([{ mirna: 'batch', error: err.response?.data?.error ?? err.message }]);
      setStatus('error');
      return;
    }

    pollRef.current = setInterval(async () => {
      try {
        const res = await axios.get(`/api/batch-status/${jid}`);
        const d = res.data;
        setProgress({
          completed: d.completed,
          total:     d.total,
          succeeded: d.succeeded,
          failed:    d.failed,
        });
        setResults(d.results ?? []);
        setErrors(d.errors ?? []);

        if (d.status === 'done' || d.status === 'error') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setStatus(d.status === 'done' ? 'done' : 'error');
        }
      } catch (err) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        setErrors(e => [...e, { mirna: 'poll', error: err.message }]);
        setStatus('error');
      }
    }, POLL_INTERVAL_MS);
  }, []);

  // ── Public run ───────────────────────────────────────────────────────────────
  const run = useCallback((mirnas, params) => {
    reset();
    if (mirnas.length <= BATCH_ASYNC_THRESHOLD) {
      return _runSync(mirnas, params);
    }
    return _runAsync(mirnas, params);
  }, [reset, _runSync, _runAsync]);

  return { status, progress, results, errors, jobId, run, reset };
}
