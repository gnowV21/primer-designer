/**
 * useDesignForm — form state + submit logic for the designer (/design).
 *
 * The draft lives under DESIGN_DRAFT_KEY, so it survives navigation: going to
 * /results and back restores the miRNA and every parameter. The results page
 * writes the same key when the user tunes parameters there, so "Back to
 * designer" opens with the parameters of the result being viewed.
 *
 * The request itself goes through utils/designRequest — the same helper the
 * re-run bar on /results uses — so the body and error mapping cannot drift.
 */
import { useState, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { DEFAULTS } from '../constants/defaults.js';
import useDraftState from './useDraftState.js';
import { saveDesign } from '../utils/historyDb.js';
import { computeSeqAnalysis } from '../utils/seqAnalysis.js';
import { buildDesignBody, computeDerived, requestDesign } from '../utils/designRequest.js';
import { DESIGN_DRAFT_KEY, firstRunState } from '../utils/designRuns.js';

export function initialFormData() {
  return {
    sequence:            { ...DEFAULTS.sequence },
    thermodynamic:       { ...DEFAULTS.thermodynamic },
    primerConstraints:   { ...DEFAULTS.primerConstraints },
    qpcr:                { ...DEFAULTS.qpcr },
    detectionMethod:     { ...DEFAULTS.detectionMethod },
    experimentalContext: { ...DEFAULTS.experimentalContext },
  };
}

export default function useDesignForm() {
  const navigate = useNavigate();
  const [formData, setFormData] = useDraftState(DESIGN_DRAFT_KEY, initialFormData);

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

  // Binding-region stats follow the chosen 3' overhang length (5-7 nt), never a fixed 6.
  const seqAnalysis = useMemo(
    () => computeSeqAnalysis(
      formData.sequence.matureSequence,
      formData.primerConstraints.bindingRegion3prime,
    ),
    [formData.sequence.matureSequence, formData.primerConstraints.bindingRegion3prime]
  );

  const computedFields = useMemo(
    () => computeDerived(formData.thermodynamic),
    [formData.thermodynamic]
  );

  const hasErrors = Object.keys(errors).length > 0;
  const canSubmit = !hasErrors && !isSubmitting && seqAnalysis !== null;

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;
    setIsSubmitting(true);
    setDesignError(null);
    try {
      const body = buildDesignBody(formData);
      const results = await requestDesign(body);
      saveDesign(body, results);   // best-effort, not awaited
      navigate('/results', { state: firstRunState(body, results) });
    } catch (err) {
      setDesignError(err);
      setTimeout(() => {
        errorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } finally {
      setIsSubmitting(false);
    }
  }, [canSubmit, formData, navigate]);

  const clearErrors = useCallback(() => setErrors({}), []);

  return {
    formData, setFormData,
    errors, handleChange, handleError, hasErrors, clearErrors,
    seqAnalysis, computedFields,
    isSubmitting, canSubmit, handleSubmit,
    designError, errorRef,
  };
}
