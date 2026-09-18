// OverhangCollisionPanel — Week 2 P1 (§1.7)
// Dual-axis primer-binding specificity: RT 3' overhang x forward 5' prefix.
// Reads specificity_warnings.overhang_collision — does NOT call the backend.
// Pure SVG, no chart libraries.

import { useState } from 'react';

const COMBINED_COLOR = {
  CRITICAL: { color: '#7F1D1D', bg: '#FEF2F2', border: '#FCA5A5', label: 'CRITICAL' },
  LOW:      { color: '#B45309', bg: '#FFFBEB', border: '#FCD34D', label: 'LOW' },
  SAFE:     { color: '#0F766E', bg: '#F0FDF9', border: '#5EEAD4', label: 'SAFE' },
};

// Axis order. Y (RT risk) worst at top; X (FWD risk) worst at right (SAFE→IDENTICAL).
const RT_ORDER = ['IDENTICAL', 'HIGH', 'LOW', 'SAFE'];
const FWD_ORDER = ['SAFE', 'LOW', 'HIGH', 'IDENTICAL'];

// Combined risk keyed (rt_risk, fwd_risk) — mirrors backend COMBINED_RISK_MATRIX.
const COMBINED = {
  'IDENTICAL|IDENTICAL': 'CRITICAL', 'IDENTICAL|HIGH': 'CRITICAL', 'IDENTICAL|LOW': 'LOW', 'IDENTICAL|SAFE': 'SAFE',
  'HIGH|IDENTICAL': 'CRITICAL', 'HIGH|HIGH': 'CRITICAL', 'HIGH|LOW': 'LOW', 'HIGH|SAFE': 'SAFE',
  'LOW|IDENTICAL': 'LOW', 'LOW|HIGH': 'LOW', 'LOW|LOW': 'SAFE', 'LOW|SAFE': 'SAFE',
  'SAFE|IDENTICAL': 'SAFE', 'SAFE|HIGH': 'SAFE', 'SAFE|LOW': 'SAFE', 'SAFE|SAFE': 'SAFE',
};

// ── Matrix layout ─────────────────────────────────────────────────
const CELL = 58;
const PAD_L = 74;   // room for Y (RT) axis labels
const PAD_T = 22;
const PAD_B = 40;   // room for X (FWD) axis labels
const GRID = CELL * 4;
const SVG_W = PAD_L + GRID + 12;
const SVG_H = PAD_T + GRID + PAD_B;

function _diffMarkup(seq, ref) {
  if (!seq) return null;
  return seq.split('').map((nt, i) => (
    <span key={i} className={ref && ref[i] !== nt ? 'font-bold text-red-600' : 'text-slate-500'}>{nt}</span>
  ));
}

function MatrixView({ data }) {
  const [active, setActive] = useState(null);
  const collisions = data.collisions || [];
  const target = data.target || {};

  // Bucket colliders into cells, with jittered dot positions.
  const placed = collisions.map((c, idx) => {
    const col = FWD_ORDER.indexOf(c.fwd_risk);
    const row = RT_ORDER.indexOf(c.rt_risk);
    if (col < 0 || row < 0) return null;
    const jx = ((idx % 3) - 1) * 12;
    const jy = (Math.floor(idx / 3) % 3 - 1) * 12;
    return {
      ...c, idx,
      cx: PAD_L + col * CELL + CELL / 2 + jx,
      cy: PAD_T + row * CELL + CELL / 2 + jy,
    };
  }).filter(Boolean);

  const activeC = active != null ? placed.find((p) => p.idx === active) : null;

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="overflow-x-auto max-w-full">
        <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} className="w-full max-w-md" role="img"
             aria-label="Primer-binding collision matrix: RT axis (rows) vs forward axis (columns)">
          <title>Primer Binding Specificity matrix</title>

          {/* cells */}
          {RT_ORDER.map((rt, r) => FWD_ORDER.map((fwd, c) => {
            const combined = COMBINED[`${rt}|${fwd}`];
            const cfg = COMBINED_COLOR[combined];
            return (
              <rect key={`${r}-${c}`} x={PAD_L + c * CELL} y={PAD_T + r * CELL}
                    width={CELL} height={CELL} fill={cfg.bg} stroke="#E2E8F0" strokeWidth="1" />
            );
          }))}

          {/* Y axis (RT risk) labels */}
          {RT_ORDER.map((rt, r) => (
            <text key={rt} x={PAD_L - 8} y={PAD_T + r * CELL + CELL / 2} textAnchor="end"
                  dominantBaseline="central" fontSize="10" fill="#475569">{rt}</text>
          ))}
          <text x={14} y={PAD_T + GRID / 2} textAnchor="middle" dominantBaseline="central"
                fontSize="10" fontWeight="bold" fill="#334155"
                transform={`rotate(-90 14 ${PAD_T + GRID / 2})`}>RT axis (3′ overhang)</text>

          {/* X axis (FWD risk) labels */}
          {FWD_ORDER.map((fwd, c) => (
            <text key={fwd} x={PAD_L + c * CELL + CELL / 2} y={PAD_T + GRID + 14} textAnchor="middle"
                  fontSize="10" fill="#475569">{fwd}</text>
          ))}
          <text x={PAD_L + GRID / 2} y={PAD_T + GRID + 32} textAnchor="middle"
                fontSize="10" fontWeight="bold" fill="#334155">FWD axis (5′ prefix)</text>

          {/* collider dots */}
          {placed.map((p) => {
            const cfg = COMBINED_COLOR[p.combined_risk] || COMBINED_COLOR.SAFE;
            const on = active === p.idx;
            return (
              <circle key={p.idx} cx={p.cx} cy={p.cy} r={on ? 8 : 6}
                      fill={on ? cfg.color : cfg.bg} stroke={cfg.color} strokeWidth={on ? 2.5 : 1.5}
                      style={{ cursor: 'pointer' }} tabIndex={0}
                      onMouseEnter={() => setActive(p.idx)} onMouseLeave={() => setActive(null)}
                      onFocus={() => setActive(p.idx)} onBlur={() => setActive(null)}>
                <title>{p.mirna} — {p.combined_risk}</title>
              </circle>
            );
          })}
        </svg>
      </div>

      {/* hover detail */}
      {activeC && (
        <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-3 py-2 space-y-1 text-xs shadow-sm">
          <div className="flex items-center justify-between">
            <span className="font-mono font-semibold text-slate-800">{activeC.mirna}</span>
            <span className="font-bold px-2 py-0.5 rounded-full border text-[11px]"
                  style={{ color: COMBINED_COLOR[activeC.combined_risk].color, borderColor: COMBINED_COLOR[activeC.combined_risk].border, background: COMBINED_COLOR[activeC.combined_risk].bg }}>
              {activeC.combined_risk}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-slate-600">
            <span>RT 6-mer</span>
            <span className="font-mono">{_diffMarkup(activeC.rt_window_dna, target.rt_window_dna)} <span className="text-slate-400">({activeC.rt_risk}, kwok {activeC.rt_kwok})</span></span>
            <span>FWD prefix</span>
            <span className="font-mono">{_diffMarkup(activeC.fwd_window_dna, target.fwd_window_dna)} <span className="text-slate-400">({activeC.fwd_risk}, kwok {activeC.fwd_kwok})</span></span>
            <span>Same seed?</span>
            <span>{activeC.same_seed_family ? 'yes' : 'no'}</span>
          </div>
          {activeC.note && <p className="text-[11px] text-slate-500 pt-1">{activeC.note}</p>}
        </div>
      )}

      {/* legend */}
      <div className="flex flex-wrap gap-2 justify-center text-[10px]">
        {Object.values(COMBINED_COLOR).map((cfg) => (
          <span key={cfg.label} className="flex items-center gap-1 px-1.5 py-0.5 rounded border"
                style={{ color: cfg.color, borderColor: cfg.border, background: cfg.bg }}>● {cfg.label}</span>
        ))}
      </div>
    </div>
  );
}

function TableView({ data }) {
  const collisions = data.collisions || [];
  return (
    <div className="rounded-lg border border-slate-200 overflow-x-auto">
      <table className="w-full text-xs">
        <thead className="bg-slate-100 border-b border-slate-200">
          <tr>
            {['Collider', 'RT 6-mer', 'RT mm', 'RT risk', 'FWD mm', 'FWD mm pos', 'FWD risk', 'Combined', 'Same seed?'].map((h) => (
              <th key={h} className="text-left px-2 py-1.5 font-semibold text-slate-600 whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {collisions.map((c) => {
            const cfg = COMBINED_COLOR[c.combined_risk] || COMBINED_COLOR.SAFE;
            return (
              <tr key={c.mirna}>
                <td className="px-2 py-1.5 font-mono text-slate-700 whitespace-nowrap">{c.mirna}</td>
                <td className="px-2 py-1.5 font-mono text-slate-600">{c.rt_window_dna}</td>
                <td className="px-2 py-1.5 tabular-nums text-slate-600">{c.rt_mismatch}</td>
                <td className="px-2 py-1.5 text-slate-600">{c.rt_risk}</td>
                <td className="px-2 py-1.5 tabular-nums text-slate-600">{c.fwd_mismatch}</td>
                <td className="px-2 py-1.5 tabular-nums text-slate-500">{(c.fwd_mismatch_positions_1based || []).join(', ') || '—'}</td>
                <td className="px-2 py-1.5 text-slate-600">{c.fwd_risk}</td>
                <td className="px-2 py-1.5">
                  <span className="font-bold px-2 py-0.5 rounded-full border text-[11px]"
                        style={{ color: cfg.color, borderColor: cfg.border, background: cfg.bg }}>{c.combined_risk}</span>
                </td>
                <td className="px-2 py-1.5 text-slate-500">{c.same_seed_family ? 'yes' : 'no'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function OverhangCollisionPanel({ overhangCollision }) {
  const [view, setView] = useState('matrix');
  if (!overhangCollision) return null;

  const {
    species, overhang_len, forward_specific_len, forward_axis_estimated,
    collisions = [], summary = {}, worst_combined_risk, recommendation,
    data_provenance = {}, n_screened,
  } = overhangCollision;

  const hasCollisions = collisions.length > 0;

  return (
    <div className="space-y-3">
      {/* header */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Primer Binding Specificity</p>
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded border bg-slate-50 border-slate-200 text-slate-600">RT 3′ · {overhang_len} nt</span>
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded border bg-slate-50 border-slate-200 text-slate-600">
            FWD 5′ · {forward_specific_len} nt{forward_axis_estimated ? ' (est.)' : ''}
          </span>
          {n_screened != null && (
            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded border bg-teal-50 border-teal-200 text-teal-700"
                  title={`Screened ${n_screened} ${species} mature miRNAs. Built ${data_provenance.build_date || 'n/a'}.`}>
              {n_screened} {species} screened
            </span>
          )}
        </div>
        {hasCollisions && (
          <div className="flex rounded-lg border border-slate-200 overflow-hidden text-[11px]">
            {['matrix', 'table'].map((v) => (
              <button key={v} type="button" onClick={() => setView(v)}
                      className={`px-2.5 py-1 font-medium capitalize transition-colors ${v === 'table' ? 'border-l border-slate-200 ' : ''}${view === v ? 'bg-teal-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}>
                {v}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* body */}
      {!hasCollisions ? (
        <p className="text-xs text-teal-700">
          No primer-axis collision detected across {n_screened} {species} mature miRNAs
          (RT 3′-{overhang_len}mer and forward 5′-{forward_specific_len}mer both discriminate).
        </p>
      ) : view === 'matrix' ? (
        <MatrixView data={overhangCollision} />
      ) : (
        <TableView data={overhangCollision} />
      )}

      {/* summary line */}
      {hasCollisions && (
        <p className="text-[11px] text-slate-500">
          Worst combined risk: <span className="font-semibold text-slate-700">{worst_combined_risk}</span>
          {' · '}{summary.CRITICAL || 0} CRITICAL, {summary.LOW || 0} LOW, {summary.rt_identical || 0} RT-identical
          {summary.truncated ? ` (showing ${summary.n_reported} of ${summary.n_total_non_safe})` : ''}
        </p>
      )}

      {/* recommendation (moved here from the seed panel) */}
      {recommendation && recommendation.action && recommendation.action !== 'none' && (
        <div className="rounded-lg bg-white border border-slate-200 px-3 py-2 space-y-1">
          <p className="text-xs font-semibold text-slate-600">Recommendation</p>
          <p className="text-xs text-slate-600">{recommendation.reason}</p>
          {recommendation.off_label_warning && (
            <p className="text-xs text-amber-700 mt-1">⚠ {recommendation.off_label_warning}</p>
          )}
        </div>
      )}

      {/* interpretation */}
      {overhangCollision.interpretation && (
        <p className="text-[10px] text-slate-400 italic">{overhangCollision.interpretation}</p>
      )}
    </div>
  );
}
