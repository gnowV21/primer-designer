import { useState, useRef } from 'react';
import RangeSlider from '../../components/ui/RangeSlider.jsx';
import NumInput from '../../components/ui/NumInput.jsx';
import CollapsibleSection from '../../components/ui/CollapsibleSection.jsx';
import { DEFAULTS, LIMITS } from '../../constants/defaults.js';

function WarnBox({ text }) {
  return (
    <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
      ⚠ {text}
    </p>
  );
}

export default function ThermodynamicGroup({
  data, errors, onChange, onError, seqAnalysis, onFirstOpen, openRequested = 0,
}) {
  const [confirmingReset, setConfirmingReset] = useState(false);
  const resetTimerRef = useRef(null);

  function handleResetClick() {
    if (confirmingReset) {
      clearTimeout(resetTimerRef.current);
      setConfirmingReset(false);
      handleReset();
    } else {
      setConfirmingReset(true);
      resetTimerRef.current = setTimeout(() => setConfirmingReset(false), 2500);
    }
  }
  function handleSaltChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    if (str === '' || isNaN(val)) { onError('saltConcentration', `[Na⁺] must be between ${LIMITS.thermodynamic.saltMin} and ${LIMITS.thermodynamic.saltMax} mM.`); return; }
    onError('saltConcentration', val < LIMITS.thermodynamic.saltMin || val > LIMITS.thermodynamic.saltMax ? `[Na⁺] must be between ${LIMITS.thermodynamic.saltMin} and ${LIMITS.thermodynamic.saltMax} mM.` : '');
    onChange('saltConcentration', val);
  }

  function handlePrimerConcChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    if (str === '' || isNaN(val)) { onError('primerConcentration', `Primer concentration must be between ${LIMITS.thermodynamic.primerConcMin} and ${LIMITS.thermodynamic.primerConcMax} nM.`); return; }
    onError('primerConcentration', val < LIMITS.thermodynamic.primerConcMin || val > LIMITS.thermodynamic.primerConcMax ? `Primer concentration must be between ${LIMITS.thermodynamic.primerConcMin} and ${LIMITS.thermodynamic.primerConcMax} nM.` : '');
    onChange('primerConcentration', val);
  }

  function handleMgChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    if (str === '' || isNaN(val)) { onError('magnesiumConcentration', `[Mg²⁺] must be between ${LIMITS.thermodynamic.mgMin} and ${LIMITS.thermodynamic.mgMax} mM.`); return; }
    onError('magnesiumConcentration', val < LIMITS.thermodynamic.mgMin || val > LIMITS.thermodynamic.mgMax ? `[Mg²⁺] must be between ${LIMITS.thermodynamic.mgMin} and ${LIMITS.thermodynamic.mgMax} mM.` : '');
    onChange('magnesiumConcentration', val);
  }

  function handleDntpChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    if (str === '' || isNaN(val)) { onError('dntpTotal', `[dNTP] must be between ${LIMITS.thermodynamic.dntpMin} and ${LIMITS.thermodynamic.dntpMax} mM.`); return; }
    onError('dntpTotal', val < LIMITS.thermodynamic.dntpMin || val > LIMITS.thermodynamic.dntpMax ? `[dNTP] must be between ${LIMITS.thermodynamic.dntpMin} and ${LIMITS.thermodynamic.dntpMax} mM.` : '');
    onChange('dntpTotal', val);
  }

  function handleKPlusChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    if (str === '' || isNaN(val)) { onError('kPlusConc', `[K⁺] must be between ${LIMITS.thermodynamic.kPlusMin} and ${LIMITS.thermodynamic.kPlusMax} mM.`); return; }
    onError('kPlusConc', val < LIMITS.thermodynamic.kPlusMin || val > LIMITS.thermodynamic.kPlusMax ? `[K⁺] must be between ${LIMITS.thermodynamic.kPlusMin} and ${LIMITS.thermodynamic.kPlusMax} mM.` : '');
    onChange('kPlusConc', val);
  }

  function handlePHChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    if (str === '' || isNaN(val)) { onError('bufferPH', `pH must be between ${LIMITS.thermodynamic.bufferPHMin} and ${LIMITS.thermodynamic.bufferPHMax}.`); return; }
    onError('bufferPH', val < LIMITS.thermodynamic.bufferPHMin || val > LIMITS.thermodynamic.bufferPHMax ? `pH must be between ${LIMITS.thermodynamic.bufferPHMin} and ${LIMITS.thermodynamic.bufferPHMax}.` : '');
    onChange('bufferPH', val);
  }

  function handleReset() {
    const d = DEFAULTS.thermodynamic;
    onChange('tmMin', d.tmMin);
    onChange('tmMax', d.tmMax);
    onChange('saltConcentration', d.saltConcentration);
    onChange('primerConcentration', d.primerConcentration);
    onChange('magnesiumConcentration', d.magnesiumConcentration);
    onChange('dntpTotal', d.dntpTotal);
    onChange('kPlusConc', d.kPlusConc);
    onChange('bufferPH', d.bufferPH);
    ['saltConcentration', 'primerConcentration', 'magnesiumConcentration',
      'dntpTotal', 'kPlusConc', 'bufferPH'].forEach((f) => onError(f, ''));
  }

  const mg    = data.magnesiumConcentration;
  const salt  = data.saltConcentration;
  const pc    = data.primerConcentration;
  const dNTP  = data.dntpTotal  ?? DEFAULTS.thermodynamic.dntpTotal;
  const kPlus = data.kPlusConc  ?? DEFAULTS.thermodynamic.kPlusConc;
  const pH    = data.bufferPH   ?? DEFAULTS.thermodynamic.bufferPH;

  // dNTPs chelate Mg²⁺ stoichiometrically → free Mg²⁺ = total − dNTP
  const freeMg = Math.max(0, mg - dNTP);

  // ── Warnings ──────────────────────────────────────────────────────────────
  const mgWarning = !errors.magnesiumConcentration
    ? mg < 1.0
      ? 'Low [Mg²⁺] — polymerase cofactor activity is reduced; amplification efficiency may suffer.'
      : mg > 3.5
        ? 'High [Mg²⁺] — increased risk of non-specific products and primer-dimer formation.'
        : ''
    : '';

  const saltWarning = !errors.saltConcentration
    ? salt < 20
      ? `Low [Na⁺] (${salt} mM) — estimated Tm is ~${Math.round(16.6 * Math.log10(50 / salt))}°C lower than standard (50 mM). Adjust target Tm accordingly.`
      : salt > 150
        ? `High [Na⁺] (${salt} mM) — estimated Tm is ~${Math.round(16.6 * Math.log10(salt / 50))}°C higher than standard. If your master mix has a pre-formulated buffer, verify the total [Na⁺].`
        : ''
    : '';

  const primerConcWarning = !errors.primerConcentration
    ? pc < 100
      ? `Low primer concentration (${pc} nM) — Tm may be ~3–5°C lower than calculations at 250 nM. Consider reducing the annealing temperature.`
      : pc > 600
        ? `High primer concentration (${pc} nM) — increased risk of primer-dimer formation and elevated SYBR Green background fluorescence.`
        : ''
    : '';

  const dntpWarning = !errors.dntpTotal
    ? dNTP < 0.1
      ? `Very low [dNTP] (${dNTP} mM) — risk of substrate depletion in high-cycle or high-template reactions.`
      : dNTP > 0.4
        ? `[dNTP] (${dNTP} mM) chelates Mg²⁺ — check the effective free [Mg²⁺] indicator below.`
        : ''
    : '';

  const kPlusWarning = !errors.kPlusConc
    ? kPlus > 100
      ? `[K⁺] ${kPlus} mM significantly inhibits Taq and most thermostable polymerases. Most master mixes use 40–75 mM KCl.`
      : kPlus > 75
        ? `[K⁺] ${kPlus} mM is at the upper recommended limit (≤ 75 mM). Monitor for reduced polymerase activity.`
        : ''
    : '';

  const phWarning = !errors.bufferPH
    ? pH < 7.5
      ? `Buffer pH ${pH} is below 7.5 — polymerase activity drops sharply below pH 7.5. Most enzymes are optimized for pH 8.3–8.8.`
      : pH > 9.0
        ? `Buffer pH ${pH} is above 9.0 — risk of primer degradation and elevated non-specific amplification.`
        : ''
    : '';

  const freeMgWarning =
    !errors.magnesiumConcentration && !errors.dntpTotal && freeMg < 1.0
      ? `Free [Mg²⁺] ≈ ${freeMg.toFixed(2)} mM (${mg} total − ${dNTP} dNTP) is below 1.0 mM — insufficient for reliable polymerase activity. Increase [Mg²⁺]_total or reduce [dNTP].`
      : '';

  const showCombinedIonicWarn =
    !errors.saltConcentration && !errors.magnesiumConcentration && salt > 100 && mg > 3.0;

  const fwdTmDeficit  = seqAnalysis ? data.tmMin - seqAnalysis.fwdRegionTm : 0;
  const showFwdTmWarn = seqAnalysis && fwdTmDeficit > 33;

  const hasError = !!(
    errors.saltConcentration || errors.primerConcentration || errors.magnesiumConcentration ||
    errors.dntpTotal || errors.kPlusConc || errors.bufferPH
  );
  const hasWarning = !!(
    mgWarning || saltWarning || primerConcWarning || dntpWarning || kPlusWarning ||
    phWarning || freeMgWarning || showCombinedIonicWarn || showFwdTmWarn
  );

  return (
    <CollapsibleSection
      title="Thermodynamic Parameters"
      tooltip="Set buffer and ionic conditions for accurate Tm prediction via nearest-neighbor thermodynamics."
      hasError={hasError}
      hasWarning={hasWarning}
      onFirstOpen={onFirstOpen}
      openRequested={openRequested}
      actions={
        <button
          type="button"
          onClick={handleResetClick}
          className={`text-xs font-medium px-2 py-0.5 rounded transition-all duration-150 shrink-0 ${
            confirmingReset
              ? 'text-red-600 bg-red-50 border border-red-200 hover:bg-red-100'
              : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
          }`}
        >
          {confirmingReset ? 'Confirm reset?' : 'Reset'}
        </button>
      }
    >
      {/* Tm range slider */}
      <RangeSlider
        label="Melting temperature (Tm) range"
        min={LIMITS.thermodynamic.tmMin}
        max={LIMITS.thermodynamic.tmMax}
        valueMin={data.tmMin}
        valueMax={data.tmMax}
        step={1}
        unit="°C"
        onChange={(lo, hi) => { onChange('tmMin', lo); onChange('tmMax', hi); }}
        tooltip="Target Tm range for primers. 58–62°C is optimal for stem-loop RT-qPCR. Too low → mispriming; too high → reduced hybridization efficiency."
      />

      {/* Subsection divider */}
      <div className="flex items-center gap-3 pt-1">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400 shrink-0">
          Buffer &amp; Ionic Conditions
        </span>
        <div className="flex-1 h-px bg-gray-100" />
      </div>

      {/* 3 × 2 parameter grid */}
      <div className="grid grid-cols-3 gap-x-4 gap-y-4">
        <NumInput
          id="thermo-na"
          label={<>[Na<sup>+</sup>] / NaCl</>}
          tooltip="Monovalent sodium concentration. Affects Tm via SantaLucia correction: ΔTm ≈ 16.6 × log([Na⁺] / 50 mM). Default 50 mM suits most standard PCR buffers."
          value={salt}
          onChange={handleSaltChange}
          min={LIMITS.thermodynamic.saltMin}
          max={LIMITS.thermodynamic.saltMax}
          step={5}
          unit="mM"
          error={errors.saltConcentration}
        />

        <NumInput
          id="thermo-k"
          label={<>[K<sup>+</sup>] / KCl</>}
          tooltip="Potassium chloride concentration. Contributes to ionic strength. Taq and most thermostable polymerases are inhibited at KCl > 75–100 mM. Most master mixes contain 40–75 mM KCl."
          value={kPlus}
          onChange={handleKPlusChange}
          min={LIMITS.thermodynamic.kPlusMin}
          max={LIMITS.thermodynamic.kPlusMax}
          step={5}
          unit="mM"
          error={errors.kPlusConc}
        />

        <NumInput
          id="thermo-mg"
          label={<>[Mg<sup>2+</sup>]<sub> total</sub></>}
          tooltip="Total magnesium concentration. Mg²⁺ is the essential polymerase cofactor and stabilizes dNTP binding. Caution: dNTPs chelate Mg²⁺ stoichiometrically — free [Mg²⁺] = [Mg²⁺]_total − [dNTP]_total. Optimal free Mg²⁺ is 1.5–3 mM."
          value={mg}
          onChange={handleMgChange}
          min={LIMITS.thermodynamic.mgMin}
          max={LIMITS.thermodynamic.mgMax}
          step={0.5}
          unit="mM"
          error={errors.magnesiumConcentration}
        />

        <NumInput
          id="thermo-dntp"
          label="[dNTP] total"
          tooltip="Total dNTP concentration (dATP + dCTP + dGTP + dTTP combined). Standard: 0.2 mM per nucleotide = 0.8 mM total. Many protocols list 0.2 mM as the per-dNTP value — check your master mix datasheet. dNTPs chelate Mg²⁺ stoichiometrically."
          value={dNTP}
          onChange={handleDntpChange}
          min={LIMITS.thermodynamic.dntpMin}
          max={LIMITS.thermodynamic.dntpMax}
          step={0.05}
          unit="mM"
          error={errors.dntpTotal}
        />

        <NumInput
          id="thermo-primer"
          label="[Primer]"
          tooltip="Primer concentration per primer in the reaction. Used in Tm calculation: correction term ≈ R × ln([primer] / 4). Standard is 250 nM; serum/plasma samples may require 50–100 nM due to low RNA input."
          value={pc}
          onChange={handlePrimerConcChange}
          min={LIMITS.thermodynamic.primerConcMin}
          max={LIMITS.thermodynamic.primerConcMax}
          step={10}
          unit="nM"
          error={errors.primerConcentration}
        />

        <NumInput
          id="thermo-ph"
          label="Buffer pH"
          tooltip="Reaction buffer pH at 20°C. Most Tris-HCl buffers are pH 8.3–8.8. Note: Tris has a strong temperature coefficient (−0.03 pH/°C) — at 72°C extension, pH is ~1.5 units lower than at 20°C."
          value={pH}
          onChange={handlePHChange}
          min={LIMITS.thermodynamic.bufferPHMin}
          max={LIMITS.thermodynamic.bufferPHMax}
          step={0.1}
          unit=""
          error={errors.bufferPH}
        />
      </div>

      {/* Effective free Mg²⁺ indicator */}
      {!errors.magnesiumConcentration && !errors.dntpTotal && (
        <div
          className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs border
            ${freeMg < 1.0
              ? 'bg-red-50 border-red-200 text-red-700'
              : freeMg < 1.5
                ? 'bg-amber-50 border-amber-200 text-amber-700'
                : 'bg-teal-50 border-teal-200 text-teal-700'
            }`}
        >
          <span className="font-medium shrink-0">Effective free [Mg²⁺]</span>
          <span className="font-mono font-bold">{freeMg.toFixed(2)} mM</span>
          <span className="text-gray-400 font-normal">
            ({mg} total − {dNTP} mM dNTP)
          </span>
          <span className="ml-auto shrink-0 font-medium">
            {freeMg >= 1.5
              ? '✓ Optimal (1.5–3 mM)'
              : freeMg >= 1.0
                ? '⚠ Below optimal'
                : '✕ Insufficient'}
          </span>
        </div>
      )}

      {/* Warning banners — most critical first */}
      {freeMgWarning            && <WarnBox text={freeMgWarning} />}
      {saltWarning              && <WarnBox text={saltWarning} />}
      {kPlusWarning             && <WarnBox text={kPlusWarning} />}
      {mgWarning                && <WarnBox text={mgWarning} />}
      {!freeMgWarning && dntpWarning && <WarnBox text={dntpWarning} />}
      {primerConcWarning        && <WarnBox text={primerConcWarning} />}
      {phWarning                && <WarnBox text={phWarning} />}
      {showCombinedIonicWarn && (
        <WarnBox text={`High ionic strength: [Na⁺] ${salt} mM + [Mg²⁺] ${mg} mM — actual Tm may be significantly higher than the Na⁺-only correction predicts. Consider reducing one parameter to avoid non-specific binding.`} />
      )}
      {showFwdTmWarn && (
        <WarnBox text={`Tm target may be difficult to achieve: the 12-nt miRNA binding region contributes only ~${seqAnalysis.fwdRegionTm}°C (Wallace rule). Reaching ${data.tmMin}°C requires the 5′ tail to add ~${fwdTmDeficit}°C — equivalent to a 12–15 nt extension. Consider lowering Tm min to ${data.tmMin - 5}–${data.tmMin - 3}°C.`} />
      )}
    </CollapsibleSection>
  );
}
