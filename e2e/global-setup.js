// Playwright global setup — warm the backend BLAST cache (SPEC_ui_tiered_4.0.0 §3).
//
// Algorithm 4.0.0 BLASTs the candidates during /api/design: ~10–13 s per design when the
// cache is cold, ~3 s when warm. The specs below design these miRNAs through the UI with
// the frontend's default parameters, so the same bodies are sent here once, in series,
// before the parallel workers start. A failure here only makes the first specs slower.
import { request } from '@playwright/test';
import { DEFAULTS } from '../frontend/src/constants/defaults.js';
import { computeDerived } from '../frontend/src/utils/designRequest.js';
import { WARM_MIRNAS } from './helpers.js';

export default async function globalSetup(config) {
  const baseURL = config.projects[0]?.use?.baseURL || 'http://localhost:5173';
  const ctx = await request.newContext({ baseURL });
  for (const { name, sequence } of WARM_MIRNAS) {
    const form = { ...DEFAULTS, sequence: { ...DEFAULTS.sequence, mirnaName: name, matureSequence: sequence } };
    const t0 = Date.now();
    try {
      const r = await ctx.post('/api/design', {
        data: { ...form, _computed: computeDerived(form.thermodynamic) },
        timeout: 120_000,
      });
      const rs = (await r.json()).ranking_summary || {};
      console.log(`[warm] ${name}: HTTP ${r.status()} in ${Date.now() - t0} ms, `
        + `BLAST cache ${rs.blast_cache_hits ?? '?'}/${rs.blast_candidates ?? '?'}`);
    } catch (e) {
      console.log(`[warm] ${name}: ${e.message}`);
    }
  }
  await ctx.dispose();
}
