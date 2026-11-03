/**
 * ParameterEditor — every design parameter, in one component.
 *
 * Rendered in two places: folded away under the miRNA input on /design, and in
 * the "Adjust parameters" bar on /results. Using the same component in both is
 * what keeps the two pages in step — a parameter added here appears in both.
 *
 * Each group is its own collapsible section, so the editor stays short until
 * the user opens the part they care about. `openRequests` opens groups
 * programmatically ({ constraints: 1 } opens Primer Design Constraints).
 */
import PrimerConstraintsGroup from '../pages/SearchPage/PrimerConstraintsGroup.jsx';
import DetectionMethodGroup from '../pages/SearchPage/DetectionMethodGroup.jsx';
import QpcrConditionsGroup from '../pages/SearchPage/QpcrConditionsGroup.jsx';
import ExperimentalContextGroup from '../pages/SearchPage/ExperimentalContextGroup.jsx';

export default function ParameterEditor({
  params,
  errors = {},
  onChange,          // (group, field, value)
  onError,           // (field, message | null)
  onApplyPreset,     // (preset)
  seqAnalysis = null,
  openRequests = {},
}) {
  const set = (group) => (field, value) => onChange(group, field, value);

  return (
    <div className="space-y-3">
      <PrimerConstraintsGroup
        data={params.primerConstraints}
        onChange={set('primerConstraints')}
        seqAnalysis={seqAnalysis}
        mirnaFamily={params.sequence?.family}
        thermoData={params.thermodynamic}
        thermoErrors={{
          saltConcentration:      errors.saltConcentration,
          primerConcentration:    errors.primerConcentration,
          magnesiumConcentration: errors.magnesiumConcentration,
          dntpTotal:              errors.dntpTotal,
          kPlusConc:              errors.kPlusConc,
          bufferPH:               errors.bufferPH,
        }}
        onThermoChange={set('thermodynamic')}
        onThermoError={onError}
        openRequested={openRequests.constraints || 0}
      />
      <QpcrConditionsGroup
        data={params.qpcr}
        errors={errors}
        onChange={set('qpcr')}
        onError={onError}
        tmMin={params.thermodynamic.tmMin}
        openRequested={openRequests.qpcr || 0}
      />
      <DetectionMethodGroup
        data={params.detectionMethod}
        onChange={set('detectionMethod')}
        seqAnalysis={seqAnalysis}
        openRequested={openRequests.method || 0}
      />
      <ExperimentalContextGroup
        data={params.experimentalContext}
        onChange={set('experimentalContext')}
        onApplyPreset={onApplyPreset}
        openRequested={openRequests.context || 0}
      />
    </div>
  );
}
