import RangeSlider from '../../components/ui/RangeSlider.jsx';
import Toggle from '../../components/ui/Toggle.jsx';
import Tooltip from '../../components/ui/Tooltip.jsx';
import CollapsibleSection from '../../components/ui/CollapsibleSection.jsx';
import { LIMITS } from '../../constants/defaults.js';

export default function PrimerConstraintsGroup({ data, onChange, seqAnalysis, onFirstOpen, openRequested }) {
  const hasWarning = !!(seqAnalysis?.hasContinuousRepeat || (seqAnalysis && (seqAnalysis.fwdRegionGC < 30 || seqAnalysis.fwdRegionGC > 70)));

  return (
    <CollapsibleSection
      title="Primer Design Constraints"
      tooltip="Primer design constraints: GC content, length, and 3′ end properties."
      hasError={false}
      hasWarning={hasWarning}
      onFirstOpen={onFirstOpen}
      openRequested={openRequested}
    >
      {/* GC content RangeSlider */}
      <RangeSlider
        label="GC content (%)"
        min={LIMITS.primerConstraints.gcMin}
        max={LIMITS.primerConstraints.gcMax}
        valueMin={data.gcMin}
        valueMax={data.gcMax}
        step={1}
        unit="%"
        onChange={(newMin, newMax) => {
          onChange('gcMin', newMin);
          onChange('gcMax', newMax);
        }}
        tooltip="Below 35%: weak primer-template binding. Above 65%: risk of undesired secondary structures. 40–60% is optimal for stem-loop RT-qPCR."
      />

      {/* Primer length RangeSlider */}
      <RangeSlider
        label="Primer length (nt)"
        min={LIMITS.primerConstraints.lengthMin}
        max={LIMITS.primerConstraints.lengthMax}
        valueMin={data.lengthMin}
        valueMax={data.lengthMax}
        step={1}
        unit=" nt"
        onChange={(newMin, newMax) => {
          onChange('lengthMin', newMin);
          onChange('lengthMax', newMax);
        }}
        tooltip="Total forward primer length. Typically 22–24 nt (miRNA-specific region + 5′ tail). The stem-loop body (~44–57 nt) is not counted here."
      />

      {/* GC Clamp + Binding region */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-1.5">
            <label className="text-sm font-medium text-gray-700">3′ GC Clamp</label>
            <Tooltip text="End the primer with a G or C at the 3′ terminus. Increases binding stability and prevents 3′ end 'breathing'. Recommended ON in most cases." />
          </div>
          <Toggle
            checked={data.gcClamp3prime}
            onChange={(val) => onChange('gcClamp3prime', val)}
            label
          />
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-1.5">
            <label className="text-sm font-medium text-gray-700">3′ Binding region</label>
            <Tooltip text="Number of nucleotides at the 3′ overhang of the stem-loop RT primer that base-pair with the 3′ end of the mature miRNA. Fixed at 6 nt — the validated standard for steric hindrance against pri/pre-miRNA precursors." />
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-50 border border-gray-200">
            <span className="text-sm font-semibold text-gray-700 tabular-nums">6 nt</span>
            <span className="text-xs text-gray-400">(fixed)</span>
          </div>
          {seqAnalysis && !seqAnalysis.fwdEndGC && data.gcClamp3prime && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
              ⚠ Position 10–12 of the miRNA ends with A/U. The algorithm will adjust the 5′ tail of the forward primer to ensure a GC clamp.
            </p>
          )}
        </div>
      </div>

      {seqAnalysis?.hasContinuousRepeat && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
          ⚠ Sequence contains a homopolymer run (≥ 4 identical nt). This region in a primer can cause polymerase slippage or synthesis failure — the algorithm will deprioritize it.
        </p>
      )}
      {seqAnalysis && seqAnalysis.fwdRegionGC < 30 && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
          ⚠ <strong>AU-rich forward binding region ({seqAnalysis.fwdRegionGC}% GC):</strong> The 5′-most 12 nt are heavily AU — the forward primer will require a long 5′ tail to reach the Tm target. Consider lowering the Tm minimum in the Thermodynamic Parameters section.
        </p>
      )}
      {seqAnalysis && seqAnalysis.fwdRegionGC > 70 && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
          ⚠ <strong>GC-rich forward binding region ({seqAnalysis.fwdRegionGC}% GC):</strong> The 5′-most 12 nt are GC-heavy — increased risk of self-complementarity and hairpin formation. Enable precursor check in the Detection Method section.
        </p>
      )}
    </CollapsibleSection>
  );
}
