// RequiredGroup — Parameters that set a hard limit in the tiered engine (2026-11-22):
// the forward-primer Tm window, the amplicon window and the RT overhang (assay
// structure). Candidates outside these are not generated. Field names and defaults are
// unchanged (constants/defaults.js); only the grouping on screen is new.
import RangeSlider from '../../components/ui/RangeSlider.jsx';
import Tooltip from '../../components/ui/Tooltip.jsx';
import CollapsibleSection from '../../components/ui/CollapsibleSection.jsx';
import { LIMITS } from '../../constants/defaults.js';
import { WarnBox } from './paramUi.jsx';

// Family-specific suggestion: which overhangs benefit from 7 nt for discrimination
function getFamilyHint(mirnaFamily) {
  const fam = (mirnaFamily || '').toLowerCase();
  if (fam.includes('let-7') || fam.includes('let7')) {
    return { text: `let-7 family has 13 members with nearly identical 3′ sequences — 7 nt may help discriminate between family members.`, suggestNt: 7 };
  }
  if (fam.includes('mir-17') || fam.includes('mir17')) {
    return { text: `miR-17 family members share highly conserved seed and 3′ sequences — 7 nt may improve specificity.`, suggestNt: 7 };
  }
  if (fam.includes('mir-29') || fam.includes('mir29') || fam.includes('mir-30') || fam.includes('mir30')) {
    return { text: `${mirnaFamily} family has multiple members with similar 3′ ends — 7 nt may reduce cross-reactivity risk.`, suggestNt: 7 };
  }
  return null;
}

const OFF_LABEL_WARNINGS = {
  5: 'Off-label — not experimentally validated. Chen et al. 2005 only tested 6 nt. A 5-nt overhang reduces specificity against related family members and may lower RT efficiency. Use only if you have evidence that a shorter overlap is required for your specific template.',
  7: 'Off-label — not experimentally validated. Chen et al. 2005 only tested 6 nt. A 7-nt overhang may improve discrimination in large miRNA families (e.g. let-7), but no published data exists confirming RT efficiency or sensitivity at 7 nt for stem-loop RT-qPCR.',
};

export default function RequiredGroup({
  constraints, onConstraintChange, thermoData, onThermoChange, qpcrData, onQpcrChange,
  seqAnalysis, mirnaFamily, onFirstOpen, openRequested,
}) {
  const familyHint = getFamilyHint(mirnaFamily);
  const offLabelWarn = OFF_LABEL_WARNINGS[constraints.bindingRegion3prime] ?? null;
  const fwdTmDeficit = seqAnalysis ? thermoData.tmMin - seqAnalysis.fwdRegionTm : 0;
  const showFwdTmWarn = seqAnalysis && fwdTmDeficit > 33;

  return (
    <CollapsibleSection
      title="Required"
      tooltip="Hard limits: a forward primer outside these is not generated. Specificity (S1–S3) is the other Required part; it is computed, not set here."
      hasWarning={!!showFwdTmWarn}
      onFirstOpen={onFirstOpen}
      openRequested={openRequested}
    >
      <RangeSlider
        label="Forward-primer Tm window"
        min={LIMITS.thermodynamic.tmMin}
        max={LIMITS.thermodynamic.tmMax}
        valueMin={thermoData.tmMin}
        valueMax={thermoData.tmMax}
        step={1}
        unit="°C"
        onChange={(lo, hi) => { onThermoChange('tmMin', lo); onThermoChange('tmMax', hi); }}
        tooltip="Hard limit: forward primers with a Tm outside this window are not generated. 58–62 °C is the default (Ta 60 °C ± 2). The window does not follow Ta; set both."
      />
      {showFwdTmWarn && (
        <WarnBox text={`Tm target may be difficult to achieve: the 12-nt miRNA binding region contributes only ~${seqAnalysis.fwdRegionTm}°C. Reaching ${thermoData.tmMin}°C requires the 5′ tail to add ~${fwdTmDeficit}°C. Consider lowering Tm min to ${thermoData.tmMin - 5}–${thermoData.tmMin - 3}°C.`} />
      )}

      <RangeSlider
        label="Amplicon size"
        min={LIMITS.qpcr.ampliconMin}
        max={LIMITS.qpcr.ampliconMax}
        valueMin={qpcrData.ampliconMin}
        valueMax={qpcrData.ampliconMax}
        step={5}
        unit=" bp"
        onChange={(newMin, newMax) => {
          onQpcrChange('ampliconMin', newMin);
          onQpcrChange('ampliconMax', newMax);
        }}
        tooltip="Hard limit on the PCR product size. In stem-loop RT-qPCR the amplicon is 5′ tail + miRNA + 37 nt of the RT body (about 57–77 bp), so the lower limit is the one that usually matters."
      />

      {/* 3′ Binding region — selectable 5 / 6 / 7 nt */}
      <div className="space-y-1.5">
        <div className="flex items-center gap-1.5">
          <label className="text-sm font-medium text-slate-700">3′ Binding region (RT overhang)</label>
          <Tooltip text="Number of nucleotides at the 3′ overhang of the stem-loop RT primer that base-pair with the 3′ end of the mature miRNA. 6 nt is the validated standard (Chen et al. 2005). Use 7 nt for large miRNA families with highly similar 3′ sequences. Part of the assay structure; it also changes the specificity screen." />
        </div>
        <div className="flex gap-1.5 max-w-xs">
          {[5, 6, 7].map((nt) => (
            <button
              key={nt}
              type="button"
              onClick={() => onConstraintChange('bindingRegion3prime', nt)}
              className={`flex-1 py-1.5 rounded-lg text-sm font-semibold border transition-all duration-150 active:scale-95 ${
                constraints.bindingRegion3prime === nt
                  ? 'bg-teal-600 text-white border-teal-600 shadow-sm'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-teal-300 hover:text-teal-700'
              }`}
            >
              {nt} nt
            </button>
          ))}
        </div>
        {/* Off-label note — shown whenever binding length ≠ 6 nt */}
        {offLabelWarn && (
          <p className="text-xs text-amber-800 leading-snug">
            <strong>Off-label ({constraints.bindingRegion3prime} nt)</strong> — not validated by Chen 2005.{' '}
            <button
              type="button"
              onClick={() => onConstraintChange('bindingRegion3prime', 6)}
              className="underline hover:no-underline font-medium"
            >
              Revert to 6 nt
            </button>
          </p>
        )}
        {/* Family-specific suggestion (informational, not a blocker) */}
        {familyHint && constraints.bindingRegion3prime !== familyHint.suggestNt && (
          <p className="text-xs leading-relaxed rounded-lg px-2.5 py-1.5 text-teal-700 bg-teal-50 border border-teal-100">
            {familyHint.text}
            <button
              type="button"
              onClick={() => onConstraintChange('bindingRegion3prime', familyHint.suggestNt)}
              className="ml-1.5 underline font-medium hover:no-underline"
            >
              Use {familyHint.suggestNt} nt
            </button>
          </p>
        )}
      </div>
    </CollapsibleSection>
  );
}
