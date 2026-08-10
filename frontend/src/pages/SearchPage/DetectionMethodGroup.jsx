import { useState } from 'react';
import Tooltip from '../../components/ui/Tooltip.jsx';
import CollapsibleSection from '../../components/ui/CollapsibleSection.jsx';

const REFERENCE_GENE_OPTIONS = [
  { value: 'miR-16',    label: 'miR-16',    desc: 'hsa-miR-16-5p — stable across most tissues' },
  { value: 'U6',        label: 'U6 snRNA',  desc: 'small nuclear RNA U6 — common for serum/plasma' },
  { value: 'RNU48',     label: 'RNU48',     desc: 'stable in human tissue' },
  { value: 'cel-miR-39',label: 'cel-miR-39',desc: 'C. elegans spike-in control for serum/plasma' },
  { value: 'custom',    label: 'Custom',    desc: 'enter miRBase ID manually' },
];

function Reveal({ show, children }) {
  return (
    <div className={`grid transition-[grid-template-rows] duration-300 ease-in-out ${show ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}>
      <div className="overflow-hidden">{children}</div>
    </div>
  );
}

export default function DetectionMethodGroup({ data, onChange, seqAnalysis, onFirstOpen, openRequested }) {
  const [showSpecificity, setShowSpecificity] = useState(false);
  const isCustomRef = data.referenceGene === 'custom';
  const isTaqMan = data.signalMethod === 'taqman';
  const isSYBR   = data.signalMethod === 'sybr';

  return (
    <CollapsibleSection
      title="Detection Method"
      tooltip="Choose TaqMan (hydrolysis probe) or SYBR Green (intercalating dye). This controls which primers and outputs are generated."
      accent="purple"
      onFirstOpen={onFirstOpen}
      openRequested={openRequested}
    >
      {/* Non-canonical 5' end warning */}
      {seqAnalysis && !seqAnalysis.startsWithU && (
        <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
          <strong>Non-canonical 5′ end:</strong> This miRNA does not start with U — detection efficiency may be lower. Consider increasing RNA input.
        </div>
      )}

      {/* ── Signal detection — card picker ── */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-gray-700">Signal detection</label>
        <div className="grid grid-cols-2 gap-3">
          {/* TaqMan card */}
          <button
            type="button"
            onClick={() => onChange('signalMethod', 'taqman')}
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

          {/* SYBR Green card */}
          <button
            type="button"
            onClick={() => onChange('signalMethod', 'sybr')}
            className={`text-left rounded-xl border-2 px-4 py-3 transition-all duration-150 active:scale-[0.98] ${
              isSYBR
                ? 'border-amber-400 bg-amber-50 shadow-sm'
                : 'border-gray-200 bg-white hover:border-amber-200 hover:bg-amber-50/30'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-sm font-semibold ${isSYBR ? 'text-amber-800' : 'text-gray-700'}`}>
                SYBR Green
              </span>
              {isSYBR && <span className="ml-auto text-amber-600 text-sm font-bold">✓</span>}
            </div>
            <p className={`text-xs leading-snug ${isSYBR ? 'text-amber-700' : 'text-gray-400'}`}>
              Intercalating dye · no probe · melting curve required
            </p>
          </button>
        </div>

        {/* SYBR mandatory note */}
        <Reveal show={isSYBR}>
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5 mt-0.5">
            Melting curve analysis is mandatory after every run to confirm product specificity.
          </p>
        </Reveal>
      </div>

      {/* ── Quantification mode ── */}
      <div className="space-y-2">
        <div className="flex items-center gap-1.5">
          <label className="text-sm font-medium text-gray-700">Quantification mode</label>
          <Tooltip text="Absolute: reports copy number per volume. Relative: reports fold-change vs. a reference sample using the 2^(−ΔΔCt) formula." />
        </div>
        <div className="flex gap-4">
          {[
            { value: 'absolute', label: 'Absolute' },
            { value: 'relative', label: 'Relative' },
          ].map(({ value, label }) => (
            <label key={value} className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="radio"
                name="quantMode"
                value={value}
                checked={data.quantMode === value}
                onChange={() => onChange('quantMode', value)}
                className="accent-teal-600"
              />
              <span className="text-sm text-gray-700">{label}</span>
            </label>
          ))}
        </div>

        <Reveal show={data.quantMode === 'relative'}>
          <div className="space-y-1.5 pt-0.5">
            <div className="flex items-center gap-1.5">
              <label className="text-sm font-medium text-gray-700">Reference gene</label>
              <Tooltip text="Housekeeping reference used to normalize RNA input across samples. miR-16 is stable in most tissues. Use cel-miR-39 (spike-in) for serum or plasma." />
            </div>
            <select
              value={data.referenceGene}
              onChange={(e) => onChange('referenceGene', e.target.value)}
              className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 text-gray-900 focus:outline-none focus:border-teal-300 focus:ring-1 focus:ring-teal-100 bg-white"
            >
              {REFERENCE_GENE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label} — {opt.desc}
                </option>
              ))}
            </select>
            <Reveal show={isCustomRef}>
              <input
                type="text"
                value={data.customReferenceGene}
                onChange={(e) => onChange('customReferenceGene', e.target.value)}
                placeholder="e.g. hsa-miR-103a-3p"
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-teal-300 focus:ring-1 focus:ring-teal-100"
              />
            </Reveal>
          </div>
        </Reveal>
      </div>

      {/* ── Advanced specificity ── */}
      <div className="space-y-2">
        <button
          type="button"
          onClick={() => setShowSpecificity((v) => !v)}
          className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-teal-700 transition-colors"
        >
          <span className={`text-teal-600 font-bold text-sm leading-none transition-transform duration-200 ${showSpecificity ? 'rotate-90' : ''}`}>
            ▸
          </span>
          Advanced specificity options
        </button>
        <Reveal show={showSpecificity}>
          <div className="space-y-2 pl-3 border-l-2 border-teal-100 mt-1">
            {[
              {
                key: 'enableFamilyDiscrimination',
                label: 'Penalize off-target in same miRNA family',
                tooltip: 'The algorithm penalizes candidates whose 6 nt overhang could cross-react with a family member. Especially important for the let-7 family.',
              },
              {
                key: 'enablePrecursorCheck',
                label: 'Check cross-reactivity with pre-miRNA',
                tooltip: 'Enable only when high pre-miRNA levels are expected. Steric hindrance normally prevents stem-loop primers from binding pre-miRNA.',
              },
              {
                key: 'enableRefoldingProtocol',
                label: 'Generate re-folding protocol in output',
                tooltip: 'Adds a thermal re-folding step to the output: 95°C 10 min → slow cool → hold 60°C.',
              },
            ].map(({ key, label, tooltip }) => (
              <label key={key} className="flex items-start gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={data[key]}
                  onChange={(e) => onChange(key, e.target.checked)}
                  className="mt-0.5 accent-teal-600"
                />
                <span className="text-sm text-gray-700 flex-1">{label}</span>
                <Tooltip text={tooltip} />
              </label>
            ))}
          </div>
        </Reveal>
      </div>
    </CollapsibleSection>
  );
}
