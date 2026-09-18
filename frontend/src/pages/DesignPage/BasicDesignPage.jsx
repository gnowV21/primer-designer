/**
 * BasicDesignPage — /design
 *
 * The beginner entry point: enter a miRNA, pick a sample type and a detection
 * chemistry, get primers. Every other parameter stays at the documented default
 * (constants/defaults.js) so the user never has to know it exists.
 *
 * Only two choices are exposed here, deliberately — they are the two inputs a
 * newcomer can answer from their bench setup alone, and both genuinely change
 * the design:
 *   - sample type  -> applies SAMPLE_TYPE_PRESETS (amplicon window, primer conc)
 *   - chemistry    -> TaqMan designs a hydrolysis probe; SYBR does not
 *
 * Anything more (Tm window, ionic strength, GC clamp, cycles…) lives on
 * /design/advanced, which shares this page's draft state.
 */
import { useEffect } from 'react';
import { SAMPLE_TYPE_PRESETS } from '../../constants/defaults.js';
import useDesignForm from '../../hooks/useDesignForm.js';
import DesignModeToggle from '../../components/DesignModeToggle.jsx';
import SequenceGroup from '../SearchPage/SequenceGroup.jsx';
import ResultsSection from '../SearchPage/ResultsSection/index.jsx';

// Descriptors are drawn from the same evidence as SAMPLE_TYPE_PRESETS warnings.
const SAMPLE_CARDS = [
  { value: 'tissue', label: 'Tissue',       hint: 'Biopsy or organ tissue' },
  { value: 'cell',   label: 'Cell culture', hint: 'Cultured cell lines' },
  { value: 'plasma', label: 'Plasma',       hint: 'Cell-free, low RNA' },
  { value: 'serum',  label: 'Serum',        hint: 'Cell-free, low RNA' },
  { value: 'ffpe',   label: 'FFPE',         hint: 'Fixed, fragmented RNA' },
  { value: 'urine',  label: 'Urine',        hint: 'May carry inhibitors' },
];

/** Human-readable summary of what a sample-type preset changed on the user's behalf. */
function presetSummary(preset) {
  const parts = [];
  if (preset.ampliconMin !== undefined || preset.ampliconMax !== undefined) {
    const lo = preset.ampliconMin !== undefined ? preset.ampliconMin : 60;
    const hi = preset.ampliconMax !== undefined ? preset.ampliconMax : 150;
    parts.push(`amplicon ${lo}–${hi} bp`);
  }
  if (preset.primerConcentration !== undefined) {
    parts.push(`primer ${preset.primerConcentration} nM`);
  }
  return parts;
}

export default function BasicDesignPage() {
  useEffect(() => { document.title = 'HG Lab | Primer Designer'; }, []);

  const {
    formData, setFormData,
    errors, handleChange, handleError, hasErrors,
    seqAnalysis,
    isSubmitting, canSubmit, handleSubmit,
    designError, errorRef,
  } = useDesignForm('basic');

  const sampleType   = formData.experimentalContext.sampleType;
  const signalMethod = formData.detectionMethod.signalMethod;
  const isTaqMan     = signalMethod === 'taqman';
  const preset       = SAMPLE_TYPE_PRESETS[sampleType] || {};
  const applied      = presetSummary(preset);

  /**
   * Picking a sample type applies its preset immediately. On the Advanced page
   * the same preset is offered as an opt-in banner; here we apply it silently
   * (and say so below) because choosing "FFPE" and still getting a 150 bp
   * amplicon would be a worse default than the beginner can diagnose.
   */
  function selectSample(value) {
    const p = SAMPLE_TYPE_PRESETS[value] || {};
    setFormData((prev) => {
      const nextMin = p.ampliconMin !== undefined ? p.ampliconMin : prev.qpcr.ampliconMin;
      const nextMax = p.ampliconMax !== undefined ? p.ampliconMax : prev.qpcr.ampliconMax;
      const validRange = nextMin < nextMax;
      return {
        ...prev,
        experimentalContext: { ...prev.experimentalContext, sampleType: value },
        qpcr: validRange
          ? { ...prev.qpcr, ampliconMin: nextMin, ampliconMax: nextMax }
          : prev.qpcr,
        thermodynamic: {
          ...prev.thermodynamic,
          ...(p.primerConcentration !== undefined && { primerConcentration: p.primerConcentration }),
        },
      };
    });
  }

  const stepClass = 'flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold shrink-0';

  return (
    <div className="max-w-2xl mx-auto space-y-6 pb-12">

      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-700">Design your primers</h1>
          <p className="text-sm text-gray-500 mt-1">
            Enter a miRNA and answer two questions — everything else uses validated defaults.
          </p>
        </div>
        <div className="shrink-0 pt-1">
          <DesignModeToggle current="basic" />
        </div>
      </div>

      {/* ── Step 1 — miRNA ── */}
      <div className="space-y-2">
        <div className="flex items-center gap-2.5">
          <span className={`${stepClass} ${seqAnalysis ? 'bg-teal-600 text-white' : 'bg-slate-200 text-slate-600'}`}>
            {seqAnalysis ? '✓' : '1'}
          </span>
          <h2 className="text-sm font-semibold text-slate-700">Which miRNA?</h2>
        </div>
        <SequenceGroup
          data={formData.sequence}
          errors={errors}
          onChange={(field, value) => handleChange('sequence', field, value)}
          onError={handleError}
          seqAnalysis={seqAnalysis}
          openRequested={0}
        />
      </div>

      {/* ── Step 2 — Sample type ── */}
      <div className="space-y-2">
        <div className="flex items-center gap-2.5">
          <span className={`${stepClass} bg-teal-600 text-white`}>2</span>
          <h2 className="text-sm font-semibold text-slate-700">What sample are you using?</h2>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            {SAMPLE_CARDS.map(({ value, label, hint }) => {
              const isActive = sampleType === value;
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => selectSample(value)}
                  aria-pressed={isActive}
                  className={`text-left rounded-xl border-2 px-3 py-2.5 transition-all duration-150 active:scale-[0.98] ${
                    isActive
                      ? 'border-teal-500 bg-teal-50 shadow-sm'
                      : 'border-gray-200 bg-white hover:border-teal-200 hover:bg-teal-50/30'
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <span className={`text-sm font-semibold ${isActive ? 'text-teal-800' : 'text-gray-700'}`}>
                      {label}
                    </span>
                    {isActive && <span className="ml-auto text-teal-600 text-sm font-bold">✓</span>}
                  </div>
                  <p className={`text-xs leading-snug mt-0.5 ${isActive ? 'text-teal-700' : 'text-gray-400'}`}>
                    {hint}
                  </p>
                </button>
              );
            })}
          </div>

          {/* Transparency: say what was auto-adjusted, never adjust silently. */}
          {applied.length > 0 && (
            <p className="text-xs text-teal-800 bg-teal-50 border border-teal-200 rounded-lg px-3 py-1.5">
              <span className="font-semibold">Adjusted for this sample:</span> {applied.join(' · ')}
            </p>
          )}
          {preset.warning && (
            <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
              {preset.warning}
            </p>
          )}
        </div>
      </div>

      {/* ── Step 3 — Detection chemistry ── */}
      <div className="space-y-2">
        <div className="flex items-center gap-2.5">
          <span className={`${stepClass} bg-teal-600 text-white`}>3</span>
          <h2 className="text-sm font-semibold text-slate-700">How will you detect the signal?</h2>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => handleChange('detectionMethod', 'signalMethod', 'taqman')}
              aria-pressed={isTaqMan}
              className={`text-left rounded-xl border-2 px-4 py-3 transition-all duration-150 active:scale-[0.98] ${
                isTaqMan
                  ? 'border-teal-500 bg-teal-50 shadow-sm'
                  : 'border-gray-200 bg-white hover:border-teal-200 hover:bg-teal-50/30'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-sm font-semibold ${isTaqMan ? 'text-teal-800' : 'text-gray-700'}`}>
                  TaqMan Probe
                </span>
                {isTaqMan && <span className="ml-auto text-teal-600 text-sm font-bold">✓</span>}
              </div>
              <p className={`text-xs leading-snug ${isTaqMan ? 'text-teal-700' : 'text-gray-400'}`}>
                Hydrolysis probe · high specificity · probe designed automatically
              </p>
            </button>

            <button
              type="button"
              onClick={() => handleChange('detectionMethod', 'signalMethod', 'sybr')}
              aria-pressed={!isTaqMan}
              className={`text-left rounded-xl border-2 px-4 py-3 transition-all duration-150 active:scale-[0.98] ${
                !isTaqMan
                  ? 'border-amber-400 bg-amber-50 shadow-sm'
                  : 'border-gray-200 bg-white hover:border-amber-200 hover:bg-amber-50/30'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-sm font-semibold ${!isTaqMan ? 'text-amber-800' : 'text-gray-700'}`}>
                  SYBR Green
                </span>
                {!isTaqMan && <span className="ml-auto text-amber-600 text-sm font-bold">✓</span>}
              </div>
              <p className={`text-xs leading-snug ${!isTaqMan ? 'text-amber-700' : 'text-gray-400'}`}>
                Intercalating dye · no probe · melting curve required
              </p>
            </button>
          </div>

          {!isTaqMan && (
            <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5">
              Melting curve analysis is mandatory after every run to confirm product specificity.
            </p>
          )}
        </div>
      </div>

      {/* ── Submit ── */}
      <div className="space-y-2 pt-1">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className={`w-full py-3 px-6 rounded-xl text-sm font-semibold transition-all shadow-md
            ${!canSubmit
              ? 'bg-gray-200 text-gray-400 cursor-not-allowed shadow-none'
              : 'bg-gradient-to-r from-teal-600 to-teal-800 text-white hover:opacity-90 hover:shadow-lg active:scale-[0.99]'
            }`}
        >
          {isSubmitting ? (
            <span className="flex items-center justify-center gap-2">
              <span className="animate-spin inline-block">⟳</span> Processing…
            </span>
          ) : hasErrors ? (
            <span className="flex items-center justify-center gap-2">
              <span className="text-gray-500">✕</span> Fix errors to continue
            </span>
          ) : !seqAnalysis ? (
            'Enter a miRNA to continue'
          ) : (
            'Design Primers →'
          )}
        </button>
        <p className="text-center text-xs text-gray-400">
          You&apos;ll get a stem-loop RT primer, a forward primer, and the universal reverse primer
          {isTaqMan ? ' — plus a TaqMan probe.' : '.'}
        </p>
        <p className="text-center text-xs text-gray-400">
          Need to tune Tm, salt or GC limits?{' '}
          <span className="text-teal-600 font-medium">Switch to Advanced</span> — your entries carry over.
        </p>
      </div>

      {/* ── Design error ── */}
      {designError && (
        <div ref={errorRef}>
          <ResultsSection results={null} error={designError} />
        </div>
      )}
    </div>
  );
}
