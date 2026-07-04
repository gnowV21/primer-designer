// FamilySpecificityMap — Phase 7 PART C (UX A3 ★★★)
// SVG radial specificity map for family cross-reactivity.
// Reads data from response family_cross_reactivity — does NOT call backend.
// No chart libraries — pure SVG + JS.

import { useState } from 'react';
import Tooltip from './ui/Tooltip.jsx';

// Risk → visual properties (consistent with RISK_STYLE in ResultsSection/index.jsx)
const RISK_CONFIG = {
  IDENTICAL: { color: '#B91C1C', bg: '#FEF2F2', border: '#FCA5A5', label: 'IDENTICAL', shape: '◆', radiusFrac: 0.13 },
  HIGH:      { color: '#C2410C', bg: '#FFF7ED', border: '#FDBA74', label: 'HIGH',      shape: '▲', radiusFrac: 0.35 },
  LOW:       { color: '#B45309', bg: '#FFFBEB', border: '#FCD34D', label: 'LOW',       shape: '●', radiusFrac: 0.62 },
  SAFE:      { color: '#0F766E', bg: '#F0FDF9', border: '#5EEAD4', label: 'SAFE',      shape: '●', radiusFrac: 0.85 },
};

const HIGH_ZONE_FRAC   = 0.48;  // dashed ring separating HIGH and LOW zones
const CENTER_R         = 18;    // target circle radius (px)
const SIBLING_R        = 7;     // sibling dot radius
const SVG_SIZE         = 340;   // viewBox size (px, square)
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
      <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded border bg-teal-50 border-teal-200 text-teal-700">
        miRBase family (canonical)
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded border bg-amber-50 border-amber-200 text-amber-700">
      Seed-based grouping (approximate)
      <Tooltip text="Canonical miFam.dat source unavailable. Family grouping based on 7-nt seed sequence (positions 2-8). Re-run scripts/build_family_db.py with FTP access for canonical data." />
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
      aria-label={`${sibling.sibling} — ${config.label} risk, ${sibling.mismatch} mismatch(es)`}
      onMouseEnter={onActivate}
      onMouseLeave={onDeactivate}
      onFocus={onActivate}
      onBlur={onDeactivate}
      tabIndex={0}
      style={{ cursor: 'pointer', outline: 'none' }}
    >
      <title>
        {sibling.sibling} | Risk: {config.label} | Mismatch: {sibling.mismatch} |
        ΔTm: {sibling.delta_tm > 0 ? '+' : ''}{sibling.delta_tm}°C |
        Overhang: {sibling.sibling_overhang}
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
        className="w-full max-w-xs"
        aria-label="Radial family specificity map — center is the target miRNA; siblings are positioned by cross-reactivity risk"
        role="img"
      >
        <title>Family Specificity Map</title>

        {/* Outer safe ring guide (dashed) */}
        <circle cx={CX} cy={CY} r={MAX_RADIUS} fill="none" stroke="#E2E8F0" strokeWidth="1" strokeDasharray="4 3" />

        {/* HIGH-zone boundary ring (dashed, amber) */}
        <circle cx={CX} cy={CY} r={highZoneR} fill="none" stroke="#FCD34D" strokeWidth="1.5" strokeDasharray="5 4" />

        {/* Danger zone fill (IDENTICAL+HIGH zone) */}
        <circle cx={CX} cy={CY} r={dangerZoneR} fill="#FEF2F2" fillOpacity="0.4" stroke="none" />

        {/* Zone labels */}
        <text x={CX + highZoneR + 4} y={CY - 3} fontSize="8" fill="#92400E" opacity="0.8">HIGH zone</text>
        <text x={CX + MAX_RADIUS + 3} y={CY - 3} fontSize="8" fill="#0F766E" opacity="0.7">SAFE</text>

        {/* Target center */}
        <circle cx={CX} cy={CY} r={CENTER_R} fill="#CCFBF1" stroke="#0F766E" strokeWidth={2} />
        <text x={CX} y={CY} textAnchor="middle" dominantBaseline="central" fontSize="8" fill="#0F6E56" fontWeight="bold">
          TARGET
        </text>
        {targetOverhang && (
          <text x={CX} y={CY + CENTER_R + 10} textAnchor="middle" fontSize="7" fill="#64748B" fontFamily="monospace">
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
            <span className="font-mono font-semibold text-slate-800">{activeData.sibling}</span>
            <span
              className="font-bold px-2 py-0.5 rounded-full border text-[11px]"
              style={{ color: activeData.cfg.color, borderColor: activeData.cfg.border, background: activeData.cfg.bg }}
            >
              {activeData.cfg.shape} {activeData.cfg.label}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-slate-600">
            <span>Overhang</span>
            <span className="font-mono">{activeData.sibling_overhang}</span>
            <span>Mismatch(es)</span>
            <span>{activeData.mismatch}</span>
            <span>ΔTm</span>
            <span>{activeData.delta_tm > 0 ? '+' : ''}{activeData.delta_tm}°C</span>
            {activeData.kwok_distance != null && (
              <>
                <span>Kwok dist.</span>
                <span>{activeData.kwok_distance}</span>
              </>
            )}
          </div>
          {/* Highlight mismatched positions in overhang */}
          {activeData.sibling_overhang && activeData.sibling_overhang.length === (data.overhang_used || 6) && (
            <div className="mt-1 font-mono text-[11px]">
              <span className="text-slate-400 mr-1">vs target:</span>
              {(data.target_overhang || '').split('').map((nt, idx) => {
                const sib = activeData.sibling_overhang[idx] || '';
                const mismatch = nt !== sib;
                return (
                  <span key={idx} className={mismatch ? 'font-bold text-red-600' : 'text-slate-500'}>
                    {sib}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Risk legend */}
      <div className="flex flex-wrap gap-2 justify-center text-[10px]">
        {Object.entries(RISK_CONFIG).map(([risk, cfg]) => (
          <span key={risk} className="flex items-center gap-1 px-1.5 py-0.5 rounded border"
            style={{ color: cfg.color, borderColor: cfg.border, background: cfg.bg }}>
            {cfg.shape} {cfg.label}
          </span>
        ))}
        <span className="flex items-center gap-1 px-1.5 py-0.5 rounded border border-amber-200 bg-amber-50 text-amber-700">
          - - HIGH zone boundary
        </span>
      </div>
    </div>
  );
}

function TableView({ data }) {
  const siblings = data.cross_reactivity || [];
  const RISK_STYLE = {
    IDENTICAL: 'text-red-700 bg-red-50 border-red-300',
    HIGH:      'text-orange-700 bg-orange-50 border-orange-300',
    LOW:       'text-amber-700 bg-amber-50 border-amber-200',
    SAFE:      'text-teal-700 bg-teal-50 border-teal-200',
  };

  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      {siblings.length === 0 ? (
        <p className="px-3 py-3 text-xs text-teal-700">
          No cross-reactive family members detected (Hamming distance ≥ 3 on overhang).
        </p>
      ) : (
        <table className="w-full text-xs">
          <thead className="bg-slate-100 border-b border-slate-200">
            <tr>
              <th className="text-left px-3 py-1.5 font-semibold text-slate-600">Sibling</th>
              <th className="text-center px-2 py-1.5 font-semibold text-slate-600">Overhang</th>
              <th className="text-center px-2 py-1.5 font-semibold text-slate-600">Mismatch</th>
              <th className="text-center px-2 py-1.5 font-semibold text-slate-600">ΔTm</th>
              <th className="text-center px-2 py-1.5 font-semibold text-slate-600">Risk</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {siblings.map((s) => (
              <tr key={s.sibling}>
                <td className="px-3 py-1.5 font-mono text-slate-700">{s.sibling}</td>
                <td className="px-2 py-1.5 text-center font-mono text-slate-600">{s.sibling_overhang}</td>
                <td className="px-2 py-1.5 text-center tabular-nums text-slate-600">{s.mismatch}</td>
                <td className="px-2 py-1.5 text-center tabular-nums text-slate-600">
                  {s.delta_tm > 0 ? '+' : ''}{s.delta_tm}°C
                </td>
                <td className="px-2 py-1.5 text-center">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${RISK_STYLE[s.risk] ?? ''}`}>
                    {s.risk}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function FamilySpecificityMap({ familyCrossReactivity }) {
  const [view, setView] = useState('map'); // 'map' | 'table'

  if (!familyCrossReactivity) return null;

  const {
    family,
    cross_reactivity = [],
    target_overhang,
    overhang_used,
    data_warning,
    data_provenance = {},
    recommendation,
  } = familyCrossReactivity;

  const noFamilyData = !family || (cross_reactivity.length === 0 && !target_overhang);
  const hasHighRisk = cross_reactivity.some((s) => s.risk === 'IDENTICAL' || s.risk === 'HIGH');

  return (
    <div className="space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
            Family Specificity
            {family && (
              <span className="ml-1.5 font-normal normal-case text-slate-500">
                ({family} · {overhang_used}-nt overhang)
              </span>
            )}
          </p>
          <ProvenanceBadge
            provenance={data_provenance.provenance}
            canonical={data_provenance.canonical}
          />
        </div>
        {/* Map / Table toggle */}
        {!noFamilyData && (
          <div className="flex rounded-lg border border-slate-200 overflow-hidden text-[11px]">
            <button
              type="button"
              onClick={() => setView('map')}
              className={`px-2.5 py-1 font-medium transition-colors ${
                view === 'map'
                  ? 'bg-teal-600 text-white'
                  : 'bg-white text-slate-600 hover:bg-slate-50'
              }`}
            >
              Map
            </button>
            <button
              type="button"
              onClick={() => setView('table')}
              className={`px-2.5 py-1 font-medium transition-colors border-l border-slate-200 ${
                view === 'table'
                  ? 'bg-teal-600 text-white'
                  : 'bg-white text-slate-600 hover:bg-slate-50'
              }`}
            >
              Table
            </button>
          </div>
        )}
      </div>

      {/* Empty state */}
      {noFamilyData ? (
        <p className="text-xs text-slate-500 italic">
          No family siblings found — target appears unique in this family set.
        </p>
      ) : cross_reactivity.length === 0 ? (
        <p className="text-xs text-teal-700">
          No cross-reactive siblings detected (all Hamming distances ≥ 3 on the {overhang_used}-nt overhang).
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

      {/* Recommendation */}
      {recommendation && hasHighRisk && (
        <div className="rounded-lg bg-white border border-slate-200 px-3 py-2 space-y-1">
          <p className="text-xs font-semibold text-slate-600">Recommendation</p>
          <p className="text-xs text-slate-600">{recommendation.reason}</p>
          {recommendation.off_label_warning && (
            <p className="text-xs text-amber-700 mt-1">⚠ {recommendation.off_label_warning}</p>
          )}
          {!recommendation.resolved && recommendation.remaining_high_risk_siblings?.length > 0 && (
            <p className="text-xs text-red-700">
              Unresolved at max overhang: {recommendation.remaining_high_risk_siblings.join(', ')}
            </p>
          )}
        </div>
      )}

      {/* Data warning */}
      {data_warning && (
        <p className="text-[10px] text-slate-400 italic">{data_warning}</p>
      )}
    </div>
  );
}
