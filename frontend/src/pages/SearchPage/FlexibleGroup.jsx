// FlexibleGroup — Parameters that change the score of the Flexible criteria (2026-11-22):
//   1. No critical weakness — the standard primer rules (GC window, GC clamp): in the
//      tiered engine they no longer filter (QD 15) but set has_v4_violation, a step of
//      the ranking key;
//   2. PCR — the annealing temperature Ta (P2 |Tm − Ta|);
//   reaction conditions — salt, Mg²⁺, dNTP, primer concentration: every Tm.
// Field names and defaults are unchanged (constants/defaults.js).
import { useState, useRef } from 'react';
import RangeSlider from '../../components/ui/RangeSlider.jsx';
import NumInput from '../../components/ui/NumInput.jsx';
import Toggle from '../../components/ui/Toggle.jsx';
import Tooltip from '../../components/ui/Tooltip.jsx';
import CollapsibleSection from '../../components/ui/CollapsibleSection.jsx';
import { DEFAULTS, LIMITS } from '../../constants/defaults.js';
import { taAboveWindowLow, taOutsideWindow } from '../../utils/paramChecks.js';
import { WarnBox, SubDivider } from './paramUi.jsx';

// Free Mg²⁺ (total − dNTP) below this warns. Project threshold, no published source.
const FREE_MG_WARN_BELOW = 0.5;   // mM

export const TA_TOOLTIP = 'Annealing/extension temperature of the 2-step cycling you will run (Chen 2005: 40 × 95 °C 15 s / 60 °C 1 min). Forward primers are ranked by |Tm − Ta|, so enter the Ta you will actually use.';

export const PRIMER_CONC_TOOLTIP = 'One value for both primers (max 1000 nM). Tm is computed at this concentration. Chen 2005 used 1.5 µM forward / 0.7 µM reverse; entering 1000 nM then gives a Tm about 0.5 °C below the real one (forward primer; the reverse primer comes out about 0.5 °C above).';


export default function FlexibleGroup({
  constraints, onConstraintChange, seqAnalysis,
  thermoData, thermoErrors, onThermoChange, onThermoError,
  qpcrData, qpcrErrors, onQpcrChange, onQpcrError,
  onFirstOpen, openRequested,
}) {
  const [confirmingReset, setConfirmingReset] = useState(false);
  const resetTimerRef = useRef(null);

  function handleResetClick() {
    if (confirmingReset) {
      clearTimeout(resetTimerRef.current);
      setConfirmingReset(false);
      const d = DEFAULTS.thermodynamic;
      // Reaction conditions only; the Tm window has its own reset under Required.
      ['saltConcentration', 'primerConcentration',
        'magnesiumConcentration', 'dntpTotal', 'kPlusConc', 'bufferPH']
        .forEach((f) => onThermoChange(f, d[f]));
      ['saltConcentration', 'primerConcentration', 'magnesiumConcentration',
        'dntpTotal', 'kPlusConc', 'bufferPH']
        .forEach((f) => onThermoError(f, ''));
    } else {
      setConfirmingReset(true);
      resetTimerRef.current = setTimeout(() => setConfirmingReset(false), 2500);
    }
  }

  // ── Reaction conditions ───────────────────────────────────────────────
  function mkHandler(field, min, max, msg) {
    return (e) => {
      const val = parseFloat(e.target.value);
      if (e.target.value === '' || isNaN(val)) { onThermoError(field, msg); return; }
      onThermoError(field, (val < min || val > max) ? msg : '');
      onThermoChange(field, val);
    };
  }
  const L = LIMITS.thermodynamic;
  const handleSalt     = mkHandler('saltConcentration',      L.saltMin,      L.saltMax,      `Monovalent salt must be ${L.saltMin}–${L.saltMax} mM.`);
  const handlePrimerC  = mkHandler('primerConcentration',    L.primerConcMin,L.primerConcMax,`Primer concentration must be ${L.primerConcMin}–${L.primerConcMax} nM.`);
  const handleMg       = mkHandler('magnesiumConcentration', L.mgMin,        L.mgMax,        `[Mg²⁺] must be ${L.mgMin}–${L.mgMax} mM.`);
  const handleDntp     = mkHandler('dntpTotal',              L.dntpMin,      L.dntpMax,      `[dNTP] must be ${L.dntpMin}–${L.dntpMax} mM.`);
  const handleKPlus    = mkHandler('kPlusConc',              L.kPlusMin,     L.kPlusMax,     `[K⁺] must be ${L.kPlusMin}–${L.kPlusMax} mM.`);
  const handlePH       = mkHandler('bufferPH',               L.bufferPHMin,  L.bufferPHMax,  `pH must be ${L.bufferPHMin}–${L.bufferPHMax}.`);

  const mg    = thermoData.magnesiumConcentration;
  const salt  = thermoData.saltConcentration;
  const pc    = thermoData.primerConcentration;
  const dNTP  = thermoData.dntpTotal ?? DEFAULTS.thermodynamic.dntpTotal;
  const kPlus = thermoData.kPlusConc ?? DEFAULTS.thermodynamic.kPlusConc;
  const pH    = thermoData.bufferPH  ?? DEFAULTS.thermodynamic.bufferPH;
  const freeMg = Math.max(0, mg - dNTP);

  const mgWarn = !thermoErrors.magnesiumConcentration
    ? mg < 1.0 ? 'Low Mg²⁺: polymerase cofactor activity is reduced; amplification efficiency may suffer.'
      : mg > 3.5 ? 'High Mg²⁺: higher risk of non-specific products and primer-dimers.' : '' : '';
  const saltWarn = !thermoErrors.saltConcentration
    ? salt < 20 ? `Low monovalent salt (${salt}\u00a0mM): the estimated Tm is about ${Math.round(16.6 * Math.log10(50 / salt))}\u00a0°C lower than at the standard 50\u00a0mM. Adjust the Tm window accordingly.`
      : salt > 150 ? `High monovalent salt (${salt}\u00a0mM): the estimated Tm is about ${Math.round(16.6 * Math.log10(salt / 50))}\u00a0°C higher than at the standard 50\u00a0mM.` : '' : '';
  const primerCWarn = !thermoErrors.primerConcentration
    ? pc < 100 ? `Low primer concentration (${pc}\u00a0nM): the Tm may be about 3–5\u00a0°C lower than at 250\u00a0nM.`
      : pc > 600 ? `High primer concentration (${pc}\u00a0nM): higher risk of primer-dimers.` : '' : '';
  // Mg²⁺ chelation by dNTP is shown once, in the free-Mg²⁺ box (UI review 2026-11-23:
  // the second box fired at the standard 0.8 mM and pointed "below" to a box above it).
  const dntpWarn = !thermoErrors.dntpTotal && dNTP < 0.1
    ? `Very low dNTP (${dNTP}\u00a0mM total): risk of substrate depletion.` : '';
  const kPlusWarn = !thermoErrors.kPlusConc
    ? kPlus > 100 ? `K⁺ ${kPlus}\u00a0mM strongly inhibits Taq and most thermostable polymerases.`
      : kPlus > 75 ? `K⁺ ${kPlus}\u00a0mM is at the upper recommended limit (75\u00a0mM).` : '' : '';
  const phWarn = !thermoErrors.bufferPH
    ? pH < 7.5 ? `Buffer pH ${pH} is below 7.5: polymerase activity drops sharply below pH 7.5.`
      : pH > 9.0 ? `Buffer pH ${pH} is above 9.0: risk of primer degradation.` : '' : '';
  // One warning line, free Mg²⁺ < 0.5 mM: a project threshold, not taken from a publication.
  // The standard Taq mix (1.5 mM MgCl₂, 0.2 mM each dNTP) leaves 0.7 mM and must not warn,
  // so there is no 1.0 mM level (2026-11-23).
  const freeMgLow = freeMg < FREE_MG_WARN_BELOW;
  const freeMgWarn = !thermoErrors.magnesiumConcentration && !thermoErrors.dntpTotal && freeMgLow
    ? 'Polymerase activity may be impaired. Increase the total Mg²⁺ or reduce the dNTP.' : '';
  const showIonicWarn = !thermoErrors.saltConcentration && !thermoErrors.magnesiumConcentration && salt > 100 && mg > 3.0;

  // ── PCR: annealing temperature ────────────────────────────────────────
  function handleTaChange(e) {
    const str = e.target.value;
    const val = parseFloat(str);
    const msg = `Annealing temperature must be between ${LIMITS.qpcr.taMin} and ${LIMITS.qpcr.taMax}°C.`;
    if (str === '' || isNaN(val)) { onQpcrError('annealingTemp', msg); return; }
    onQpcrError('annealingTemp', val < LIMITS.qpcr.taMin || val > LIMITS.qpcr.taMax ? msg : '');
    onQpcrChange('annealingTemp', val);
  }
  const ta = qpcrData.annealingTemp;
  const { tmMin, tmMax } = thermoData;
  // Kept condition (Ta > tmMin + 5); the wording no longer contradicts the Ta tooltip.
  const showTaHighWarning = !qpcrErrors.annealingTemp && taAboveWindowLow(ta, tmMin);
  const showTaWindowWarning = !qpcrErrors.annealingTemp && taOutsideWindow(ta, tmMin, tmMax);

  // ── 1. No critical weakness: standard primer rules ────────────────────
  const seqWarn = !!(seqAnalysis?.hasContinuousRepeat
    || (seqAnalysis && (seqAnalysis.fwdRegionGC < 30 || seqAnalysis.fwdRegionGC > 70)));

  const thermoHasError = !!(thermoErrors.saltConcentration || thermoErrors.primerConcentration
    || thermoErrors.magnesiumConcentration || thermoErrors.dntpTotal
    || thermoErrors.kPlusConc || thermoErrors.bufferPH);
  const thermoHasWarn = !!(mgWarn || saltWarn || primerCWarn || dntpWarn
    || kPlusWarn || phWarn || freeMgWarn || showIonicWarn);

  return (
    <CollapsibleSection
      title="Flexible"
      tooltip="Settings that change the score of the Flexible criteria: 1. No critical weakness (standard primer rules), 2. PCR (Ta), and the reaction conditions every Tm is computed at."
      hasError={thermoHasError || !!qpcrErrors.annealingTemp}
      hasWarning={seqWarn || thermoHasWarn || showTaHighWarning || showTaWindowWarning}
      onFirstOpen={onFirstOpen}
      openRequested={openRequested}
      actions={
        <button
          type="button"
          onClick={handleResetClick}
          className={`text-xs font-medium px-2 py-0.5 rounded transition-all duration-150 shrink-0 ${confirmingReset
            ? 'text-red-700 bg-red-50 border border-red-200 hover:bg-red-100'
            : 'text-slate-700 hover:text-slate-900 hover:bg-slate-100'}`}
        >
          {confirmingReset ? 'Confirm reset?' : 'Reset reaction conditions'}
        </button>
      }
    >
      {/* ══ 1. No critical weakness — standard primer rules ══ */}
      <SubDivider label="1. Standard primer rules"
        note="Part of No critical weakness. Not filters: a set outside them ranks below the sets with the same specificity." />

      <RangeSlider
        label="GC content (%)"
        min={LIMITS.primerConstraints.gcMin}
        max={LIMITS.primerConstraints.gcMax}
        valueMin={constraints.gcMin}
        valueMax={constraints.gcMax}
        step={1}
        unit="%"
        onChange={(lo, hi) => { onConstraintChange('gcMin', lo); onConstraintChange('gcMax', hi); }}
        tooltip="Standard primer rule: a forward primer with GC % outside this window ranks below the sets that meet the rules (same specificity). Composition is also scored by F1 (40–60 % best)."
      />

      <div className="space-y-2">
        <div className="flex items-center gap-1.5">
          <label className="text-sm font-medium text-slate-700">3′ GC clamp</label>
          <Tooltip text="Standard primer rule: at least one G or C in the last 3 nt of the forward primer. The 3′ end is set by the miRNA; the clamp is scored (F2) and, with this ON, an all-A/T 3′ end counts as a rule not met." />
        </div>
        <Toggle
          checked={constraints.gcClamp3prime}
          onChange={(val) => onConstraintChange('gcClamp3prime', val)}
          label
        />
        {seqAnalysis && !seqAnalysis.fwdEndGC && constraints.gcClamp3prime && (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-1.5 leading-relaxed">
            Position 10–12 of the miRNA ends with A/U: the 3′ end is set by the miRNA; GC clamp is scored, not adjusted.
          </p>
        )}
      </div>

      {seqAnalysis?.hasContinuousRepeat && (
        <WarnBox text="The sequence contains a homopolymer run (4 or more identical nt). It can cause polymerase slippage; the algorithm deprioritizes it." />
      )}
      {seqAnalysis && seqAnalysis.fwdRegionGC < 30 && (
        <WarnBox text={`AU-rich forward binding region (${seqAnalysis.fwdRegionGC}% GC): the 5′-most 12 nt are mostly A/U, so the forward primer needs a long 5′ tail to reach the Tm window. Consider lowering the Tm minimum under Required.`} />
      )}
      {seqAnalysis && seqAnalysis.fwdRegionGC > 70 && (
        <WarnBox text={`GC-rich forward binding region (${seqAnalysis.fwdRegionGC}% GC): risk of self-complementarity and hairpins. Check the structure rows of each primer set in the results.`} />
      )}

      {/* ══ 2. PCR ══ */}
      <SubDivider label="2. PCR" note="Scores how close the forward-primer Tm is to Ta." />
      <div className="space-y-1 max-w-xs">
        <NumInput
          id="qpcr-ta"
          label="Annealing temperature (Ta)"
          tooltip={TA_TOOLTIP}
          value={ta}
          onChange={handleTaChange}
          min={LIMITS.qpcr.taMin}
          max={LIMITS.qpcr.taMax}
          step={1}
          unit="°C"
          error={qpcrErrors.annealingTemp}
        />
      </div>
      {showTaHighWarning && (
        <WarnBox testId="ta-high-warning"
          text={`Ta is more than 5\u00a0°C above the lower end of the Tm window (${tmMin}\u00a0°C): forward primers near that end would anneal poorly. Raise the Tm window together with Ta.`} />
      )}
      {showTaWindowWarning && (
        <WarnBox testId="ta-window-warning"
          text={`Ta is outside the forward-primer Tm window (${tmMin}–${tmMax} °C), so P2 cannot reach its best level. Consider setting the window to Ta ± 2 °C.`} />
      )}

      {/* ══ Reaction conditions ══ */}
      <SubDivider label="Reaction conditions"
        note="Every Tm is computed at these values, including the Tm window and the specificity checks. Enter the Mg²⁺ and dNTP of the master mix you will use (its datasheet)." />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-4 gap-y-4">
        <NumInput
          id="thermo-na"
          label={<>Na<sup>+</sup>/K<sup>+</sup> total</>}
          tooltip="Total monovalent salt of your PCR buffer (usually KCl). The default 50 mM is the condition every validation number uses."
          value={salt}
          onChange={handleSalt}
          min={L.saltMin} max={L.saltMax} step={5} unit="mM"
          error={thermoErrors.saltConcentration}
        />
        <NumInput
          id="thermo-k"
          label={<>Extra K<sup>+</sup></>}
          hint="On top of the total; usually 0."
          value={kPlus}
          onChange={handleKPlus}
          min={L.kPlusMin} max={L.kPlusMax} step={5} unit="mM"
          error={thermoErrors.kPlusConc}
        />
        <NumInput
          id="thermo-mg"
          label={<>Mg<sup>2+</sup> total</>}
          value={mg}
          onChange={handleMg}
          min={L.mgMin} max={L.mgMax} step={0.5} unit="mM"
          error={thermoErrors.magnesiumConcentration}
        />
        <NumInput
          id="thermo-dntp"
          label="dNTP total"
          hint="0.2 mM each = 0.8 mM total."
          value={dNTP}
          onChange={handleDntp}
          min={L.dntpMin} max={L.dntpMax} step={0.05} unit="mM"
          error={thermoErrors.dntpTotal}
        />
        <NumInput
          id="thermo-primer"
          label="Primer"
          tooltip={PRIMER_CONC_TOOLTIP}
          value={pc}
          onChange={handlePrimerC}
          min={L.primerConcMin} max={L.primerConcMax} step={10} unit="nM"
          error={thermoErrors.primerConcentration}
        />
        <NumInput
          id="thermo-ph"
          label="Buffer pH"
          hint="Applied only if you change it."
          value={pH}
          onChange={handlePH}
          min={L.bufferPHMin} max={L.bufferPHMax} step={0.1} unit=""
          error={thermoErrors.bufferPH}
        />
      </div>

      {/* Free Mg²⁺ indicator */}
      {!thermoErrors.magnesiumConcentration && !thermoErrors.dntpTotal && (
        <div data-testid="free-mg" className={`px-3 py-2 rounded-lg text-xs border space-y-0.5 ${
          freeMgLow ? 'bg-amber-50 border-amber-200 text-amber-800'
            : 'bg-green-50 border-green-200 text-green-700'}`}>
          <p className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <span className="font-medium">Free Mg²⁺</span>
            <span className="font-bold tabular-nums whitespace-nowrap">{freeMg.toFixed(2)}{'\u00a0'}mM</span>
            <span className="text-slate-700 font-normal tabular-nums whitespace-nowrap">({mg} total − {dNTP} dNTP, which binds Mg²⁺ one to one)</span>
            <span className="ml-auto shrink-0 font-semibold">
              {freeMgLow ? `Warning: below ${FREE_MG_WARN_BELOW} mM` : `Pass (≥ ${FREE_MG_WARN_BELOW} mM)`}
            </span>
          </p>
          {freeMgWarn && <p>{freeMgWarn}</p>}
          <p className="text-slate-600 font-normal">
            The {FREE_MG_WARN_BELOW}{' '}mM line is a project threshold, not a published value.
          </p>
        </div>
      )}

      {saltWarn                && <WarnBox text={saltWarn} />}
      {kPlusWarn               && <WarnBox text={kPlusWarn} />}
      {mgWarn                  && <WarnBox text={mgWarn} />}
      {dntpWarn                && <WarnBox text={dntpWarn} />}
      {primerCWarn             && <WarnBox text={primerCWarn} />}
      {phWarn                  && <WarnBox text={phWarn} />}
      {showIonicWarn && (
        <WarnBox text={`High ionic strength (monovalent ${salt}\u00a0mM plus Mg²⁺ ${mg}\u00a0mM): the real Tm may be clearly higher than the salt correction predicts.`} />
      )}
    </CollapsibleSection>
  );
}
