/**
 * designRequest — the single place that POSTs to /api/design.
 *
 * Both the designer (/design) and the re-run bar on /results go through here,
 * so the request body and the error mapping can never drift between them.
 */
import axios from 'axios';

export const DESIGN_TIMEOUT_MS = 15000;

/**
 * Values derived from the thermodynamic inputs, sent alongside the form as
 * `_computed`. Effective monovalent = Na+ + K+ + protonated Tris (pKa 8.06,
 * standard 10 mM Tris), matching backend thermodynamics.effective_monovalent_mM.
 */
export function computeDerived(t) {
  const mg = t.magnesiumConcentration;
  const dntp = t.dntpTotal;
  const freeMg = Math.max(0, mg - dntp);
  const trisPlus = t.bufferPH != null ? 10 / (1 + Math.pow(10, t.bufferPH - 8.06)) : 0;
  const mono = (t.saltConcentration || 0) + (t.kPlusConc || 0) + trisPlus;
  const naEq = dntp < mg ? mono + 120 * Math.sqrt(mg - dntp) : mono;
  return {
    freeMagnesium: parseFloat(freeMg.toFixed(3)),
    naEquivalent:  parseFloat(naEq.toFixed(2)),
  };
}

/** The exact body POSTed for a given form state. */
export function buildDesignBody(formData) {
  return { ...formData, _computed: computeDerived(formData.thermodynamic) };
}

/** Strip request-only fields so a stored body can be edited as form state again. */
export function bodyToForm(body) {
  const { _computed, ...form } = body || {};   // eslint-disable-line no-unused-vars
  return form;
}

/** Map an axios failure to the error object ResultsSection knows how to render. */
export function toDesignError(err) {
  if (err.response?.status === 422) {
    const d = err.response.data || {};
    return {
      type: 'no_candidates',
      message: d.error || 'No valid candidates found.',
      suggestion: d.suggestion,
      rejection_summary: d.rejection_summary,
      edge_cases: d.edge_cases,
      global_warnings: d.global_warnings,
    };
  }
  if (err.response?.data?.error) return { type: 'validation', message: err.response.data.error };
  if (err.code === 'ECONNABORTED') {
    return { type: 'timeout', message: 'Request timed out. The backend may be overloaded.' };
  }
  return { type: 'network', message: 'Could not reach the backend. Is the Flask server running?' };
}

/** POST a design. Resolves with the response data, rejects with a toDesignError() object. */
export async function requestDesign(body) {
  try {
    const response = await axios.post('/api/design', body, { timeout: DESIGN_TIMEOUT_MS });
    return response.data;
  } catch (err) {
    throw toDesignError(err);
  }
}
