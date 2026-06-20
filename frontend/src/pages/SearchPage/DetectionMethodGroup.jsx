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

// Reusable animated reveal: expands to true content height (no magic max-h numbers).
// Same grid-rows technique used by CollapsibleSection.
function Reveal({ show, children }) {
  return (
    <div
      className={`grid transition-[grid-template-rows] duration-300 ease-in-out ${
        show ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
      }`}
    >
      <div className="overflow-hidden">{children}</div>
    </div>
  );
}

export default function DetectionMethodGroup({ data, onChange, seqAnalysis, onFirstOpen, openRequested }) {
  const [showSpecificity, setShowSpecificity] = useState(false);

  const isCustomRef = data.referenceGene === 'custom';

  return (
    <CollapsibleSection
      title="Detection Method"
      tooltip="Determines the primer design algorithm and output format. TaqMan requires a probe; SYBR Green requires melting curve analysis. This selection directly affects weeks 2–3 design logic."
      accent="purple"
      defaultOpen
      onFirstOpen={onFirstOpen}
      openRequested={openRequested}
    >
      {/* Non-canonical 5' end warning */}
      {seqAnalysis && !seqAnalysis.startsWithU && (
        <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
          ⚠ <strong>Non-canonical 5′ end:</strong> This miRNA does not start with U. Most mature miRNAs start with U for preferential loading into the Ago2 complex. Detection efficiency may be lower than expected — consider increasing RNA input amount.
        </div>
      )}

      {/* Signal detection */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-gray-700">Signal detection</label>
        <div className="flex gap-4">
          {[
            { value: 'taqman', label: 'TaqMan probe' },
            { value: 'sybr',   label: 'SYBR Green' },
          ].map(({ value, label }) => (
            <label key={value} className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="radio"
                name="signalMethod"
                value={value}
                checked={data.signalMethod === value}
                onChange={() => onChange('signalMethod', value)}
                className="accent-teal-600"
              />
              <span className="text-sm text-gray-700">{label}</span>
            </label>
          ))}
        </div>

        <Reveal show={data.signalMethod === 'taqman'}>
          <div className="text-xs text-teal-700 bg-teal-50 border border-teal-200 rounded-lg px-3 py-2 leading-relaxed pt-0.5">
            <strong>TaqMan mode:</strong> The algorithm will design a probe binding site at the miRNA–stem-loop junction. The probe requires a Minor Groove Binder (MGB) group to achieve Tm ≥ 70°C on a short 12–17 nt sequence.
          </div>
        </Reveal>

        <Reveal show={data.signalMethod === 'sybr'}>
          <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed pt-0.5">
            <strong>SYBR Green mode:</strong> No probe will be designed. Amplicon size is constrained to ≤ 120 bp to minimize primer dimers. Melting curve analysis is mandatory after every run to confirm product specificity.
          </div>
        </Reveal>
      </div>

      {/* Quantification mode */}
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

        <Reveal show={data.quantMode === 'absolute'}>
          <div className="text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 leading-relaxed pt-0.5">
            <strong>Absolute quantification:</strong> The output will include a recommendation for a standard curve covering 10²–10⁹ copies/µl using a recombinant plasmid as the calibration standard.
          </div>
        </Reveal>

        <Reveal show={data.quantMode === 'relative'}>
          <div className="space-y-2 pt-0.5">
            <div className="flex items-center gap-1.5">
              <label className="text-sm font-medium text-gray-700">Reference gene</label>
              <Tooltip text="Housekeeping reference used to normalize RNA input across samples. miR-16 is stable in most tissues. Use cel-miR-39 (spike-in) for serum or plasma where endogenous reference genes are unreliable." />
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
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-teal-300 focus:ring-1 focus:ring-teal-100 mt-0.5"
              />
            </Reveal>
          </div>
        </Reveal>
      </div>

      {/* Advanced specificity options */}
      <div className="space-y-2">
        <button
          type="button"
          onClick={() => setShowSpecificity((v) => !v)}
          className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-teal-700 transition-colors"
        >
          <span
            className={`text-teal-600 font-bold text-sm leading-none transition-transform duration-200 ${
              showSpecificity ? 'rotate-90' : ''
            }`}
          >
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
                tooltip: 'When enabled: the algorithm penalizes any primer candidate whose 6 nt overhang could cross-react with a related family member. Especially important for the let-7 family (13 members, many differing by only 1–2 nt).',
              },
              {
                key: 'enablePrecursorCheck',
                label: 'Check cross-reactivity with pre-miRNA',
                tooltip: 'Normally, steric hindrance of the stem-loop structure prevents binding to pre-miRNA. Enable only when there is specific reason to expect high pre-miRNA levels.',
              },
              {
                key: 'enableRefoldingProtocol',
                label: 'Generate re-folding protocol in output',
                tooltip: 'When enabled: the output will include a thermal re-folding protocol to ensure the stem-loop primer adopts the correct hairpin conformation: 95°C 10 min → slow cool → hold at 60°C.',
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
