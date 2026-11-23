// AssaySetupGroup — Parameters the tiered ranking does not use (2026-11-22): cycle number
// and the efficiency acceptance range. The primer-length control was removed (UI review
// 2026-11-23): the engine always uses 18–27 nt, so it changed nothing; lengthMin/lengthMax
// stay in the form state and the request body at their defaults. They are recorded in the MIQE export. Detection and
// experimental context keep their own sections below this one. Field names and defaults
// are unchanged (constants/defaults.js).
import NumInput from '../../components/ui/NumInput.jsx';
import Tooltip from '../../components/ui/Tooltip.jsx';
import CollapsibleSection from '../../components/ui/CollapsibleSection.jsx';
import { LIMITS } from '../../constants/defaults.js';
import { WarnBox } from './paramUi.jsx';

export default function AssaySetupGroup({
  qpcrData, errors, onQpcrChange, onError, onFirstOpen, openRequested,
}) {
  function handleCyclesChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    const msg = `Total cycles must be between ${LIMITS.qpcr.cyclesMin} and ${LIMITS.qpcr.cyclesMax}.`;
    if (str === '' || isNaN(val)) { onError('totalCycles', msg); return; }
    onError('totalCycles', val < LIMITS.qpcr.cyclesMin || val > LIMITS.qpcr.cyclesMax ? msg : '');
    onQpcrChange('totalCycles', val);
  }

  function handleEffMinChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    if (str === '' || isNaN(val)) { onError('pcrEfficiencyMin', `Min efficiency must be between ${LIMITS.qpcr.efficiencyMin} and 100%.`); return; }
    if (val < LIMITS.qpcr.efficiencyMin || val > 100) {
      onError('pcrEfficiencyMin', `Min efficiency must be between ${LIMITS.qpcr.efficiencyMin} and 100%.`);
    } else if (val >= qpcrData.pcrEfficiencyMax) {
      onError('pcrEfficiencyMin', `Min must be less than max (${qpcrData.pcrEfficiencyMax}%).`);
    } else {
      onError('pcrEfficiencyMin', '');
    }
    onQpcrChange('pcrEfficiencyMin', val);
  }

  function handleEffMaxChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    if (str === '' || isNaN(val)) { onError('pcrEfficiencyMax', `Max efficiency must be between 100 and ${LIMITS.qpcr.efficiencyMax}%.`); return; }
    if (val < 100 || val > LIMITS.qpcr.efficiencyMax) {
      onError('pcrEfficiencyMax', `Max efficiency must be between 100 and ${LIMITS.qpcr.efficiencyMax}%.`);
    } else if (val <= qpcrData.pcrEfficiencyMin) {
      onError('pcrEfficiencyMax', `Max must be greater than min (${qpcrData.pcrEfficiencyMin}%).`);
    } else {
      onError('pcrEfficiencyMax', '');
    }
    onQpcrChange('pcrEfficiencyMax', val);
  }

  const cycles = qpcrData.totalCycles;
  const cyclesWarning =
    !errors.totalCycles && cycles >= LIMITS.qpcr.cyclesMin && cycles <= LIMITS.qpcr.cyclesMax
      ? cycles < 35
        ? 'Fewer than 35 cycles may be insufficient to detect low-abundance targets.'
        : cycles > 45
          ? 'Too many cycles increases the risk of non-specific amplification.'
          : ''
      : '';
  const effRange = qpcrData.pcrEfficiencyMax - qpcrData.pcrEfficiencyMin;
  const showEffRangeWarning = !errors.pcrEfficiencyMin && !errors.pcrEfficiencyMax && effRange > 25;

  const hasError = !!(errors.totalCycles || errors.pcrEfficiencyMin || errors.pcrEfficiencyMax);
  const hasWarning = !!cyclesWarning || showEffRangeWarning;

  return (
    <CollapsibleSection
      title="Assay setup"
      tooltip="Planned-assay settings that the ranking does not use; recorded in the MIQE export. Detection method and experimental context follow."
      hasError={hasError}
      hasWarning={hasWarning}
      onFirstOpen={onFirstOpen}
      openRequested={openRequested}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1">
          <NumInput
            id="qpcr-cycles"
            label="Total cycles"
            hint="Reported in the MIQE export."
            value={qpcrData.totalCycles}
            onChange={handleCyclesChange}
            min={LIMITS.qpcr.cyclesMin}
            max={LIMITS.qpcr.cyclesMax}
            step={1}
            unit="cycles"
            error={errors.totalCycles}
          />
          {cyclesWarning && <WarnBox text={cyclesWarning} />}
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-1.5">
            <label className="text-sm font-medium text-slate-700">PCR efficiency (%)</label>
            <Tooltip text="Ideal efficiency = 100% (slope −3.32). Your acceptance range for the standard curve: reported in the MIQE export, not used by the ranking." />
          </div>
          <div className="flex items-center gap-1.5">
            <div className="flex-1">
              <NumInput
                id="qpcr-eff-min"
                ariaLabel="Minimum PCR efficiency, %"
                value={qpcrData.pcrEfficiencyMin}
                onChange={handleEffMinChange}
                min={LIMITS.qpcr.efficiencyMin}
                max={100}
                step={1}
                error={errors.pcrEfficiencyMin}
              />
            </div>
            <span className="text-xs text-slate-700 shrink-0 self-start mt-2.5">to</span>
            <div className="flex-1">
              <NumInput
                id="qpcr-eff-max"
                ariaLabel="Maximum PCR efficiency, %"
                value={qpcrData.pcrEfficiencyMax}
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
            <WarnBox text="A wide efficiency range accepts a wider spread of measured efficiencies in your validation." />
          )}
        </div>
      </div>
    </CollapsibleSection>
  );
}
