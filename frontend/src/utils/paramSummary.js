/**
 * paramSummary — how design parameters are described to the user.
 *
 * One table of labels/units drives three things, so they always agree:
 *   - the compact chips that summarise a parameter set ("6 nt overhang · Na⁺ 50 mM"),
 *   - the change list next to the Re-run button ("Overhang 6 nt → 7 nt"),
 *   - the label of each run in the run switcher.
 */
import { DEFAULTS } from '../constants/defaults.js';

const onOff = (v) => (v ? 'on' : 'off');

const SAMPLE_LABELS = {
  tissue: 'Tissue', cell: 'Cell culture', serum: 'Serum',
  plasma: 'Plasma', ffpe: 'FFPE', urine: 'Urine',
};

/** Every editable field: label, unit and an optional value formatter. */
const FIELDS = {
  thermodynamic: {
    tmMin:                  { label: 'Tm min', unit: '°C' },
    tmMax:                  { label: 'Tm max', unit: '°C' },
    saltConcentration:      { label: 'Na⁺', unit: 'mM' },
    primerConcentration:    { label: 'Primer', unit: 'nM' },
    magnesiumConcentration: { label: 'Mg²⁺', unit: 'mM' },
    dntpTotal:              { label: 'dNTP', unit: 'mM' },
    kPlusConc:              { label: 'K⁺', unit: 'mM' },
    bufferPH:               { label: 'pH', unit: '' },
  },
  primerConstraints: {
    gcMin:               { label: 'GC min', unit: '%' },
    gcMax:               { label: 'GC max', unit: '%' },
    lengthMin:           { label: 'Length min', unit: 'nt' },
    lengthMax:           { label: 'Length max', unit: 'nt' },
    gcClamp3prime:       { label: 'GC clamp', unit: '', fmt: onOff },
    bindingRegion3prime: { label: 'Overhang', unit: 'nt' },
  },
  qpcr: {
    annealingTemp:    { label: 'Ta', unit: '°C' },
    ampliconMin:      { label: 'Amplicon min', unit: 'bp' },
    ampliconMax:      { label: 'Amplicon max', unit: 'bp' },
    totalCycles:      { label: 'Cycles', unit: '' },
    pcrEfficiencyMin: { label: 'Efficiency min', unit: '%' },
    pcrEfficiencyMax: { label: 'Efficiency max', unit: '%' },
  },
  detectionMethod: {
    signalMethod:            { label: 'Chemistry', unit: '', fmt: (v) => (v === 'sybr' ? 'SYBR Green' : 'TaqMan') },
    quantMode:               { label: 'Quantification', unit: '' },
    referenceGene:           { label: 'Reference', unit: '' },
    customReferenceGene:     { label: 'Custom reference', unit: '' },
    enableRefoldingProtocol: { label: 'Refolding', unit: '', fmt: onOff },
  },
  experimentalContext: {
    sampleType: { label: 'Sample', unit: '', fmt: (v) => SAMPLE_LABELS[v] || v },
    qpcrSystem: { label: 'qPCR system', unit: '' },
  },
};

/** Groups the user edits. `sequence` is the target itself, not a parameter. */
export const PARAM_GROUPS = Object.keys(FIELDS);

export function formatValue(group, field, value) {
  const spec = FIELDS[group]?.[field];
  if (value === '' || value === null || value === undefined) return '—';
  if (!spec) return String(value);
  const text = spec.fmt ? spec.fmt(value) : String(value);
  return spec.unit ? `${text} ${spec.unit}` : text;
}

/** The handful of knobs worth showing at a glance — what users turn after a poor result. */
export function summarizeParams(p) {
  if (!p) return [];
  const v = (group, field) => formatValue(group, field, p[group]?.[field]);
  // `path` matches diffParams() entries, so a chip can be highlighted when its value changed.
  return [
    { path: 'detectionMethod.signalMethod',            text: v('detectionMethod', 'signalMethod') },
    { path: 'experimentalContext.sampleType',          text: v('experimentalContext', 'sampleType') },
    { path: 'primerConstraints.bindingRegion3prime',   text: `${v('primerConstraints', 'bindingRegion3prime')} overhang` },
    { path: 'thermodynamic.saltConcentration',         text: `Na⁺ ${v('thermodynamic', 'saltConcentration')}` },
    { path: 'thermodynamic.magnesiumConcentration',    text: `Mg²⁺ ${v('thermodynamic', 'magnesiumConcentration')}` },
    { path: 'qpcr.annealingTemp',                      text: `Ta ${v('qpcr', 'annealingTemp')}` },
  ];
}

/** "group.field" keys of a diffParams() result — for highlighting chips. */
export function changedPaths(changes) {
  return new Set(changes.map((c) => `${c.group}.${c.field}`));
}

const same = (a, b) => String(a ?? '') === String(b ?? '');

/** Every editable field whose value differs between two parameter sets. */
export function diffParams(base, next) {
  const out = [];
  for (const group of PARAM_GROUPS) {
    for (const field of Object.keys(FIELDS[group])) {
      const from = base?.[group]?.[field];
      const to = next?.[group]?.[field];
      if (!same(from, to)) {
        out.push({
          group, field,
          label: FIELDS[group][field].label,
          from: formatValue(group, field, from),
          to: formatValue(group, field, to),
        });
      }
    }
  }
  return out;
}

/** Fresh copies of the documented defaults for every parameter group. */
export function defaultParams() {
  return Object.fromEntries(PARAM_GROUPS.map((g) => [g, { ...DEFAULTS[g] }]));
}

/**
 * Apply a SAMPLE_TYPE_PRESETS entry (amplicon window, primer concentration) to a
 * parameter set. Returns `prev` unchanged if the preset would invert the window.
 */
export function applySamplePreset(prev, preset) {
  const nextMin = preset.ampliconMin !== undefined ? preset.ampliconMin : prev.qpcr.ampliconMin;
  const nextMax = preset.ampliconMax !== undefined ? preset.ampliconMax : prev.qpcr.ampliconMax;
  if (nextMin >= nextMax) return prev;
  return {
    ...prev,
    qpcr: { ...prev.qpcr, ampliconMin: nextMin, ampliconMax: nextMax },
    thermodynamic: {
      ...prev.thermodynamic,
      ...(preset.primerConcentration !== undefined && { primerConcentration: preset.primerConcentration }),
    },
  };
}
