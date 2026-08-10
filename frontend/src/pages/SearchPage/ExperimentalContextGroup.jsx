import { useState } from 'react';
import Tooltip from '../../components/ui/Tooltip.jsx';
import CollapsibleSection from '../../components/ui/CollapsibleSection.jsx';
import { SAMPLE_TYPE_PRESETS, QPCR_SYSTEM_NOTES } from '../../constants/defaults.js';

const SAMPLE_OPTIONS = [
  { value: 'tissue', label: 'Tissue' },
  { value: 'cell',   label: 'Cell culture' },
  { value: 'serum',  label: 'Serum' },
  { value: 'plasma', label: 'Plasma' },
  { value: 'ffpe',   label: 'FFPE' },
  { value: 'urine',  label: 'Urine' },
];

const QPCR_SYSTEM_OPTIONS = [
  { value: 'abi',    label: 'ABI / Applied Biosystems' },
  { value: 'biorad', label: 'Bio-Rad CFX' },
  { value: 'roche',  label: 'Roche LightCycler' },
  { value: 'qiagen', label: 'Qiagen Rotor-Gene' },
  { value: 'other',  label: 'Other' },
];


const EXPORT_OPTIONS = [
  { value: 'copy', label: 'Copy to clipboard' },
  { value: 'pdf',  label: 'PDF report' },
  { value: 'csv',  label: 'CSV for ordering' },
];

export default function ExperimentalContextGroup({ data, onChange, onApplyPreset, onFirstOpen, openRequested }) {
  const [presetDismissed, setPresetDismissed] = useState(false);
  const [prevSample, setPrevSample] = useState(data.sampleType); // eslint-disable-line no-unused-vars

  function handleSampleChange(e) {
    const val = e.target.value;
    onChange('sampleType', val);
    setPresetDismissed(false);
    setPrevSample(val);
  }

  function handleExportToggle(value) {
    const current = data.exportFormat;
    const next = current.includes(value)
      ? current.filter((v) => v !== value)
      : [...current, value];
    onChange('exportFormat', next);
  }

  const preset = SAMPLE_TYPE_PRESETS[data.sampleType] || {};
  const hasPresetChanges = !presetDismissed && (preset.ampliconMax || preset.primerConcentration);
  const sampleWarning = preset.warning || '';

  const systemNote = QPCR_SYSTEM_NOTES[data.qpcrSystem];

  const hasWarning = hasPresetChanges || !!sampleWarning;

  return (
    <CollapsibleSection
      title="Experimental Context"
      tooltip="Experimental context does not affect the core primer design algorithm but adjusts recommendations in the output section."
      accent="purple"
      hasWarning={hasWarning}
      onFirstOpen={onFirstOpen}
      openRequested={openRequested}
    >
      {/* Sample type + qPCR system */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-1.5">
            <label className="text-sm font-medium text-gray-700">Sample type</label>
            <Tooltip text="Sample type affects optimal amplicon size, primer concentration, and reference gene selection. Serum and FFPE samples require shorter amplicons due to RNA fragmentation." />
          </div>
          <select
            value={data.sampleType}
            onChange={handleSampleChange}
            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 text-gray-900 focus:outline-none focus:border-teal-300 focus:ring-1 focus:ring-teal-100 bg-white"
          >
            {SAMPLE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-1.5">
            <label className="text-sm font-medium text-gray-700">qPCR system</label>
            <Tooltip text="Your qPCR platform affects the choice of reference dye (ROX or none), reaction volume, and compatible master mix." />
          </div>
          <select
            value={data.qpcrSystem}
            onChange={(e) => onChange('qpcrSystem', e.target.value)}
            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 text-gray-900 focus:outline-none focus:border-teal-300 focus:ring-1 focus:ring-teal-100 bg-white"
          >
            {QPCR_SYSTEM_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Preset banner */}
      {hasPresetChanges && (
        <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 space-y-1.5">
          <p className="font-medium">Special sample type detected. Recommended adjustments:</p>
          <ul className="list-disc list-inside space-y-0.5 text-amber-600">
            {preset.ampliconMax && <li>Amplicon size max → {preset.ampliconMax} bp</li>}
            {preset.ampliconMin && <li>Amplicon size min → {preset.ampliconMin} bp</li>}
            {preset.primerConcentration && <li>Primer concentration → {preset.primerConcentration} nM</li>}
          </ul>
          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={() => { onApplyPreset(preset); setPresetDismissed(true); }}
              className="px-3 py-1 rounded bg-amber-600 text-white text-xs font-medium hover:bg-amber-700 transition-colors"
            >
              Apply
            </button>
            <button
              type="button"
              onClick={() => setPresetDismissed(true)}
              className="px-3 py-1 rounded border border-amber-300 text-amber-700 text-xs font-medium hover:bg-amber-50 transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Sample warning (no preset adjustments, just a note) */}
      {!hasPresetChanges && sampleWarning && (
        <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
          {sampleWarning}
        </p>
      )}

      {/* System note */}
      {systemNote && (
        <p className="text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 leading-relaxed">
          {systemNote}
        </p>
      )}

      {/* Export format */}
      <div className="space-y-2">
        <div className="flex items-center gap-1.5">
          <label className="text-sm font-medium text-gray-700">Export format</label>
          <Tooltip text="CSV format is suitable for submitting directly to oligo synthesis vendors. PDF is ideal for lab notebooks or sharing with collaborators." />
        </div>
        <div className="flex gap-4">
          {EXPORT_OPTIONS.map(({ value, label }) => (
            <label key={value} className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={data.exportFormat.includes(value)}
                onChange={() => handleExportToggle(value)}
                className="accent-teal-600"
              />
              <span className="text-sm text-gray-700">{label}</span>
            </label>
          ))}
        </div>
      </div>
    </CollapsibleSection>
  );
}
