import RangeSlider from '../../components/ui/RangeSlider.jsx';
import NumInput from '../../components/ui/NumInput.jsx';
import Tooltip from '../../components/ui/Tooltip.jsx';
import CollapsibleSection from '../../components/ui/CollapsibleSection.jsx';
import { LIMITS } from '../../constants/defaults.js';

export default function QpcrConditionsGroup({ data, errors, onChange, onError, tmMin, onFirstOpen, openRequested }) {
  function handleTaChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    if (str === '' || isNaN(val)) { onError('annealingTemp', `Annealing temperature must be between ${LIMITS.qpcr.taMin} and ${LIMITS.qpcr.taMax}°C.`); return; }
    onError('annealingTemp', val < LIMITS.qpcr.taMin || val > LIMITS.qpcr.taMax ? `Annealing temperature must be between ${LIMITS.qpcr.taMin} and ${LIMITS.qpcr.taMax}°C.` : '');
    onChange('annealingTemp', val);
  }

  function handleCyclesChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    if (str === '' || isNaN(val)) { onError('totalCycles', `Total cycles must be between ${LIMITS.qpcr.cyclesMin} and ${LIMITS.qpcr.cyclesMax}.`); return; }
    onError('totalCycles', val < LIMITS.qpcr.cyclesMin || val > LIMITS.qpcr.cyclesMax ? `Total cycles must be between ${LIMITS.qpcr.cyclesMin} and ${LIMITS.qpcr.cyclesMax}.` : '');
    onChange('totalCycles', val);
  }

  function handleEffMinChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    if (str === '' || isNaN(val)) { onError('pcrEfficiencyMin', `Min efficiency must be between ${LIMITS.qpcr.efficiencyMin} and 100%.`); return; }
    if (val < LIMITS.qpcr.efficiencyMin || val > 100) {
      onError('pcrEfficiencyMin', `Min efficiency must be between ${LIMITS.qpcr.efficiencyMin} and 100%.`);
    } else if (val >= data.pcrEfficiencyMax) {
      onError('pcrEfficiencyMin', `Min must be less than max (${data.pcrEfficiencyMax}%).`);
    } else {
      onError('pcrEfficiencyMin', '');
    }
    onChange('pcrEfficiencyMin', val);
  }

  function handleEffMaxChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    if (str === '' || isNaN(val)) { onError('pcrEfficiencyMax', `Max efficiency must be between 100 and ${LIMITS.qpcr.efficiencyMax}%.`); return; }
    if (val < 100 || val > LIMITS.qpcr.efficiencyMax) {
      onError('pcrEfficiencyMax', `Max efficiency must be between 100 and ${LIMITS.qpcr.efficiencyMax}%.`);
    } else if (val <= data.pcrEfficiencyMin) {
      onError('pcrEfficiencyMax', `Max must be greater than min (${data.pcrEfficiencyMin}%).`);
    } else {
      onError('pcrEfficiencyMax', '');
    }
    onChange('pcrEfficiencyMax', val);
  }

  const showTaWarning = !errors.annealingTemp && data.annealingTemp > tmMin + 5;

  const cycles = data.totalCycles;
  const cyclesWarning =
    !errors.totalCycles && cycles >= LIMITS.qpcr.cyclesMin && cycles <= LIMITS.qpcr.cyclesMax
      ? cycles < 35
        ? '⚠ Fewer than 35 cycles may be insufficient to detect low-abundance targets.'
        : cycles > 45
          ? '⚠ Too many cycles increases the risk of non-specific amplification.'
          : ''
      : '';

  const effRange = data.pcrEfficiencyMax - data.pcrEfficiencyMin;
  const showEffRangeWarning =
    !errors.pcrEfficiencyMin && !errors.pcrEfficiencyMax && effRange > 25;

  const hasError = !!(errors.annealingTemp || errors.totalCycles || errors.pcrEfficiencyMin || errors.pcrEfficiencyMax);
  const hasWarning = showTaWarning || !!cyclesWarning || showEffRangeWarning;

  return (
    <CollapsibleSection
      title="qPCR Conditions"
      tooltip="qPCR reaction conditions: annealing temperature, cycle number, efficiency range, and expected amplicon size."
      hasError={hasError}
      hasWarning={hasWarning}
      onFirstOpen={onFirstOpen}
      openRequested={openRequested}
    >
      {/* Row 1: Ta · Cycles · Efficiency range */}
      <div className="grid grid-cols-3 gap-4">
        {/* Annealing temperature */}
        <div className="space-y-1">
          <NumInput
            id="qpcr-ta"
            label="Annealing temp (Ta)"
            tooltip="Annealing temperature in the PCR cycle. Typically Tm - 2 to 5°C. With Tm = 60°C, Ta = 58–60°C gives good results."
            value={data.annealingTemp}
            onChange={handleTaChange}
            min={LIMITS.qpcr.taMin}
            max={LIMITS.qpcr.taMax}
            step={1}
            unit="°C"
            error={errors.annealingTemp}
          />
          {showTaWarning && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">⚠ Ta should be 2–5°C below Tm to avoid mispriming.</p>
          )}
        </div>

        {/* Total cycles */}
        <div className="space-y-1">
          <NumInput
            id="qpcr-cycles"
            label="Total cycles"
            tooltip="Number of thermal cycles in the qPCR reaction. Ct values within 5 cycles of the total are generally unreliable."
            value={data.totalCycles}
            onChange={handleCyclesChange}
            min={LIMITS.qpcr.cyclesMin}
            max={LIMITS.qpcr.cyclesMax}
            step={1}
            unit="cycles"
            error={errors.totalCycles}
          />
          {cyclesWarning && <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">{cyclesWarning}</p>}
        </div>

        {/* PCR efficiency range */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5">
            <label className="text-sm font-medium text-gray-700">PCR efficiency (%)</label>
            <Tooltip text="Ideal efficiency = 100% (slope −3.32). The algorithm will prioritize primers with predicted efficiency within this range." />
          </div>
          <div className="flex items-center gap-1.5">
            <div className="flex-1">
              <NumInput
                id="qpcr-eff-min"
                value={data.pcrEfficiencyMin}
                onChange={handleEffMinChange}
                min={LIMITS.qpcr.efficiencyMin}
                max={100}
                step={1}
                error={errors.pcrEfficiencyMin}
              />
            </div>
            <span className="text-xs text-gray-400 shrink-0 self-start mt-2">→</span>
            <div className="flex-1">
              <NumInput
                id="qpcr-eff-max"
                value={data.pcrEfficiencyMax}
                onChange={handleEffMaxChange}
                min={100}
                max={LIMITS.qpcr.efficiencyMax}
                step={1}
                unit="%"
                error={errors.pcrEfficiencyMax}
              />
            </div>
          </div>
          {showEffRangeWarning && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">⚠ A wide efficiency range will accept more low-quality primer candidates.</p>
          )}
        </div>
      </div>

      {/* Row 2: Amplicon size */}
      <RangeSlider
        label="Amplicon size"
        min={LIMITS.qpcr.ampliconMin}
        max={LIMITS.qpcr.ampliconMax}
        valueMin={data.ampliconMin}
        valueMax={data.ampliconMax}
        step={5}
        unit=" bp"
        onChange={(newMin, newMax) => {
          onChange('ampliconMin', newMin);
          onChange('ampliconMax', newMax);
        }}
        tooltip="Expected PCR product size. For stem-loop RT-qPCR, 60–150 bp is typical due to the extended cDNA template."
      />
    </CollapsibleSection>
  );
}
