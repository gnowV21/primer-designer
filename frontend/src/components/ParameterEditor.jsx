/**
 * ParameterEditor — every design parameter, in one component.
 *
 * Rendered in two places: folded away under the miRNA input on /design, and in
 * the "Adjust parameters" bar on /results. Using the same component in both is
 * what keeps the two pages in step — a parameter added here appears in both.
 *
 * Grouped by what a parameter does in the tiered engine (2026-11-22,
 * docs/REVIEW_panel_4.0.0.md §13): Required (hard limits), Flexible (changes the
 * Flexible scores: standard primer rules, Ta, reaction conditions), Assay setup
 * (not used by the ranking), then Detection Method and Experimental Context as before.
 * Field names, form groups and defaults are unchanged.
 *
 * Each group is its own collapsible section, so the editor stays short until the user
 * opens the part they care about. `openRequests` opens groups programmatically
 * ({ required: 1 } — or the older key `constraints` — opens Required).
 */
import RequiredGroup from '../pages/SearchPage/RequiredGroup.jsx';
import FlexibleGroup from '../pages/SearchPage/FlexibleGroup.jsx';
import AssaySetupGroup from '../pages/SearchPage/AssaySetupGroup.jsx';
import DetectionMethodGroup from '../pages/SearchPage/DetectionMethodGroup.jsx';
import ExperimentalContextGroup from '../pages/SearchPage/ExperimentalContextGroup.jsx';
import { SectionsOpenByDefault } from './ui/CollapsibleSection.jsx';

export default function ParameterEditor({
  params,
  errors = {},
  onChange,          // (group, field, value)
  onError,           // (field, message | null)
  onApplyPreset,     // (preset)
  seqAnalysis = null,
  openRequests = {},
  groupsOpen = false, // /design: every group open once Parameters is open
}) {
  const set = (group) => (field, value) => onChange(group, field, value);
  const thermoErrors = {
    saltConcentration:      errors.saltConcentration,
    primerConcentration:    errors.primerConcentration,
    magnesiumConcentration: errors.magnesiumConcentration,
    dntpTotal:              errors.dntpTotal,
    kPlusConc:              errors.kPlusConc,
    bufferPH:               errors.bufferPH,
  };

  return (
    <SectionsOpenByDefault.Provider value={groupsOpen}>
    <div className="space-y-3">
      <RequiredGroup
        constraints={params.primerConstraints}
        onConstraintChange={set('primerConstraints')}
        thermoData={params.thermodynamic}
        onThermoChange={set('thermodynamic')}
        qpcrData={params.qpcr}
        onQpcrChange={set('qpcr')}
        seqAnalysis={seqAnalysis}
        mirnaFamily={params.sequence?.family}
        openRequested={openRequests.required || openRequests.constraints || 0}
      />
      <FlexibleGroup
        constraints={params.primerConstraints}
        onConstraintChange={set('primerConstraints')}
        seqAnalysis={seqAnalysis}
        thermoData={params.thermodynamic}
        thermoErrors={thermoErrors}
        onThermoChange={set('thermodynamic')}
        onThermoError={onError}
        qpcrData={params.qpcr}
        qpcrErrors={{ annealingTemp: errors.annealingTemp }}
        onQpcrChange={set('qpcr')}
        onQpcrError={onError}
        openRequested={openRequests.flexible || 0}
      />
      <AssaySetupGroup
        constraints={params.primerConstraints}
        onConstraintChange={set('primerConstraints')}
        qpcrData={params.qpcr}
        errors={errors}
        onQpcrChange={set('qpcr')}
        onError={onError}
        openRequested={openRequests.assay || 0}
      />
      <DetectionMethodGroup
        data={params.detectionMethod}
        onChange={set('detectionMethod')}
        seqAnalysis={seqAnalysis}
        targetName={params.sequence?.mirnaName}
        openRequested={openRequests.method || 0}
      />
      <ExperimentalContextGroup
        data={params.experimentalContext}
        onChange={set('experimentalContext')}
        onApplyPreset={onApplyPreset}
        openRequested={openRequests.context || 0}
      />
    </div>
    </SectionsOpenByDefault.Provider>
  );
}
