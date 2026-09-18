/**
 * SearchPage — /design/advanced
 *
 * The full designer: every thermodynamic, constraint and protocol parameter is
 * editable. Form state and submit logic live in useDesignForm, shared with the
 * Basic page (/design), so switching modes preserves everything already entered.
 */
import { useState, useEffect, useCallback } from 'react';
import useDesignForm from '../../hooks/useDesignForm.js';
import DesignModeToggle from '../../components/DesignModeToggle.jsx';
import SequenceGroup from './SequenceGroup.jsx';
import DetectionMethodGroup from './DetectionMethodGroup.jsx';
import PrimerConstraintsGroup from './PrimerConstraintsGroup.jsx';
import QpcrConditionsGroup from './QpcrConditionsGroup.jsx';
import ExperimentalContextGroup from './ExperimentalContextGroup.jsx';
import ResultsSection from './ResultsSection/index.jsx';

const NAV_SECTIONS = [
  { id: 'seq',         label: 'Sequence' },
  { id: 'method',      label: 'Method'   },
  { id: 'constraints', label: 'Primer'   },
  { id: 'qpcr',        label: 'qPCR'     },
  { id: 'context',     label: 'Context'  },
];

export default function SearchPage() {
  useEffect(() => { document.title = 'HG Lab | Primer Designer (Advanced)'; }, []);

  const {
    formData, setFormData,
    errors, handleChange, handleError, hasErrors,
    seqAnalysis,
    isSubmitting, canSubmit, handleSubmit,
    designError, errorRef,
  } = useDesignForm('advanced');

  const [activeSection, setActiveSection] = useState('seq');
  const [visitedSections, setVisitedSections] = useState(new Set());
  const [resetKey] = useState(0);
  const [sectionOpenRequests, setSectionOpenRequests] = useState({});

  const markVisited = useCallback((id) => {
    setVisitedSections((prev) => prev.has(id) ? prev : new Set([...prev, id]));
  }, []);

  function handleApplyPreset(preset) {
    setFormData((prev) => {
      const nextMin = preset.ampliconMin !== undefined ? preset.ampliconMin : prev.qpcr.ampliconMin;
      const nextMax = preset.ampliconMax !== undefined ? preset.ampliconMax : prev.qpcr.ampliconMax;
      if (nextMin >= nextMax) return prev;
      return {
        ...prev,
        qpcr: {
          ...prev.qpcr,
          ampliconMin: nextMin,
          ampliconMax: nextMax,
        },
        thermodynamic: {
          ...prev.thermodynamic,
          ...(preset.primerConcentration !== undefined && { primerConcentration: preset.primerConcentration }),
        },
      };
    });
  }

  const configured = Object.fromEntries(
    NAV_SECTIONS.map(({ id }) => [id, id === 'seq' ? seqAnalysis !== null : visitedSections.has(id)])
  );
  const readyCount = Object.values(configured).filter(Boolean).length;

  useEffect(() => {
    const sectionIds = NAV_SECTIONS.map((s) => s.id);
    const main = document.querySelector('main');
    if (!main) return;

    function handleScroll() {
      let current = 'seq';
      for (const id of sectionIds) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top <= 80) current = id;
      }
      setActiveSection(current);
    }

    main.addEventListener('scroll', handleScroll, { passive: true });
    return () => main.removeEventListener('scroll', handleScroll);
  }, []);

  function scrollToSection(id) {
    setActiveSection(id);
    markVisited(id);
    setSectionOpenRequests((prev) => ({ ...prev, [id]: (prev[id] || 0) + 1 }));
    setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
  }

  const seqTrimmed = formData.sequence.matureSequence.trim();
  const isSeqReady = seqTrimmed.length >= 15 && /^[AUGC]+$/i.test(seqTrimmed);

  return (
    <div className="max-w-2xl xl:max-w-[52rem] mx-auto space-y-6">
    <div className="flex gap-5">

      {/* ── Mini nav ── */}
      <aside className="hidden xl:block w-32 shrink-0 self-start sticky top-6">
        <nav className="pt-1">
          <p className="text-xs font-bold text-slate-600 mb-3 px-3 tracking-wide uppercase">
            Sections
          </p>
          <ul className="space-y-1">
            {NAV_SECTIONS.map(({ id, label }) => {
              const isActive = activeSection === id;
              const isReady  = !!configured[id];
              return (
                <li key={id}>
                  <button
                    type="button"
                    onClick={() => scrollToSection(id)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-sm font-medium
                      transition-all duration-150 active:scale-[0.96]
                      ${isActive
                        ? 'bg-teal-50 text-teal-700 ring-1 ring-teal-200 shadow-sm'
                        : 'text-gray-600 hover:text-teal-700 hover:bg-teal-50'
                      }`}
                  >
                    <span className={`w-2 h-2 rounded-full shrink-0 transition-all duration-300 ${
                      isReady ? 'bg-teal-500 scale-100' : 'bg-gray-300 scale-75'
                    }`} />
                    <span className="truncate">{label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>

      {/* ── Main form ── */}
      <div className="flex-1 min-w-0 space-y-5" key={resetKey}>

        {/* Header + progress */}
        <div className="space-y-3">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-semibold text-gray-700">Design your primers</h1>
              <p className="text-sm text-gray-500 mt-1">
                Enter miRNA information and adjust technical parameters.
              </p>
            </div>
            <div className="shrink-0 pt-1">
              <DesignModeToggle current="advanced" />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-teal-500 rounded-full transition-all duration-500 ease-out"
                style={{ width: `${(readyCount / NAV_SECTIONS.length) * 100}%` }}
              />
            </div>
            <span className="text-xs text-gray-500 shrink-0 tabular-nums font-medium">
              {readyCount}/{NAV_SECTIONS.length} ready
            </span>
          </div>
        </div>

        {/* ── Sequence ── */}
        <section id="seq" className="scroll-mt-4">
          <SequenceGroup
            data={formData.sequence}
            errors={errors}
            onChange={(field, value) => handleChange('sequence', field, value)}
            onError={handleError}
            seqAnalysis={seqAnalysis}
            openRequested={sectionOpenRequests.seq || 0}
          />
        </section>

        {/* ── Detection Method ── */}
        <section id="method" className="scroll-mt-4">
          <DetectionMethodGroup
            data={formData.detectionMethod}
            onChange={(field, value) => handleChange('detectionMethod', field, value)}
            seqAnalysis={seqAnalysis}
            onFirstOpen={() => markVisited('method')}
            openRequested={sectionOpenRequests.method || 0}
          />
        </section>

        {/* ── Primer Design Constraints ── */}
        <section id="constraints" className="scroll-mt-4">
          <PrimerConstraintsGroup
            data={formData.primerConstraints}
            onChange={(field, value) => handleChange('primerConstraints', field, value)}
            seqAnalysis={seqAnalysis}
            mirnaFamily={formData.sequence.family}
            thermoData={formData.thermodynamic}
            thermoErrors={{
              saltConcentration:      errors.saltConcentration,
              primerConcentration:    errors.primerConcentration,
              magnesiumConcentration: errors.magnesiumConcentration,
              dntpTotal:              errors.dntpTotal,
              kPlusConc:              errors.kPlusConc,
              bufferPH:               errors.bufferPH,
            }}
            onThermoChange={(field, value) => handleChange('thermodynamic', field, value)}
            onThermoError={handleError}
            onFirstOpen={() => markVisited('constraints')}
            openRequested={sectionOpenRequests.constraints || 0}
          />
        </section>

        {/* ── qPCR ── */}
        <section id="qpcr" className="scroll-mt-4">
          <QpcrConditionsGroup
            data={formData.qpcr}
            errors={errors}
            onChange={(field, value) => handleChange('qpcr', field, value)}
            onError={handleError}
            tmMin={formData.thermodynamic.tmMin}
            onFirstOpen={() => markVisited('qpcr')}
            openRequested={sectionOpenRequests.qpcr || 0}
          />
        </section>

        {/* ── Experimental Context ── */}
        <section id="context" className="scroll-mt-4">
          <ExperimentalContextGroup
            data={formData.experimentalContext}
            onChange={(field, value) => handleChange('experimentalContext', field, value)}
            onApplyPreset={handleApplyPreset}
            onFirstOpen={() => markVisited('context')}
            openRequested={sectionOpenRequests.context || 0}
          />
        </section>

        {/* ── Submit ── */}
        <div className="space-y-2 pt-3 pb-5">
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
            ) : (
              'Design Primers →'
            )}
          </button>
          {isSeqReady && !hasErrors && (
            <p className="text-center text-xs text-gray-400">
              Stem-loop primer · Forward primer · Universal reverse primer
            </p>
          )}
        </div>
      </div>
    </div>

      {/* ── Design error ── */}
      {designError && (
        <div ref={errorRef} className="pb-10">
          <ResultsSection results={null} error={designError} />
        </div>
      )}
    </div>
  );
}
