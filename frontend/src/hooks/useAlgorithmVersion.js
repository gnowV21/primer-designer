import { useState, useEffect } from 'react';
import axios from 'axios';

let cached = null;   // one /api/health call per page load

/** The backend algorithm version (GET /api/health `version`), or null until known. */
export default function useAlgorithmVersion() {
  const [version, setVersion] = useState(cached);
  useEffect(() => {
    if (cached) return undefined;
    let cancelled = false;
    axios.get('/api/health', { timeout: 5_000 })
      .then((r) => {
        cached = r.data?.version || null;
        if (!cancelled) setVersion(cached);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);
  return version;
}
