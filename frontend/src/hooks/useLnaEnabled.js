import { useState, useEffect } from 'react';
import axios from 'axios';

/**
 * useLnaEnabled — whether the backend LNA-Tm suggestion feature is enabled.
 *
 * Reads `features.lna_suggestions` from GET /api/health. The feature is gated
 * OFF while the McTigue 2004 / Owczarzy 2011 NN tables are still placeholders
 * (see backend USE_LNA_SUGGESTIONS). Defaults to `false` until the check
 * resolves so the LNA entry points never flash on when the feature is off.
 */
export default function useLnaEnabled() {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    let cancelled = false;
    axios.get('/api/health', { timeout: 5_000 })
      .then((r) => { if (!cancelled) setEnabled(Boolean(r.data?.features?.lna_suggestions)); })
      .catch(() => { if (!cancelled) setEnabled(false); });
    return () => { cancelled = true; };
  }, []);

  return enabled;
}
