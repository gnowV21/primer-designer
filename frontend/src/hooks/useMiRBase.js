import { useState, useCallback, useRef } from 'react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export function useMiRBase() {
  const [status, setStatus] = useState('idle'); // 'idle'|'loading'|'found'|'not_found'|'error'
  const [result, setResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const abortRef = useRef(null);

  const fetchMiRNA = useCallback(async (mirnaId) => {
    if (!mirnaId || mirnaId.trim() === '') return;

    // Cancel any in-flight request so stale responses never overwrite newer ones
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setStatus('loading');
    setResult(null);
    setErrorMessage('');

    try {
      const response = await axios.get(`${API_BASE}/api/mirbase/${mirnaId.trim()}`, {
        timeout: 10000,
        signal: abortRef.current.signal,
      });
      setResult(response.data);
      setStatus('found');
    } catch (error) {
      if (axios.isCancel(error)) return; // request was superseded by a newer one — ignore
      if (error.response?.status === 404) {
        setStatus('not_found');
        setErrorMessage(`"${mirnaId}" not found. Please check the ID or enter the sequence manually.`);
      } else if (error.code === 'ECONNABORTED') {
        setStatus('error');
        setErrorMessage('Connection timed out. Check your network and try again.');
      } else {
        setStatus('error');
        setErrorMessage('Cannot reach backend. Make sure the backend server is running at localhost:5000.');
      }
    }
  }, []);

  const reset = useCallback(() => {
    setStatus('idle');
    setResult(null);
    setErrorMessage('');
  }, []);

  return { status, result, errorMessage, fetchMiRNA, reset };
}
