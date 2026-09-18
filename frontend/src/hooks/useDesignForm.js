/**
 * useDesignForm — form state + submit logic shared by the Basic and Advanced
 * design pages.
 *
 * Both pages POST the exact same body to /api/design; they differ only in how
 * many of the fields the user is allowed to see and edit. Keeping the state in
 * one hook means:
 *   - switching Basic <-> Advanced preserves everything the user already set
 *     (same draft key, so Advanced opens pre-filled with the Basic choices),
 *   - the request shape and error handling can never drift between the pages.
 *
 * `mode` ('basic' | 'advanced') is recorded in experimentalContext.userLevel so
 * ResultsPage can decide how much detail to show by default.
 */
import { useState, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { DEFAULTS } from '../constants/defaults.js';
import useDraftState from './useDraftState.js';
import { computeSeqAnalysis } from '../utils/seqAnalysis.js';

export default function useDesignForm(mode) {
  const navigate = useNavigate();

  // Single draft key for BOTH pages — this is what makes the mode switch lossless.
  const [formData, setFormData] = useDraftState('designDraft.formData', () => ({
    sequence:            { ...DEFAULTS.sequence },
    thermodynamic:       { ...DEFAULTS.thermodynamic },
    primerConstraints:   { ...DEFAULTS.primerConstraints },
    qpcr:                { ...DEFAULTS.qpcr },
    detectionMethod:     { ...DEFAULTS.detectionMethod },
    experimentalContext: { ...DEFAULTS.experimentalContext },
  }));

  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [designError, setDesignError] = useState(null);
  const errorRef = useRef(null);

  const handleChange = useCallback((group, field, value) => {
    setFormData((prev) => ({
      ...prev,
      [group]: { ...prev[group], [field]: value },
    }));
  }, [setFormData]);

  const handleError = useCallback((field, message) => {
    setErrors((prev) => {
      if (!message) {
        if (!(field in prev)) return prev;
        const next = { ...prev };
        delete next[field];
        return next;
      }
      if (prev[field] === message) return prev;
      return { ...prev, [field]: message };
    });
  }, []);

  const seqAnalysis = useMemo(
    () => computeSeqAnalysis(formData.sequence.matureSequence),
    [formData.sequence.matureSequence]
  );

  const computedFields = useMemo(() => {
    const t    = formData.thermodynamic;
    const mg   = t.magnesiumConcentration;
    const dntp = t.dntpTotal;
    const freeMg = Math.max(0, mg - dntp);
    // Effective monovalent = Na+ + K+ + protonated Tris (Tris+), matching backend
    // thermodynamics.effective_monovalent_mM (Tris pKa 8.06, standard 10 mM Tris).
    const trisPlus = t.bufferPH != null ? 10 / (1 + Math.pow(10, t.bufferPH - 8.06)) : 0;
    const mono = (t.saltConcentration || 0) + (t.kPlusConc || 0) + trisPlus;
    const naEq = dntp < mg ? mono + 120 * Math.sqrt(mg - dntp) : mono;
    return {
      freeMagnesium: parseFloat(freeMg.toFixed(3)),
      naEquivalent:  parseFloat(naEq.toFixed(2)),
    };
  }, [formData.thermodynamic]);

  const hasErrors = Object.keys(errors).length > 0;
  const canSubmit = !hasErrors && !isSubmitting && seqAnalysis !== null;

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;
    setIsSubmitting(true);
    setDesignError(null);
    try {
      // userLevel travels with the request so the results page knows which
      // level of detail to open with. It does not affect the algorithm.
      const postBody = {
        ...formData,
        experimentalContext: { ...formData.experimentalContext, userLevel: mode },
        _computed: computedFields,
      };
      const response = await axios.post('/api/design', postBody, { timeout: 15000 });
      navigate('/results', { state: { results: response.data, params: postBody } });
    } catch (err) {
      if (err.response?.status === 422) {
        setDesignError({
          type: 'no_candidates',
          message: err.response.data?.error || 'No valid candidates found.',
          suggestion: err.response.data?.suggestion,
          rejection_summary: err.response.data?.rejection_summary,
          edge_cases: err.response.data?.edge_cases,
          global_warnings: err.response.data?.global_warnings,
        });
      } else if (err.response?.data?.error) {
        setDesignError({ type: 'validation', message: err.response.data.error });
      } else if (err.code === 'ECONNABORTED') {
        setDesignError({ type: 'timeout', message: 'Request timed out. The backend may be overloaded.' });
      } else {
        setDesignError({ type: 'network', message: 'Could not reach the backend. Is the Flask server running?' });
      }
      setTimeout(() => {
        errorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } finally {
      setIsSubmitting(false);
    }
  }, [canSubmit, formData, computedFields, mode, navigate]);

  return {
    formData, setFormData,
    errors, handleChange, handleError, hasErrors,
    seqAnalysis, computedFields,
    isSubmitting, canSubmit, handleSubmit,
    designError, errorRef,
  };
}
