import { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const BLAST_TIMEOUT_MS = 70_000;

export default function useBlastCheck() {
  const [status,      setStatus]      = useState('idle'); // 'idle' | 'loading' | 'done' | 'error'
  const [result,      setResult]      = useState(null);
  const [error,       setError]       = useState(null);
  const [dbAvailable, setDbAvailable] = useState(null);  // null = unknown, true/false after status check
  const [dbMessage,   setDbMessage]   = useState('');
  const abortRef = useRef(null);

  // Check DB availability once on mount (Phase 7 PART A)
  useEffect(() => {
    let cancelled = false;
    axios.get('/api/blast-status', { timeout: 5_000 })
      .then((r) => {
        if (!cancelled) {
          setDbAvailable(r.data.available ?? null);
          setDbMessage(r.data.message || '');
        }
      })
      .catch(() => {
        // Network error or server not responding — don't block user (null = unknown)
        if (!cancelled) setDbAvailable(null);
      });
    return () => { cancelled = true; };
  }, []);

  // mirnaSequence + conditions (the design's effective_p3) feed the duplex-Tm gate;
  // without them the backend falls back to the DB sequence and default salts.
  async function run(forwardPrimer, reversePrimer, mirnaId, { mirnaSequence, conditions, species } = {}) {
    // Cancel any in-flight request
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus('loading');
    setResult(null);
    setError(null);

    try {
      const resp = await axios.post(
        '/api/blast-check',
        {
          forward_primer: forwardPrimer,
          reverse_primer: reversePrimer,
          mirna_id: mirnaId,
          mirna_sequence: mirnaSequence || undefined,
          conditions: conditions || undefined,
          species: species || undefined,
        },
        { signal: controller.signal, timeout: BLAST_TIMEOUT_MS },
      );
      setResult(resp.data);
      setStatus('done');
    } catch (err) {
      if (axios.isCancel(err) || err.name === 'AbortError') return;
      setError(parseBlastError(err));
      setStatus('error');
    }
  }

  function reset() {
    if (abortRef.current) abortRef.current.abort();
    setStatus('idle');
    setResult(null);
    setError(null);
  }

  return { status, result, error, run, reset, dbAvailable, dbMessage };
}

function parseBlastError(err) {
  if (err.code === 'ECONNABORTED') {
    return { type: 'timeout', message: 'BLAST search timed out (>70 s). Try again.' };
  }
  if (!err.response) {
    return { type: 'network', message: 'Network error — check that the server is running.' };
  }
  const status = err.response.status;
  const data   = err.response.data || {};
  if (status === 429) {
    const retryAfter = parseInt(err.response.headers?.['retry-after'] ?? '60', 10);
    return { type: '429', message: data.error || 'Rate limit: max 10 checks / min.', retryAfter };
  }
  if (status === 503) {
    return {
      type: '503',
      message: data.error || 'BLAST service temporarily unavailable.',
      retryAfter: data.retry_after_seconds ?? 60,
    };
  }
  return { type: 'server', message: data.error || `Server error (${status}).` };
}
