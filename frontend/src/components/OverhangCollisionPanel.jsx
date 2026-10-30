// OverhangCollisionPanel — assay-level specificity (ΔCq model, 2026-10-29).
// ΔCq_assay = ΔCq_RT (3' overhang capture) + ΔCq_FWD (forward priming on cDNA);
// cross-reactivity ≈ 2^−ΔCq. Reads specificity_warnings.overhang_collision — does NOT
// call the backend. Pure SVG, no chart libraries.

import { useState } from 'react';

const LABEL_COLOR = {
  'CO-AMPLIFIED':  { color: '#7F1D1D', bg: '#FEF2F2', border: '#FCA5A5' },
  PARTIAL:         { color: '#B45309', bg: '#FFFBEB', border: '#FCD34D' },
  DISCRIMINATED:   { color: '#0F766E', bg: '#F0FDF9', border: '#5EEAD4' },
};

const CATEGORY_TEXT = {
  same_sequence: 'Same sequence',
  shifted_5p: "5′ end shifted ≤2 nt",
  shifted_3p: "3′ end shifted ≤2 nt",
};

// ── ΔCq bar chart layout ──────────────────────────────────────────
const AXIS_MAX = 10;          // Cq; longer bars are clipped (label shows the value)
const ROW_H = 18;
const PAD_L = 118;
const PAD_R = 46;
const PAD_T = 18;
const PLOT_W = 300;
const SVG_W = PAD_L + PLOT_W + PAD_R;

const xOf = (cq) => PAD_L + (Math.min(cq, AXIS_MAX) / AXIS_MAX) * PLOT_W;

function _diffMarkup(seq, ref) {
  if (!seq) return null;
  return seq.split('').map((nt, i) => (
    <span key={i} className={ref && ref[i] !== nt ? 'font-bold text-red-600' : 'text-slate-500'}>{nt}</span>
  ));
}

function LabelPill({ label }) {
  const cfg = LABEL_COLOR[label] || LABEL_COLOR.DISCRIMINATED;
  return (
    <span className="font-bold px-2 py-0.5 rounded-full border text-xs whitespace-nowrap"
          style={{ color: cfg.color, borderColor: cfg.border, background: cfg.bg }}>{label}</span>
  );
}

function BarView({ data }) {
  const [active, setActive] = useState(null);
  const rows = data.collisions || [];
  const target = data.target || {};
  const th = data.thresholds || { co_amplified_below: 3.3, discriminated_at: 4.3 };
  const svgH = PAD_T + rows.length * ROW_H + 22;
  const activeC = active != null ? rows[active] : null;

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="overflow-x-auto max-w-full">
        <svg viewBox={`0 0 ${SVG_W} ${svgH}`} className="w-full max-w-lg" role="img"
             aria-label="Predicted assay ΔCq per off-target miRNA (RT + forward)">
          <title>Assay ΔCq per off-target</title>
          {/* label bands */}
          <rect x={PAD_L} y={PAD_T - 6} width={xOf(th.co_amplified_below) - PAD_L}
                height={rows.length * ROW_H + 6} fill={LABEL_COLOR['CO-AMPLIFIED'].bg} />
          <rect x={xOf(th.co_amplified_below)} y={PAD_T - 6}
                width={xOf(th.discriminated_at) - xOf(th.co_amplified_below)}
                height={rows.length * ROW_H + 6} fill={LABEL_COLOR.PARTIAL.bg} />
          <rect x={xOf(th.discriminated_at)} y={PAD_T - 6} width={PAD_L + PLOT_W - xOf(th.discriminated_at)}
                height={rows.length * ROW_H + 6} fill={LABEL_COLOR.DISCRIMINATED.bg} />
          {[0, th.co_amplified_below, th.discriminated_at, AXIS_MAX].map((v) => (
            <g key={v}>
              <line x1={xOf(v)} x2={xOf(v)} y1={PAD_T - 6} y2={PAD_T + rows.length * ROW_H}
                    stroke="#CBD5E1" strokeWidth="1" strokeDasharray={v === 0 || v === AXIS_MAX ? '' : '3 2'} />
              <text x={xOf(v)} y={PAD_T + rows.length * ROW_H + 14} textAnchor="middle"
                    fontSize="9" fill="#64748B">{v === AXIS_MAX ? `≥${v}` : v}</text>
            </g>
          ))}
          <text x={PAD_L + PLOT_W / 2} y={10} textAnchor="middle" fontSize="9" fill="#334155" fontWeight="bold">
            ΔCq vs target (RT + forward)
          </text>
          {rows.map((c, i) => {
            const y = PAD_T + i * ROW_H;
            const cfg = LABEL_COLOR[c.assay_label] || LABEL_COLOR.DISCRIMINATED;
            const rtW = xOf(c.rt?.delta_cq || 0) - PAD_L;
            const on = active === i;
            return (
              <g key={c.mirna} tabIndex={0} style={{ cursor: 'pointer' }}
                 onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)}
                 onFocus={() => setActive(i)} onBlur={() => setActive(null)}>
                <text x={PAD_L - 6} y={y + ROW_H / 2} textAnchor="end" dominantBaseline="central"
                      fontSize="9.5" fontFamily="monospace" fill={on ? '#0F172A' : '#475569'}>{c.mirna}</text>
                {/* RT part (darker) + forward part */}
                <rect x={PAD_L} y={y + 4} width={Math.max(xOf(c.delta_cq) - PAD_L, 1.5)} height={ROW_H - 8}
                      fill={cfg.border} opacity={on ? 1 : 0.85} />
                <rect x={PAD_L} y={y + 4} width={Math.max(rtW, 0)} height={ROW_H - 8} fill={cfg.color} opacity="0.55" />
                <text x={xOf(c.delta_cq) + 4} y={y + ROW_H / 2} dominantBaseline="central" fontSize="9"
                      fill="#334155">{c.delta_cq}{c.delta_cq_is_lower_bound ? '+' : ''}</text>
                <title>{c.mirna} — {c.assay_label}, ΔCq {c.delta_cq} (≈{c.cross_reactivity_pct}% cross-signal)</title>
              </g>
            );
          })}
        </svg>
      </div>

      {activeC && (
        <div className="w-full max-w-lg rounded-lg border border-slate-200 bg-white px-3 py-2 space-y-1 text-xs shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono font-semibold text-slate-800">{activeC.mirna}</span>
            <LabelPill label={activeC.assay_label} />
          </div>
          <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-slate-600">
            <span>RT window</span>
            <span className="font-mono">{_diffMarkup(activeC.rt_window_dna, target.rt_window_dna)}
              <span className="text-slate-500 font-sans"> ΔCq {activeC.rt?.delta_cq}
                {activeC.rt?.shift_range && ` (shift measured ${activeC.rt.shift_range[0]}–${activeC.rt.shift_range[1]} Ct, n = ${activeC.rt.shift_range[2]})`}
                {' — '}{activeC.rt?.basis}</span></span>
            <span>Forward</span>
            <span className="font-mono">{activeC.fwd ? _diffMarkup(activeC.fwd_window_dna, target.fwd_window_dna) : '—'}
              <span className="text-slate-500 font-sans">
                {activeC.fwd ? ` ΔCq ${activeC.fwd.delta_cq} — ${activeC.fwd.basis}` : ' not evaluated (RT step already discriminates)'}
              </span></span>
            <span>Cross-signal</span>
            <span>≈{activeC.cross_reactivity_pct}%{activeC.delta_cq_is_lower_bound ? ' or less' : ''}</span>
            {activeC.delta_cq_high != null && (
              <>
                <span>ΔCq range</span>
                <span>{activeC.delta_cq}–{activeC.delta_cq_high} — the end-shift term rests on
                  two miRNAs that differ by up to 4 Ct; the label uses the lower bound.</span>
              </>
            )}
            <span>Same seed?</span>
            <span>{activeC.same_seed_family ? 'yes (context only)' : 'no'}</span>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2 justify-center text-xs">
        {Object.keys(LABEL_COLOR).map((k) => <LabelPill key={k} label={k} />)}
        <span className="text-slate-500">darker segment = RT share of the ΔCq</span>
      </div>
    </div>
  );
}

function TableView({ data }) {
  const rows = data.collisions || [];
  return (
    <div className="rounded-lg border border-slate-200 overflow-x-auto">
      <table className="w-full text-xs">
        <thead className="bg-slate-100 border-b border-slate-200">
          <tr>
            {['Off-target', 'RT window', 'ΔCq RT', 'ΔCq FWD', 'ΔCq assay', 'Cross-signal', 'Label', 'Same seed?'].map((h) => (
              <th key={h} className="text-left px-2 py-1.5 font-semibold text-slate-600 whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {rows.map((c) => (
            <tr key={c.mirna}>
              <td className="px-2 py-1.5 font-mono text-slate-700 whitespace-nowrap">{c.mirna}</td>
              <td className="px-2 py-1.5 font-mono text-slate-600">{c.rt_window_dna}</td>
              <td className="px-2 py-1.5 tabular-nums text-slate-600" title={c.rt?.basis}>{c.rt?.delta_cq}</td>
              <td className="px-2 py-1.5 tabular-nums text-slate-600" title={c.fwd?.basis}>{c.fwd ? c.fwd.delta_cq : '—'}</td>
              <td className="px-2 py-1.5 tabular-nums font-semibold text-slate-700">{c.delta_cq}{c.delta_cq_is_lower_bound ? '+' : ''}</td>
              <td className="px-2 py-1.5 tabular-nums text-slate-600">≈{c.cross_reactivity_pct}%</td>
              <td className="px-2 py-1.5"><LabelPill label={c.assay_label} /></td>
              <td className="px-2 py-1.5 text-slate-500">{c.same_seed_family ? 'yes' : 'no'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SameMoleculeList({ entries }) {
  if (!entries || !entries.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 space-y-1">
      <p className="text-xs font-semibold text-slate-600">
        Other miRBase entries for the same molecule — reported, not scored
      </p>
      <ul className="text-xs text-slate-600 space-y-0.5">
        {entries.map((e) => (
          <li key={e.mirna}>
            <span className="font-mono text-slate-700">{e.mirna}</span>
            {' · '}{CATEGORY_TEXT[e.category] || e.category}
            {' · '}ΔCq {e.delta_cq}{e.delta_cq_high != null && e.delta_cq_high !== e.delta_cq ? `–${e.delta_cq_high}` : ''} (≈{e.cross_reactivity_pct}%)
            <span className="text-slate-500"> — {e.note}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-slate-500">
        Synonyms, renamed entries or paralogues from another locus — no primer design separates them,
        so the signal is their sum (Magee et al. 2017). Biological isomiRs have no miRBase entries of
        their own; see the RT primer's isomiR flags.
      </p>
    </div>
  );
}

export default function OverhangCollisionPanel({ overhangCollision }) {
  const [view, setView] = useState('chart');
  if (!overhangCollision) return null;

  const {
    species, overhang_len, forward_specific_len, forward_axis_estimated,
    collisions = [], same_molecule_entries = [], summary = {}, worst_assay_label, recommendation,
    data_provenance = {}, n_screened, screened_species = [], annotation_note,
  } = overhangCollision;
  const screenedLabel = screened_species.length ? screened_species.join(' + ') : species;

  const hasCollisions = collisions.length > 0;

  return (
    <div className="space-y-3">
      {/* header */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Assay Specificity (ΔCq)</p>
          <span className="text-xs font-medium px-1.5 py-0.5 rounded border bg-slate-50 border-slate-200 text-slate-600">RT 3′ · {overhang_len} nt</span>
          <span className="text-xs font-medium px-1.5 py-0.5 rounded border bg-slate-50 border-slate-200 text-slate-600">
            FWD 5′ · {forward_specific_len} nt{forward_axis_estimated ? ' (est.)' : ''}
          </span>
          {n_screened != null && (
            <span className="text-xs font-medium px-1.5 py-0.5 rounded border bg-teal-50 border-teal-200 text-teal-700"
                  title={`Screened ${n_screened} mature miRNAs (${screenedLabel}), miRBase ${data_provenance.mirbase_release || '?'}. Built ${data_provenance.build_date || 'n/a'}.`}>
              {n_screened} {screenedLabel} screened
            </span>
          )}
        </div>
        {hasCollisions && (
          <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
            {['chart', 'table'].map((v) => (
              <button key={v} type="button" onClick={() => setView(v)}
                      className={`px-2.5 py-1 font-medium capitalize transition-colors ${v === 'table' ? 'border-l border-slate-200 ' : ''}${view === v ? 'bg-teal-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}>
                {v}
              </button>
            ))}
          </div>
        )}
      </div>

      {annotation_note && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
          {annotation_note}
        </p>
      )}

      {/* body */}
      {!hasCollisions ? (
        <p className="text-xs text-teal-700">
          Every other miRNA screened ({n_screened}, {screenedLabel}) is predicted to be discriminated
          (ΔCq_assay ≥ 4.3, &lt; 5 % cross-signal).
        </p>
      ) : view === 'chart' ? (
        <BarView data={overhangCollision} />
      ) : (
        <TableView data={overhangCollision} />
      )}

      {hasCollisions && (
        <p className="text-xs text-slate-500">
          Worst other miRNA: <span className="font-semibold text-slate-700">{worst_assay_label}</span>
          {' · '}{summary['CO-AMPLIFIED'] || 0} co-amplified, {summary.PARTIAL || 0} partial,
          {' '}{summary.rt_identical || 0} share the RT overhang
          {summary.truncated ? ` (showing ${summary.n_reported} of ${summary.n_total_flagged})` : ''}
        </p>
      )}

      <SameMoleculeList entries={same_molecule_entries} />

      {recommendation && recommendation.action && recommendation.action !== 'none' && (
        <div className="rounded-lg bg-white border border-slate-200 px-3 py-2 space-y-1">
          <p className="text-xs font-semibold text-slate-600">Recommendation</p>
          <p className="text-xs text-slate-600">{recommendation.reason}</p>
          {recommendation.off_label_warning && (
            <p className="text-xs text-amber-700 mt-1">⚠ {recommendation.off_label_warning}</p>
          )}
        </div>
      )}

      {overhangCollision.interpretation && (
        <p className="text-xs text-slate-500 italic">{overhangCollision.interpretation}</p>
      )}
    </div>
  );
}
