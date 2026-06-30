import { useState, useRef } from 'react';
import RangeSlider from '../../components/ui/RangeSlider.jsx';
import NumInput from '../../components/ui/NumInput.jsx';
import Toggle from '../../components/ui/Toggle.jsx';
import Tooltip from '../../components/ui/Tooltip.jsx';
import CollapsibleSection from '../../components/ui/CollapsibleSection.jsx';
import { DEFAULTS, LIMITS } from '../../constants/defaults.js';

// ── Helpers ───────────────────────────────────────────────────────────────────

function WarnBox({ text }) {
  return (
    <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
      ⚠ {text}
    </p>
  );
}

function SubDivider({ label }) {
  return (
    <div className="flex items-center gap-3 pt-1">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400 shrink-0">
        {label}
      </span>
      <div className="flex-1 h-px bg-gray-100" />
    </div>
  );
}

function Reveal({ show, children }) {
  return (
    <div className={`grid transition-[grid-template-rows] duration-300 ease-in-out ${show ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}>
      <div className="overflow-hidden">{children}</div>
    </div>
  );
}

// ── Binding region hint logic ─────────────────────────────────────────────────

function getBindingHint(mirnaFamily, bindingNt) {
  const fam = (mirnaFamily || '').toLowerCase();
  if (fam.includes('let-7') || fam.includes('let7')) {
    return {
      type: 'suggest',
      text: `let-7 family has 13 members with nearly identical 3′ sequences — 7 nt is recommended for reliable discrimination between family members.`,
      suggestNt: 7,
    };
  }
  if (fam.includes('mir-17') || fam.includes('mir17')) {
    return {
      type: 'suggest',
      text: `miR-17 family members share highly conserved seed and 3′ sequences — 7 nt improves specificity.`,
      suggestNt: 7,
    };
  }
  if (fam.includes('mir-29') || fam.includes('mir29') || fam.includes('mir-30') || fam.includes('mir30')) {
    return {
      type: 'suggest',
      text: `${mirnaFamily} family has multiple members with similar 3′ ends — 7 nt reduces cross-reactivity risk.`,
      suggestNt: 7,
    };
  }
  if (bindingNt === 5) {
    return {
      type: 'warn',
      text: '5 nt reduces specificity against related family members. Use only when template accessibility or secondary structure requires shorter overlap.',
    };
  }
  return null;
}

// ── Main component ────────────────────────────────────────────────────────────

export default function PrimerConstraintsGroup({
  // Primer constraints
  data, onChange, seqAnalysis, mirnaFamily,
  // Thermodynamic
  thermoData, thermoErrors, onThermoChange, onThermoError,
  // Advanced specificity (lives in detectionMethod state)
  specData, onSpecChange,
  // CollapsibleSection
  onFirstOpen, openRequested,
}) {
  const [confirmingReset, setConfirmingReset] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const resetTimerRef = useRef(null);

  // ── Thermodynamic reset ───────────────────────────────────────────────────
  function handleResetClick() {
    if (confirmingReset) {
      clearTimeout(resetTimerRef.current);
      setConfirmingReset(false);
      const d = DEFAULTS.thermodynamic;
      ['tmMin','tmMax','saltConcentration','primerConcentration',
       'magnesiumConcentration','dntpTotal','kPlusConc','bufferPH']
        .forEach((f) => onThermoChange(f, d[f]));
      ['saltConcentration','primerConcentration','magnesiumConcentration',
       'dntpTotal','kPlusConc','bufferPH']
        .forEach((f) => onThermoError(f, ''));
    } else {
      setConfirmingReset(true);
      resetTimerRef.current = setTimeout(() => setConfirmingReset(false), 2500);
    }
  }

  // ── Numeric field handlers (thermodynamic) ────────────────────────────────
  function mkHandler(field, min, max, msg) {
    return (e) => {
      const val = parseFloat(e.target.value);
      if (e.target.value === '' || isNaN(val)) { onThermoError(field, msg); return; }
      onThermoError(field, (val < min || val > max) ? msg : '');
      onThermoChange(field, val);
    };
  }
  const L = LIMITS.thermodynamic;
  const handleSalt     = mkHandler('saltConcentration',      L.saltMin,      L.saltMax,      `[Na⁺] must be ${L.saltMin}–${L.saltMax} mM.`);
  const handlePrimerC  = mkHandler('primerConcentration',    L.primerConcMin,L.primerConcMax,`Primer concentration must be ${L.primerConcMin}–${L.primerConcMax} nM.`);
  const handleMg       = mkHandler('magnesiumConcentration', L.mgMin,        L.mgMax,        `[Mg²⁺] must be ${L.mgMin}–${L.mgMax} mM.`);
  const handleDntp     = mkHandler('dntpTotal',              L.dntpMin,      L.dntpMax,      `[dNTP] must be ${L.dntpMin}–${L.dntpMax} mM.`);
  const handleKPlus    = mkHandler('kPlusConc',              L.kPlusMin,     L.kPlusMax,     `[K⁺] must be ${L.kPlusMin}–${L.kPlusMax} mM.`);
  const handlePH       = mkHandler('bufferPH',               L.bufferPHMin,  L.bufferPHMax,  `pH must be ${L.bufferPHMin}–${L.bufferPHMax}.`);

  // ── Thermodynamic derived values ──────────────────────────────────────────
  const mg    = thermoData.magnesiumConcentration;
  const salt  = thermoData.saltConcentration;
  const pc    = thermoData.primerConcentration;
  const dNTP  = thermoData.dntpTotal             ?? DEFAULTS.thermodynamic.dntpTotal;
  const kPlus = thermoData.kPlusConc             ?? DEFAULTS.thermodynamic.kPlusConc;
  const pH    = thermoData.bufferPH              ?? DEFAULTS.thermodynamic.bufferPH;
  const freeMg = Math.max(0, mg - dNTP);

  // ── Thermodynamic warnings ────────────────────────────────────────────────
  const mgWarn = !thermoErrors.magnesiumConcentration
    ? mg < 1.0 ? 'Low [Mg²⁺] — polymerase cofactor activity is reduced; amplification efficiency may suffer.'
      : mg > 3.5 ? 'High [Mg²⁺] — increased risk of non-specific products and primer-dimer formation.' : '' : '';
  const saltWarn = !thermoErrors.saltConcentration
    ? salt < 20 ? `Low [Na⁺] (${salt} mM) — estimated Tm is ~${Math.round(16.6 * Math.log10(50 / salt))}°C lower than standard (50 mM). Adjust target Tm accordingly.`
      : salt > 150 ? `High [Na⁺] (${salt} mM) — estimated Tm is ~${Math.round(16.6 * Math.log10(salt / 50))}°C higher than standard.` : '' : '';
  const primerCWarn = !thermoErrors.primerConcentration
    ? pc < 100 ? `Low primer concentration (${pc} nM) — Tm may be ~3–5°C lower than calculations at 250 nM.`
      : pc > 600 ? `High primer concentration (${pc} nM) — increased risk of primer-dimer formation.` : '' : '';
  const dntpWarn = !thermoErrors.dntpTotal
    ? dNTP < 0.1 ? `Very low [dNTP] (${dNTP} mM) — risk of substrate depletion.`
      : dNTP > 0.4 ? `[dNTP] (${dNTP} mM) chelates Mg²⁺ — check the effective free [Mg²⁺] below.` : '' : '';
  const kPlusWarn = !thermoErrors.kPlusConc
    ? kPlus > 100 ? `[K⁺] ${kPlus} mM significantly inhibits Taq and most thermostable polymerases.`
      : kPlus > 75 ? `[K⁺] ${kPlus} mM is at the upper recommended limit (≤ 75 mM).` : '' : '';
  const phWarn = !thermoErrors.bufferPH
    ? pH < 7.5 ? `Buffer pH ${pH} is below 7.5 — polymerase activity drops sharply below pH 7.5.`
      : pH > 9.0 ? `Buffer pH ${pH} is above 9.0 — risk of primer degradation.` : '' : '';
  const freeMgWarn = !thermoErrors.magnesiumConcentration && !thermoErrors.dntpTotal && freeMg < 0.5
    ? `Free [Mg²⁺] ≈ ${freeMg.toFixed(2)} mM (${mg} total − ${dNTP} dNTP) is critically low — polymerase activity will be severely impaired. Increase [Mg²⁺]_total or reduce [dNTP].` : '';
  const showIonicWarn = !thermoErrors.saltConcentration && !thermoErrors.magnesiumConcentration && salt > 100 && mg > 3.0;
  const fwdTmDeficit  = seqAnalysis ? thermoData.tmMin - seqAnalysis.fwdRegionTm : 0;
  const showFwdTmWarn = seqAnalysis && fwdTmDeficit > 33;

  // ── Combined error/warning state ──────────────────────────────────────────
  const thermoHasError = !!(
    thermoErrors.saltConcentration || thermoErrors.primerConcentration ||
    thermoErrors.magnesiumConcentration || thermoErrors.dntpTotal ||
    thermoErrors.kPlusConc || thermoErrors.bufferPH
  );
  const primerHasWarn = !!(seqAnalysis?.hasContinuousRepeat ||
    (seqAnalysis && (seqAnalysis.fwdRegionGC < 30 || seqAnalysis.fwdRegionGC > 70)));
  const thermoHasWarn = !!(mgWarn || saltWarn || primerCWarn || dntpWarn ||
    kPlusWarn || phWarn || freeMgWarn || showIonicWarn || showFwdTmWarn);

  // ── 3' binding region hint ────────────────────────────────────────────────
  const bindingHint = getBindingHint(mirnaFamily, data.bindingRegion3prime);

  return (
    <CollapsibleSection
      title="Primer Design Constraints"
      tooltip="Primer design constraints: GC content, primer length, thermodynamic parameters, and 3′ binding specificity."
      hasError={thermoHasError}
      hasWarning={primerHasWarn || thermoHasWarn}
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
          {confirmingReset ? 'Confirm reset?' : 'Reset Tm'}
        </button>
      }
    >

      {/* ══ 1. PRIMER CONSTRAINTS ══════════════════════════════════════════ */}

      <RangeSlider
        label="GC content (%)"
        min={LIMITS.primerConstraints.gcMin}
        max={LIMITS.primerConstraints.gcMax}
        valueMin={data.gcMin}
        valueMax={data.gcMax}
        step={1}
        unit="%"
        onChange={(lo, hi) => { onChange('gcMin', lo); onChange('gcMax', hi); }}
        tooltip="Below 35%: weak primer-template binding. Above 65%: risk of secondary structures. 40–60% is optimal for stem-loop RT-qPCR."
      />

      <RangeSlider
        label="Primer length (nt)"
        min={LIMITS.primerConstraints.lengthMin}
        max={LIMITS.primerConstraints.lengthMax}
        valueMin={data.lengthMin}
        valueMax={data.lengthMax}
        step={1}
        unit=" nt"
        onChange={(lo, hi) => { onChange('lengthMin', lo); onChange('lengthMax', hi); }}
        tooltip="Total forward primer length. Typically 22–24 nt (miRNA-specific region + 5′ tail). The stem-loop body (~44–57 nt) is not counted here."
      />

      {/* GC Clamp + 3′ Binding region */}
      <div className="grid grid-cols-2 gap-4">

        {/* GC Clamp */}
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

        {/* 3′ Binding region — selectable 5 / 6 / 7 nt */}
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5">
            <label className="text-sm font-medium text-gray-700">3′ Binding region</label>
            <Tooltip text="Number of nucleotides at the 3′ overhang of the stem-loop RT primer that base-pair with the 3′ end of the mature miRNA. 6 nt is the validated standard (Chen et al. 2005). Use 7 nt for large miRNA families with highly similar 3′ sequences." />
          </div>
          <div className="flex gap-1.5">
            {[5, 6, 7].map((nt) => (
              <button
                key={nt}
                type="button"
                onClick={() => onChange('bindingRegion3prime', nt)}
                className={`flex-1 py-1.5 rounded-lg text-sm font-semibold border transition-all duration-150 active:scale-95 ${
                  data.bindingRegion3prime === nt
                    ? 'bg-teal-600 text-white border-teal-600 shadow-sm'
                    : 'bg-white text-gray-600 border-gray-200 hover:border-teal-300 hover:text-teal-700'
                }`}
              >
                {nt} nt
              </button>
            ))}
          </div>
          {/* Family-aware hint */}
          {bindingHint && (
            <p className={`text-xs leading-relaxed rounded-lg px-2.5 py-1.5 ${
              bindingHint.type === 'suggest'
                ? 'text-teal-700 bg-teal-50 border border-teal-100'
                : 'text-amber-700 bg-amber-50 border border-amber-200'
            }`}>
              {bindingHint.type === 'suggest' ? '💡 ' : '⚠ '}
              {bindingHint.text}
              {bindingHint.type === 'suggest' && bindingHint.suggestNt !== data.bindingRegion3prime && (
                <button
                  type="button"
                  onClick={() => onChange('bindingRegion3prime', bindingHint.suggestNt)}
                  className="ml-1.5 underline font-medium hover:no-underline"
                >
                  Use {bindingHint.suggestNt} nt
                </button>
              )}
            </p>
          )}
          {seqAnalysis && !seqAnalysis.fwdEndGC && data.gcClamp3prime && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-1.5 leading-relaxed">
              ⚠ Position 10–12 of the miRNA ends with A/U. The algorithm will adjust the 5′ tail to ensure a GC clamp.
            </p>
          )}
        </div>
      </div>

      {/* Primer sequence warnings */}
      {seqAnalysis?.hasContinuousRepeat && (
        <WarnBox text="Sequence contains a homopolymer run (≥ 4 identical nt). This region can cause polymerase slippage — the algorithm will deprioritize it." />
      )}
      {seqAnalysis && seqAnalysis.fwdRegionGC < 30 && (
        <WarnBox text={`AU-rich forward binding region (${seqAnalysis.fwdRegionGC}% GC): The 5′-most 12 nt are heavily AU — the forward primer will require a long 5′ tail to reach the Tm target. Consider lowering the Tm minimum below.`} />
      )}
      {seqAnalysis && seqAnalysis.fwdRegionGC > 70 && (
        <WarnBox text={`GC-rich forward binding region (${seqAnalysis.fwdRegionGC}% GC): Risk of self-complementarity and hairpin formation. Enable precursor check in Advanced specificity options below.`} />
      )}

      {/* ══ 2. THERMODYNAMIC PARAMETERS ═══════════════════════════════════ */}

      <SubDivider label="Thermodynamic Parameters" />

      <RangeSlider
        label="Melting temperature (Tm) range"
        min={LIMITS.thermodynamic.tmMin}
        max={LIMITS.thermodynamic.tmMax}
        valueMin={thermoData.tmMin}
        valueMax={thermoData.tmMax}
        step={1}
        unit="°C"
        onChange={(lo, hi) => { onThermoChange('tmMin', lo); onThermoChange('tmMax', hi); }}
        tooltip="Target Tm range for primers. 58–62°C is optimal for stem-loop RT-qPCR. Too low → mispriming; too high → reduced hybridization efficiency."
      />

      <SubDivider label="Buffer &amp; Ionic Conditions" />

      <div className="grid grid-cols-3 gap-x-4 gap-y-4">
        <NumInput
          id="thermo-na"
          label={<>[Na<sup>+</sup>] / NaCl</>}
          tooltip="Monovalent sodium concentration. Affects Tm via SantaLucia correction: ΔTm ≈ 16.6 × log([Na⁺] / 50 mM). Default 50 mM suits most standard PCR buffers."
          value={salt}
          onChange={handleSalt}
          min={L.saltMin} max={L.saltMax} step={5} unit="mM"
          error={thermoErrors.saltConcentration}
        />
        <NumInput
          id="thermo-k"
          label={<>[K<sup>+</sup>] / KCl</>}
          tooltip="Potassium chloride concentration. Most master mixes contain 40–75 mM KCl. Taq is inhibited at KCl > 75–100 mM."
          value={kPlus}
          onChange={handleKPlus}
          min={L.kPlusMin} max={L.kPlusMax} step={5} unit="mM"
          error={thermoErrors.kPlusConc}
        />
        <NumInput
          id="thermo-mg"
          label={<>[Mg<sup>2+</sup>]<sub> total</sub></>}
          tooltip="Total magnesium concentration. Free [Mg²⁺] = [Mg²⁺]_total − [dNTP]_total. Optimal free Mg²⁺ is 1.5–3 mM."
          value={mg}
          onChange={handleMg}
          min={L.mgMin} max={L.mgMax} step={0.5} unit="mM"
          error={thermoErrors.magnesiumConcentration}
        />
        <NumInput
          id="thermo-dntp"
          label="[dNTP] total"
          tooltip="Total dNTP concentration. Standard: 0.2 mM per nucleotide = 0.8 mM total. dNTPs chelate Mg²⁺ stoichiometrically."
          value={dNTP}
          onChange={handleDntp}
          min={L.dntpMin} max={L.dntpMax} step={0.05} unit="mM"
          error={thermoErrors.dntpTotal}
        />
        <NumInput
          id="thermo-primer"
          label="[Primer]"
          tooltip="Empirical annealing oligo concentration used for Tm calculation. Not the actual primer concentration in the reaction mix. Default: 200 nM (IDT PrimerQuest). Range: 50–1000 nM."
          value={pc}
          onChange={handlePrimerC}
          min={L.primerConcMin} max={L.primerConcMax} step={10} unit="nM"
          error={thermoErrors.primerConcentration}
        />
        <NumInput
          id="thermo-ph"
          label="Buffer pH"
          tooltip="Reaction buffer pH at 20°C. Most Tris-HCl buffers are pH 8.3–8.8."
          value={pH}
          onChange={handlePH}
          min={L.bufferPHMin} max={L.bufferPHMax} step={0.1} unit=""
          error={thermoErrors.bufferPH}
        />
      </div>

      {/* Free Mg²⁺ indicator */}
      {!thermoErrors.magnesiumConcentration && !thermoErrors.dntpTotal && (
        <div className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs border ${
          freeMg < 0.5 ? 'bg-red-50 border-red-200 text-red-700'
            : freeMg < 1.0 ? 'bg-amber-50 border-amber-200 text-amber-700'
            : 'bg-teal-50 border-teal-200 text-teal-700'
        }`}>
          <span className="font-medium shrink-0">Effective free [Mg²⁺]</span>
          <span className="font-mono font-bold">{freeMg.toFixed(2)} mM</span>
          <span className="text-gray-400 font-normal">({mg} total − {dNTP} mM dNTP)</span>
          <span className="ml-auto shrink-0 font-medium">
            {freeMg >= 1.0 ? '✓ Acceptable (≥ 1.0 mM)' : freeMg >= 0.5 ? '⚠ Below optimal' : '✕ Critically low'}
          </span>
        </div>
      )}

      {/* Thermodynamic warnings */}
      {freeMgWarn              && <WarnBox text={freeMgWarn} />}
      {saltWarn                && <WarnBox text={saltWarn} />}
      {kPlusWarn               && <WarnBox text={kPlusWarn} />}
      {mgWarn                  && <WarnBox text={mgWarn} />}
      {!freeMgWarn && dntpWarn && <WarnBox text={dntpWarn} />}
      {primerCWarn             && <WarnBox text={primerCWarn} />}
      {phWarn                  && <WarnBox text={phWarn} />}
      {showIonicWarn && (
        <WarnBox text={`High ionic strength: [Na⁺] ${salt} mM + [Mg²⁺] ${mg} mM — actual Tm may be significantly higher than the Na⁺-only correction predicts.`} />
      )}
      {showFwdTmWarn && (
        <WarnBox text={`Tm target may be difficult to achieve: the 12-nt miRNA binding region contributes only ~${seqAnalysis.fwdRegionTm}°C. Reaching ${thermoData.tmMin}°C requires the 5′ tail to add ~${fwdTmDeficit}°C. Consider lowering Tm min to ${thermoData.tmMin - 5}–${thermoData.tmMin - 3}°C.`} />
      )}

      {/* ══ 3. ADVANCED SPECIFICITY ════════════════════════════════════════ */}

      <SubDivider label="Specificity" />

      <div className="space-y-2">
        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-teal-700 transition-colors"
        >
          <span className={`text-teal-600 font-bold text-sm leading-none transition-transform duration-200 ${showAdvanced ? 'rotate-90' : ''}`}>
            ▸
          </span>
          Advanced specificity options
        </button>

        <Reveal show={showAdvanced}>
          <div className="space-y-2 pl-3 border-l-2 border-teal-100 mt-1">
            {[
              {
                key: 'enableFamilyDiscrimination',
                label: 'Penalize off-target in same miRNA family',
                tooltip: 'The algorithm penalizes primer candidates whose 3′ overhang could cross-react with a related family member. Especially important for the let-7 family (13 members, many differing by only 1–2 nt).',
              },
              {
                key: 'enablePrecursorCheck',
                label: 'Check cross-reactivity with pre-miRNA',
                tooltip: 'Normally, steric hindrance of the stem-loop structure prevents binding to pre-miRNA. Enable only when there is specific reason to expect high pre-miRNA levels.',
              },
              {
                key: 'enableRefoldingProtocol',
                label: 'Generate re-folding protocol in output',
                tooltip: 'The output will include a thermal re-folding protocol to ensure the stem-loop primer adopts the correct hairpin conformation: 95°C 10 min → slow cool → hold at 60°C.',
              },
            ].map(({ key, label, tooltip }) => (
              <label key={key} className="flex items-start gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={specData[key]}
                  onChange={(e) => onSpecChange(key, e.target.checked)}
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
