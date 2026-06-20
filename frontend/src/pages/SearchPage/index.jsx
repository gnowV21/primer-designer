import { useState, useMemo, useEffect, useCallback } from 'react';
import { DEFAULTS } from '../../constants/defaults.js';
import { computeSeqAnalysis } from '../../utils/seqAnalysis.js';
import SequenceGroup from './SequenceGroup.jsx';
import DetectionMethodGroup from './DetectionMethodGroup.jsx';
import ThermodynamicGroup from './ThermodynamicGroup.jsx';
import PrimerConstraintsGroup from './PrimerConstraintsGroup.jsx';
import QpcrConditionsGroup from './QpcrConditionsGroup.jsx';
import ExperimentalContextGroup from './ExperimentalContextGroup.jsx';

const NAV_SECTIONS = [
  { id: 'seq',         label: 'Sequence'  },
  { id: 'detection',   label: 'Detection' },
  { id: 'thermo',      label: 'Thermo.'   },
  { id: 'constraints', label: 'Primer'    },
  { id: 'qpcr',        label: 'qPCR'      },
  { id: 'context',     label: 'Context'   },
];

export default function SearchPage() {
  useEffect(() => { document.title = 'HG Lab | Primer Designer'; }, []);

  const [formData, setFormData] = useState({
    sequence:            { ...DEFAULTS.sequence },
    thermodynamic:       { ...DEFAULTS.thermodynamic },
    primerConstraints:   { ...DEFAULTS.primerConstraints },
    qpcr:                { ...DEFAULTS.qpcr },
    detectionMethod:     { ...DEFAULTS.detectionMethod },
    experimentalContext: { ...DEFAULTS.experimentalContext },
  });

  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeSection, setActiveSection] = useState('seq');
  const [visitedSections, setVisitedSections] = useState(new Set());
  const [resetKey, setResetKey] = useState(0);
  const [sectionOpenRequests, setSectionOpenRequests] = useState({});

  const markVisited = useCallback((id) => {
    setVisitedSections((prev) => prev.has(id) ? prev : new Set([...prev, id]));
  }, []);

  function handleChange(group, field, value) {
    setFormData((prev) => ({
      ...prev,
      [group]: { ...prev[group], [field]: value },
    }));
  }

  function handleError(field, message) {
    setErrors((prev) => {
      if (!message) {
        const next = { ...prev };
        delete next[field];
        return next;
      }
      return { ...prev, [field]: message };
    });
  }

  function handleApplyPreset(preset) {
    setFormData((prev) => {
      const nextMin = preset.ampliconMin !== undefined ? preset.ampliconMin : prev.qpcr.ampliconMin;
      const nextMax = preset.ampliconMax !== undefined ? preset.ampliconMax : prev.qpcr.ampliconMax;
      if (nextMin >= nextMax) return prev; // guard: invalid range from preset data
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

  const seqAnalysis = useMemo(
    () => computeSeqAnalysis(formData.sequence.matureSequence),
    [formData.sequence.matureSequence]
  );

  // Progress: section is "done" when the user has visited/interacted with it.
  // seq requires a valid sequence; all others are visit-tracked via visitedSections.
  const configured = Object.fromEntries(
    NAV_SECTIONS.map(({ id }) => [id, id === 'seq' ? seqAnalysis !== null : visitedSections.has(id)])
  );
  const readyCount = Object.values(configured).filter(Boolean).length;


  // Scroll listener: update active mini-nav highlight on manual scroll.
  // Threshold 80px keeps the active item below the sticky navbar height.
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
    markVisited(id); // clicking a nav item counts as "reviewing" that section
    setSectionOpenRequests((prev) => ({ ...prev, [id]: (prev[id] || 0) + 1 }));
    setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
  }

  const hasErrors = Object.keys(errors).length > 0;

  async function handleSubmit() {
    if (hasErrors || isSubmitting || !seqAnalysis) return;
    setIsSubmitting(true);
    try {
      // Week 1 milestone: log full form payload to prove data flows through all 6 groups
      console.log('[PrimerDesigner] formData:', JSON.stringify(formData, null, 2));
    } finally {
      setTimeout(() => {
        // Reset everything: form data, errors, progress, open states, nav highlight
        setFormData({
          sequence:            { ...DEFAULTS.sequence },
          thermodynamic:       { ...DEFAULTS.thermodynamic },
          primerConstraints:   { ...DEFAULTS.primerConstraints },
          qpcr:                { ...DEFAULTS.qpcr },
          detectionMethod:     { ...DEFAULTS.detectionMethod },
          experimentalContext: { ...DEFAULTS.experimentalContext },
        });
        setErrors({});
        setVisitedSections(new Set());
        setActiveSection('seq');
        setSectionOpenRequests({});
        setIsSubmitting(false);
        setResetKey((k) => k + 1); // remount sections so CollapsibleSections reset to defaultOpen
      }, 800);
    }
  }

  const seqTrimmed = formData.sequence.matureSequence.trim();
  const isSeqReady = seqTrimmed.length >= 15 && /^[AUGC]+$/i.test(seqTrimmed);

  return (
    <div className="flex gap-5 max-w-2xl xl:max-w-[52rem] mx-auto">

      {/* ── Mini nav (visible xl+, sticky) ── */}
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
                    <span
                      className={`w-2 h-2 rounded-full shrink-0 transition-all duration-300 ${
                        isReady ? 'bg-teal-500 scale-100' : 'bg-gray-300 scale-75'
                      }`}
                    />
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
          <div>
            <h1 className="text-xl font-semibold text-gray-700">Design your primers</h1>
            <p className="text-sm text-gray-500 mt-1">
              Enter miRNA information and adjust technical parameters.
            </p>
          </div>

          {/* Progress bar */}
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

        {/* ── Sections with anchor IDs ── */}
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

        <section id="detection" className="scroll-mt-4">
          <DetectionMethodGroup
            data={formData.detectionMethod}
            onChange={(field, value) => handleChange('detectionMethod', field, value)}
            seqAnalysis={seqAnalysis}
            onFirstOpen={() => markVisited('detection')}
            openRequested={sectionOpenRequests.detection || 0}
          />
        </section>

        <section id="thermo" className="scroll-mt-4">
          <ThermodynamicGroup
            seqAnalysis={seqAnalysis}
            data={formData.thermodynamic}
            errors={errors}
            onChange={(field, value) => handleChange('thermodynamic', field, value)}
            onError={handleError}
            onFirstOpen={() => markVisited('thermo')}
            openRequested={sectionOpenRequests.thermo || 0}
          />
        </section>

        <section id="constraints" className="scroll-mt-4">
          <PrimerConstraintsGroup
            data={formData.primerConstraints}
            onChange={(field, value) => handleChange('primerConstraints', field, value)}
            seqAnalysis={seqAnalysis}
            onFirstOpen={() => markVisited('constraints')}
            openRequested={sectionOpenRequests.constraints || 0}
          />
        </section>

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

        <section id="context" className="scroll-mt-4">
          <ExperimentalContextGroup
            data={formData.experimentalContext}
            onChange={(field, value) => handleChange('experimentalContext', field, value)}
            onApplyPreset={handleApplyPreset}
            onFirstOpen={() => markVisited('context')}
            openRequested={sectionOpenRequests.context || 0}
          />
        </section>

        {/* ── Submit — sticky at bottom of scroll container ── */}
        <div className="sticky bottom-0 z-10 space-y-2 pt-3 pb-5
          bg-gradient-to-t from-white from-70% via-white/90 to-transparent">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting || hasErrors || !seqAnalysis}
            className={`w-full py-3 px-6 rounded-xl text-sm font-semibold transition-all shadow-md
              ${isSubmitting || hasErrors
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
  );
}
