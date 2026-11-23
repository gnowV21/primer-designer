import Tooltip from '../../components/ui/Tooltip.jsx';
import CollapsibleSection from '../../components/ui/CollapsibleSection.jsx';
import { sameReference } from '../../utils/paramChecks.js';

// Neutral descriptions (UI review 2026-11-23): no stability claims; validate the
// reference in your own samples.
const REFERENCE_GENE_OPTIONS = [
  { value: 'miR-16',    label: 'miR-16',    desc: 'hsa-miR-16-5p; affected by hemolysis in serum and plasma' },
  { value: 'U6',        label: 'U6 snRNA',  desc: 'small nuclear RNA' },
  { value: 'RNU48',     label: 'RNU48',     desc: 'small nucleolar RNA' },
  { value: 'cel-miR-39',label: 'cel-miR-39',desc: 'C. elegans spike-in for serum and plasma' },
  { value: 'custom',    label: 'Custom',    desc: 'enter a miRBase name' },
];

function Reveal({ show, children }) {
  return (
    <div className={`grid transition-[grid-template-rows] duration-300 ease-in-out ${show ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}>
      <div className="overflow-hidden">{children}</div>
    </div>
  );
}

export default function DetectionMethodGroup({ data, onChange, seqAnalysis, targetName = '', onFirstOpen, openRequested }) {
  const isCustomRef = data.referenceGene === 'custom';
  const refName = isCustomRef ? data.customReferenceGene : data.referenceGene;
  const refIsTarget = data.quantMode === 'relative' && sameReference(targetName, refName);
  const isTaqMan = data.signalMethod === 'taqman';
  const isSYBR   = data.signalMethod === 'sybr';

  return (
    <CollapsibleSection
      title="Detection method"
      tooltip="Choose TaqMan (hydrolysis probe) or SYBR Green (intercalating dye). This controls which primers and outputs are generated."
      accent="purple"
      onFirstOpen={onFirstOpen}
      openRequested={openRequested}
    >
      {/* Non-canonical 5′ end warning */}
      {seqAnalysis && !seqAnalysis.startsWithU && (
        <div className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
          <strong>Non-canonical 5′ end:</strong> this miRNA does not start with U, so detection efficiency may be lower. Consider increasing the RNA input.
        </div>
      )}

      {/* ── Signal detection — card picker ── */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-700">Signal detection</label>
        {/* One "selected" style for every choice control; the cards stack on phones. */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" role="radiogroup" aria-label="Signal detection">
          {[
            { key: 'taqman', title: 'TaqMan probe', text: 'Hydrolysis probe, high specificity; the probe is designed automatically.', on: isTaqMan },
            { key: 'sybr', title: 'SYBR Green', text: 'Intercalating dye, no probe.', on: isSYBR },
          ].map(({ key, title, text, on }) => (
          <button
              key={key}
            type="button"
              role="radio"
              aria-checked={on}
              onClick={() => onChange('signalMethod', key)}
              className={`text-left rounded-xl border-2 px-4 py-3 transition-all duration-150 active:scale-[0.98] ${on
                ? 'border-teal-600 bg-teal-50'
                : 'border-slate-200 bg-white hover:border-teal-300'}`}
          >
              <span className={`block text-sm font-semibold mb-1 ${on ? 'text-teal-800' : 'text-slate-800'}`}>{title}</span>
              <span className="block text-xs leading-snug text-slate-700">{text}</span>
          </button>
          ))}
        </div>

        {/* SYBR mandatory note */}
        <Reveal show={isSYBR}>
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5 mt-0.5">
            SYBR Green needs a melting curve after every run to confirm a single product.
          </p>
        </Reveal>
      </div>

      {/* ── Quantification mode ── */}
      <div className="space-y-2">
        <div className="flex items-center gap-1.5">
          <label className="text-sm font-medium text-slate-700">Quantification mode</label>
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
              <span className="text-sm text-slate-700">{label}</span>
            </label>
          ))}
        </div>

        <Reveal show={data.quantMode === 'relative'}>
          <div className="space-y-1.5 pt-0.5">
            <div className="flex items-center gap-1.5">
              <label htmlFor="det-reference-gene" className="text-sm font-medium text-slate-700">Reference gene</label>
              <Tooltip text="Reference used to normalize the RNA input across samples. Validate its stability in your own samples; a spike-in such as cel-miR-39 suits serum and plasma." />
            </div>
            <select
              id="det-reference-gene"
              value={data.referenceGene}
              onChange={(e) => onChange('referenceGene', e.target.value)}
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 text-slate-900 focus:outline-none focus:border-teal-300 focus:ring-1 focus:ring-teal-100 bg-white"
            >
              {REFERENCE_GENE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}: {opt.desc}
                </option>
              ))}
            </select>
            <Reveal show={isCustomRef}>
              <input
                type="text"
                value={data.customReferenceGene}
                onChange={(e) => onChange('customReferenceGene', e.target.value)}
                placeholder="For example hsa-miR-103a-3p"
                aria-label="Custom reference gene"
                className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 text-slate-900 placeholder-slate-500 focus:outline-none focus:border-teal-300 focus:ring-1 focus:ring-teal-100"
              />
            </Reveal>
            {refIsTarget && (
              <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2" data-testid="reference-is-target">
                The reference ({refName}) is the target miRNA itself. Choose a different reference gene.
              </p>
            )}
          </div>
        </Reveal>
      </div>

      {/* Re-folding step: one checkbox with its help next to it (no "Advanced options" level). */}
      <label className="flex items-start gap-2 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={data.enableRefoldingProtocol}
          onChange={(e) => onChange('enableRefoldingProtocol', e.target.checked)}
          className="mt-1 accent-teal-600"
        />
        <span className="text-sm text-slate-800">
          Add a re-folding step to the protocol
          <span className="block text-xs text-slate-600">95 °C for 10 min, slow cool, hold at 60 °C (refolds the RT primer before RT).</span>
        </span>
      </label>
      {/* Audit SCI-09: say what is not computed instead of offering a switch that does nothing. */}
      <p className="text-xs text-slate-600 leading-relaxed">
        Mature vs pre-miRNA discrimination is not computed: run a pre-miRNA or no-RT control if
        precursor levels may be high.
      </p>
    </CollapsibleSection>
  );
}
