/**
 * designRequest — the single place that POSTs to /api/design.
 *
 * Both the designer (/design) and the re-run bar on /results go through here,
 * so the request body and the error mapping can never drift between them.
 */
import axios from 'axios';
import { DEFAULTS } from '../constants/defaults.js';

// Algorithm 4.0.0 BLASTs every surviving candidate during the design: ~10–13 s when
// the BLAST cache is cold (benchmark/tiered_design_timing.json, p90 11.9 s), more when
// requests queue on the backend's primer3 lock. 15 s (3.8.x, no BLAST) cut real designs.
export const DESIGN_TIMEOUT_MS = 60000;

/**
 * Buffer pH is applied only when the user changed it from the default
 * (project decision 2026-11-22). Unchanged, it is not sent, so the backend adds no
 * Tris term and the effective monovalent salt is saltConcentration (+ kPlusConc) —
 * the conditions of an empty API request, which every validation, benchmark and
 * thesis number uses.
 */
export function phApplied(t) {
  return t?.bufferPH != null && t.bufferPH !== DEFAULTS.thermodynamic.bufferPH;
}

/** The thermodynamic group as sent: without bufferPH unless phApplied(). */
export function thermoForRequest(t) {
  if (!t || phApplied(t)) return t;
  const { bufferPH, ...rest } = t;   // eslint-disable-line no-unused-vars
  return rest;
}

/**
 * Effective monovalent cations (mM) the backend uses for a SENT thermodynamic group:
 * Na+ + K+ + protonated Tris (10 mM, pKa 8.06) when bufferPH is present — the same
 * formula as backend thermodynamics.effective_monovalent_mM.
 */
export function effectiveMonovalent(sent) {
  const trisPlus = sent?.bufferPH != null ? 10 / (1 + Math.pow(10, sent.bufferPH - 8.06)) : 0;
  return (sent?.saltConcentration || 0) + (sent?.kPlusConc || 0) + trisPlus;
}

/**
 * Values derived from the thermodynamic inputs, sent alongside the form as
 * `_computed` (ignored by the backend). Uses the group as it will be sent.
 */
export function computeDerived(t) {
  const sent = thermoForRequest(t);
  const mg = t.magnesiumConcentration;
  const dntp = t.dntpTotal;
  const freeMg = Math.max(0, mg - dntp);
  const mono = effectiveMonovalent(sent);
  const naEq = dntp < mg ? mono + 120 * Math.sqrt(mg - dntp) : mono;
  return {
    freeMagnesium: parseFloat(freeMg.toFixed(3)),
    naEquivalent:  parseFloat(naEq.toFixed(2)),
  };
}

/** The exact body POSTed for a given form state. */
export function buildDesignBody(formData) {
  return {
    ...formData,
    thermodynamic: thermoForRequest(formData.thermodynamic),
    _computed: computeDerived(formData.thermodynamic),
  };
}

/** Strip request-only fields so a stored body can be edited as form state again.
 *  A body sent without bufferPH (default pH, not applied) gets the default back. */
export function bodyToForm(body) {
  const { _computed, ...form } = body || {};   // eslint-disable-line no-unused-vars
  if (form.thermodynamic && form.thermodynamic.bufferPH == null) {
    form.thermodynamic = { ...form.thermodynamic, bufferPH: DEFAULTS.thermodynamic.bufferPH };
  }
  return form;
}

/**
 * One line for a run designed with extra K+ (History records saved before
 * 2026-11-22 carry kPlusConc 50 and an applied pH). null when kPlusConc is 0.
 */
export function legacySaltNote(sentThermo) {
  const k = sentThermo?.kPlusConc || 0;
  if (!(k > 0)) return null;
  const na = sentThermo.saltConcentration || 0;
  const z = effectiveMonovalent(sentThermo);
  return `Designed with K⁺ ${k} mM + Na⁺ ${na} mM (effective ${Number(z.toFixed(1))} mM); `
    + `current default is ${DEFAULTS.thermodynamic.saltConcentration} mM total.`;
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
