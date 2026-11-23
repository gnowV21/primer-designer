// FamilySpecificityMap — Phase 7 PART C (UX A3 ★★★)
// SVG radial specificity map for family cross-reactivity.
// Reads data from response family_cross_reactivity — does NOT call backend.
// No chart libraries — pure SVG + JS.

import { useState } from 'react';
import Tooltip from './ui/Tooltip.jsx';

// Risk → visual properties (consistent with RISK_STYLE in ResultsSection/index.jsx)
const RISK_CONFIG = {
  IDENTICAL: { color: '#B91C1C', bg: '#FEF2F2', border: '#FCA5A5', label: 'Identical', shape: '◆', radiusFrac: 0.13 },
  HIGH:      { color: '#C2410C', bg: '#FFF7ED', border: '#FDBA74', label: 'High',      shape: '▲', radiusFrac: 0.35 },
  LOW:       { color: '#B45309', bg: '#FFFBEB', border: '#FCD34D', label: 'Low',       shape: '●', radiusFrac: 0.62 },
  SAFE:      { color: '#15803D', bg: '#F0FDF4', border: '#86EFAC', label: 'Safe',      shape: '●', radiusFrac: 0.85 },
};

const HIGH_ZONE_FRAC   = 0.48;  // dashed ring separating HIGH and LOW zones
const CENTER_R         = 18;    // target circle radius (px)
const SIBLING_R        = 7;     // sibling dot radius
const SVG_SIZE         = 300;   // viewBox size; drawn at about this many px so text stays ≥ 11 px
const MAX_RADIUS       = (SVG_SIZE / 2) - SIBLING_R - 12;
const CX               = SVG_SIZE / 2;
const CY               = SVG_SIZE / 2;

function polarToXY(angle, r) {
  const rad = (angle - 90) * (Math.PI / 180); // 0° at top
  return { x: CX + r * Math.cos(rad), y: CY + r * Math.sin(rad) };
}

// Provenance badge
function ProvenanceBadge({ provenance, canonical }) {
  if (canonical) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded border bg-slate-50 border-slate-200 text-slate-700">
        miRBase family (canonical)
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded border bg-slate-50 border-slate-200 text-slate-700">
      Family grouping is seed-based (approximate)
      <Tooltip text="miRNAs are grouped by their 7-nt seed (positions 2–8), not by a curated family list." />
    </span>
  );
}

// Tooltip state management (hover per sibling)
function SiblingDot({ sibling, cx, cy, config, isActive, onActivate, onDeactivate }) {
  const fillColor = isActive ? config.color : config.bg;
  const strokeColor = config.color;

  return (
    <g
      role="img"
      aria-label={`${sibling.sibling}: ${config.label.toLowerCase()} risk, ${sibling.mismatch} ${sibling.mismatch === 1 ? 'mismatch' : 'mismatches'}`}
      onMouseEnter={onActivate}
      onMouseLeave={onDeactivate}
      onFocus={onActivate}
      onBlur={onDeactivate}
      tabIndex={0}
      style={{ cursor: 'pointer', outline: 'none' }}
    >
      <title>
        {sibling.sibling}: {config.label} risk, {sibling.mismatch} mismatch, ΔTm {sibling.delta_tm > 0 ? '+' : ''}{sibling.delta_tm} °C, overhang {sibling.sibling_overhang}
      </title>
      <circle
        cx={cx}
        cy={cy}
        r={SIBLING_R}
        fill={fillColor}
        stroke={strokeColor}
        strokeWidth={isActive ? 2.5 : 1.5}
      />
    </g>
  );
}

function MapView({ data }) {
  const [active, setActive] = useState(null);

  const siblings = data.cross_reactivity || [];
  const targetOverhang = data.target_overhang || '';
  const n = siblings.length;

  // Compute positions
  const positions = siblings.map((s, i) => {
    const cfg = RISK_CONFIG[s.risk] || RISK_CONFIG.SAFE;
    const angle = n === 1 ? 0 : (360 / n) * i;
    // Add slight radial jitter per index to avoid exact overlap
    const jitter = ((i % 3) - 1) * 0.04;
    const r = Math.max(CENTER_R + SIBLING_R + 4, (cfg.radiusFrac + jitter) * MAX_RADIUS);
    const { x, y } = polarToXY(angle, r);
    return { ...s, x, y, cfg, angle };
  });

  const highZoneR   = HIGH_ZONE_FRAC * MAX_RADIUS;
  const dangerZoneR = RISK_CONFIG.HIGH.radiusFrac * MAX_RADIUS;

  const activeData = active !== null ? positions[active] : null;

  return (
    <div className="relative flex flex-col items-center gap-3">
      <svg
        viewBox={`0 0 ${SVG_SIZE} ${SVG_SIZE}`}
        width={SVG_SIZE}
        height={SVG_SIZE}
        className="max-w-full h-auto"
        aria-label="Radial family specificity map — center is the target miRNA; siblings are positioned by cross-reactivity risk"
        role="img"
      >
        <title>Seed family map</title>

        {/* Outer safe ring guide (dashed) */}
        <circle cx={CX} cy={CY} r={MAX_RADIUS} fill="none" stroke="#E2E8F0" strokeWidth="1" strokeDasharray="4 3" />

        {/* HIGH-zone boundary ring (dashed, amber) */}
        <circle cx={CX} cy={CY} r={highZoneR} fill="none" stroke="#FCD34D" strokeWidth="1.5" strokeDasharray="5 4" />

        {/* Danger zone fill (IDENTICAL+HIGH zone) */}
        <circle cx={CX} cy={CY} r={dangerZoneR} fill="#FEF2F2" fillOpacity="0.4" stroke="none" />

        {/* Zone labels */}
        <text x={CX} y={CY - highZoneR - 4} textAnchor="middle" fontSize="11" fill="#92400E">High-risk zone</text>

        {/* Target center */}
        <circle cx={CX} cy={CY} r={CENTER_R + 6} fill="#EFF3FB" stroke="#273E74" strokeWidth={2} />
        <text x={CX} y={CY} textAnchor="middle" dominantBaseline="central" fontSize="11" fill="#1C2E54" fontWeight="bold">
          Target
        </text>
        {targetOverhang && (
          <text x={CX} y={CY + CENTER_R + 13} textAnchor="middle" fontSize="11" fill="#334155" fontFamily="monospace">
            {targetOverhang}
          </text>
        )}

        {/* Sibling dots */}
        {positions.map((p, i) => (
          <SiblingDot
            key={p.sibling}
            sibling={p}
            cx={p.x}
            cy={p.y}
            config={p.cfg}
            isActive={active === i}
            onActivate={() => setActive(i)}
            onDeactivate={() => setActive(null)}
          />
        ))}
      </svg>

      {/* Tooltip panel for active sibling */}
      {activeData && (
        <div className="w-full max-w-xs rounded-lg border border-slate-200 bg-white px-3 py-2 space-y-1 text-xs shadow-sm">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-800 whitespace-nowrap">{activeData.sibling}</span>
            <span
              className="font-bold px-2 py-0.5 rounded-full border text-xs"
              style={{ color: activeData.cfg.color, borderColor: activeData.cfg.border, background: activeData.cfg.bg }}
            >
              {activeData.cfg.shape} {activeData.cfg.label}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-slate-700">
            <span>Overhang</span>
            <span className="seq">{activeData.sibling_overhang}</span>
            <span>Mismatches</span>
            <span>{activeData.mismatch}</span>
            <span>ΔTm</span>
            <span className="whitespace-nowrap">{activeData.delta_tm > 0 ? '+' : ''}{activeData.delta_tm}{'\u00a0'}°C</span>
            {activeData.kwok_distance != null && (
              <>
                <span>Kwok distance</span>
                <span>{activeData.kwok_distance}</span>
              </>
            )}
          </div>
          {/* Highlight mismatched positions in overhang */}
          {activeData.sibling_overhang
            && activeData.sibling_overhang.length === (data.target_overhang || '').length && (
            <div className="mt-1 text-xs">
              <span className="text-slate-700 mr-1">vs target:</span>
              {(data.target_overhang || '').split('').map((nt, idx) => {
                const sib = activeData.sibling_overhang[idx] || '';
                const mismatch = nt !== sib;
                return (
                  <span key={idx} className={`seq ${mismatch ? 'font-bold text-red-700' : 'text-slate-600'}`}>
                    {sib}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Risk legend */}
      <div className="flex flex-wrap gap-2 justify-center text-xs">
        {Object.entries(RISK_CONFIG).map(([risk, cfg]) => (
          <span key={risk} className="flex items-center gap-1 px-1.5 py-0.5 rounded border"
            style={{ color: cfg.color, borderColor: cfg.border, background: cfg.bg }}>
            {cfg.shape} {cfg.label}
          </span>
        ))}
        <span className="flex items-center gap-1 px-1.5 py-0.5 rounded border border-amber-200 bg-amber-50 text-amber-800">
          Dashed ring: high-risk zone boundary
        </span>
      </div>
    </div>
  );
}

// Seed-similarity vocabulary — deliberately NOT the primer "risk" vocabulary. Seed
// closeness is a biological (mRNA-targeting) signal, not a primer specificity verdict.
const SEED_SIMILARITY = {
  IDENTICAL: { label: 'identical 3′', style: 'text-slate-700 bg-slate-100 border-slate-300' },
  HIGH:      { label: 'near',         style: 'text-slate-700 bg-slate-50 border-slate-200' },
  LOW:       { label: 'near',         style: 'text-slate-700 bg-slate-50 border-slate-200' },
  SAFE:      { label: 'distant',      style: 'text-slate-700 bg-white border-slate-200' },
};

function TableView({ data }) {
  const siblings = data.cross_reactivity || [];

  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      {siblings.length === 0 ? (
        <p className="px-3 py-3 text-xs text-green-700">
          No close family member (every member differs at 3 or more overhang positions).
        </p>
      ) : (
        <table className="w-full text-xs">
          <thead className="bg-slate-100 border-b border-slate-200">
            <tr>
              <th className="text-left px-3 py-1.5 font-semibold text-slate-700">Sibling</th>
              <th className="text-center px-2 py-1.5 font-semibold text-slate-700">Overhang</th>
              <th className="text-center px-2 py-1.5 font-semibold text-slate-700">Mismatches</th>
              <th className="text-center px-2 py-1.5 font-semibold text-slate-700">ΔTm</th>
              <th className="text-center px-2 py-1.5 font-semibold text-slate-700">Seed similarity</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {siblings.map((s) => {
              const sim = SEED_SIMILARITY[s.risk] ?? SEED_SIMILARITY.SAFE;
              return (
              <tr key={s.sibling}>
                <td className="px-3 py-1.5 text-slate-800 whitespace-nowrap">{s.sibling}</td>
                <td className="px-2 py-1.5 text-center seq text-slate-700">{s.sibling_overhang}</td>
                <td className="px-2 py-1.5 text-center tabular-nums text-slate-700">{s.mismatch}</td>
                <td className="px-2 py-1.5 text-center tabular-nums text-slate-700 whitespace-nowrap">
                  {s.delta_tm > 0 ? '+' : ''}{s.delta_tm}{'\u00a0'}°C
                </td>
                <td className="px-2 py-1.5 text-center">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${sim.style}`}>
                    {sim.label}
                  </span>
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function FamilySpecificityMap({ familyCrossReactivity, seed = '', hideTitle = false }) {
  // Table first: the map carries little when there are one or two siblings.
  const [view, setView] = useState('table'); // 'map' | 'table'

  if (!familyCrossReactivity) return null;

  const {
    family,
    species,
    cross_reactivity = [],
    cross_species_excluded = 0,
    target_overhang,
    overhang_used,
    data_provenance = {},
  } = familyCrossReactivity;

  const SPECIES_LABEL = { hsa: 'Human', mmu: 'Mouse', rno: 'Rat' };

  const noFamilyData = !family || (cross_reactivity.length === 0 && !target_overhang);

  return (
    <div className="space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          {/* The API family label is an auto-generated cluster ID ("miR-1" for the miR-15/16
              seed AGCAGCA); the group is named by its seed instead. */}
          <p className="text-xs font-semibold text-slate-700">
            {hideTitle ? '' : 'Seed family (biological context): '}
            {seed ? `Seed group ${seed}` : (family || 'Seed group')}
            <span className="ml-1.5 font-normal text-slate-600 whitespace-nowrap">
              ({overhang_used}-nt overhang)
            </span>
          </p>
          {species && (
            <span className="inline-flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded border bg-slate-50 border-slate-200 text-slate-700"
              title={`Cross-reactivity scoped to ${SPECIES_LABEL[species] || species} (${species}). Same-family orthologs in other species are not off-targets for a single-species sample.`}>
              {SPECIES_LABEL[species] || species}
              {cross_species_excluded > 0 && (
                <span className="text-slate-700">· {cross_species_excluded} other-species members excluded</span>
              )}
            </span>
          )}
          <ProvenanceBadge
            provenance={data_provenance.provenance}
            canonical={data_provenance.canonical}
          />
        </div>
        {/* Map / Table toggle */}
        {!noFamilyData && (
          <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
            <button
              type="button"
              onClick={() => setView('map')}
              aria-pressed={view === 'map'}
              className={`px-2.5 py-1 font-medium transition-colors ${view === 'map' ? 'bg-teal-600 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'}`}
            >
              Map
            </button>
            <button
              type="button"
              onClick={() => setView('table')}
              aria-pressed={view === 'table'}
              className={`px-2.5 py-1 font-medium transition-colors border-l border-slate-200 ${view === 'table' ? 'bg-teal-600 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'}`}
            >
              Table
            </button>
          </div>
        )}
      </div>

      {/* Fixed axis-clarification line (cannot be hidden) */}
      <p className="text-xs text-slate-700">
        Seed grouping (positions 2–8) is the mRNA-targeting axis. It does not decide primer
        specificity: see <span className="font-medium">Assay specificity</span> above. Listed: members within
        2 mismatches of the RT overhang; members that differ at 3 or more positions are not listed.
      </p>

      {/* Empty state */}
      {noFamilyData ? (
        <p className="text-xs text-slate-700">
          No family member found: the target looks unique in its seed group.
        </p>
      ) : cross_reactivity.length === 0 ? (
        <p className="text-xs text-green-700">
          No close sibling: every member differs at 3 or more positions of the {overhang_used}-nt overhang.
        </p>
      ) : (
        <>
          {view === 'map' ? (
            <MapView data={familyCrossReactivity} />
          ) : (
            <TableView data={familyCrossReactivity} />
          )}
        </>
      )}

      {/* Recommendation moved to OverhangCollisionPanel (primer-binding axis). The
          recommendation data stays in the API for back-compat but is not shown here. */}

      {/* The data warning repeats the "seed-based (approximate)" badge: not shown again. */}
    </div>
  );
}
