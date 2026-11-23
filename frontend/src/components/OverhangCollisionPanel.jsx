// OverhangCollisionPanel — assay-level specificity (ΔCq model, 2026-10-29).
// ΔCq_assay = ΔCq_RT (3′ overhang capture) + ΔCq_FWD (forward priming on cDNA);
// cross-reactivity ≈ 2^−ΔCq. Reads specificity_warnings.overhang_collision — does NOT
// call the backend. Pure SVG, no chart libraries.

import { useEffect, useRef, useState } from 'react';
import { levelWord, STATUS_CLASSES, statusOf } from '../utils/format.js';

const LABEL_COLOR = {
  'CO-AMPLIFIED':  { color: '#7F1D1D', bg: '#FEF2F2', border: '#FCA5A5' },
  PARTIAL:         { color: '#B45309', bg: '#FFFBEB', border: '#FCD34D' },
  DISCRIMINATED:   { color: '#15803D', bg: '#F0FDF4', border: '#86EFAC' },
};

const CATEGORY_TEXT = {
  same_sequence: 'Same sequence',
  shifted_5p: "5′ end shifted ≤2 nt",
  shifted_3p: "3′ end shifted ≤2 nt",
};

// ── ΔCq bar chart layout ──────────────────────────────────────────
// The SVG is drawn at the container's own pixel width (1 unit = 1 px), so its text is
// 11–12 px on screen at any width (UI review 2026-11-23: it rendered at ~6 px).
const AXIS_MAX = 10;          // Cq; longer bars are clipped (label shows the value)
const ROW_H = 24;
const PAD_L = 132;
const PAD_R = 44;
const PAD_T = 24;

function _diffMarkup(seq, ref) {
  if (!seq) return null;
  return seq.split('').map((nt, i) => (
    <span key={i} className={ref && ref[i] !== nt ? 'font-bold text-red-700' : 'text-slate-600'}>{nt}</span>
  ));
}

function LabelPill({ label }) {
  return (
    <span className={`font-semibold px-2 py-0.5 rounded-full border text-xs whitespace-nowrap ${STATUS_CLASSES[statusOf(label)]}`}>
      {levelWord(label)}
    </span>
  );
}

function useWidth(ref, fallback = 480) {
  const [w, setW] = useState(fallback);
  useEffect(() => {
    if (!ref.current) return undefined;
    const update = () => setW(Math.max(280, Math.round(ref.current.clientWidth)));
    update();
    const ro = new ResizeObserver(update);
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

function BarView({ data }) {
  const [active, setActive] = useState(null);
  const boxRef = useRef(null);
  const SVG_W = useWidth(boxRef);
  const PLOT_W = SVG_W - PAD_L - PAD_R;
  const xOf = (cq) => PAD_L + (Math.min(cq, AXIS_MAX) / AXIS_MAX) * PLOT_W;
  const rows = data.collisions || [];
  const target = data.target || {};
  const th = data.thresholds || { co_amplified_below: 3.3, discriminated_at: 4.3 };
  const svgH = PAD_T + rows.length * ROW_H + 26;
  const activeC = active != null ? rows[active] : null;

  return (
    <div className="flex flex-col gap-3">
      <div ref={boxRef} className="w-full">
        <svg viewBox={`0 0 ${SVG_W} ${svgH}`} width={SVG_W} height={svgH} className="block" role="img"
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
                    fontSize="11" fill="#475569">{v === AXIS_MAX ? `≥ ${v}` : v}</text>
            </g>
          ))}
          <text x={PAD_L + PLOT_W / 2} y={13} textAnchor="middle" fontSize="12" fill="#334155" fontWeight="600">
            Assay ΔCq vs the target (RT + forward)
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
                      fontSize="12" fill={on ? '#0F172A' : '#334155'}>{c.mirna}</text>
                {/* RT part (darker) + forward part */}
                <rect x={PAD_L} y={y + 4} width={Math.max(xOf(c.delta_cq) - PAD_L, 1.5)} height={ROW_H - 8}
                      fill={cfg.border} opacity={on ? 1 : 0.85} />
                <rect x={PAD_L} y={y + 4} width={Math.max(rtW, 0)} height={ROW_H - 8} fill={cfg.color} opacity="0.55" />
                <text x={Math.min(xOf(c.delta_cq) + 4, SVG_W - PAD_R + 4)} y={y + ROW_H / 2} dominantBaseline="central" fontSize="11"
                      fill="#334155">{c.delta_cq}{c.delta_cq_is_lower_bound ? '+' : ''}</text>
                <title>{c.mirna}: {levelWord(c.assay_label)}, ΔCq {c.delta_cq} (≈{c.cross_reactivity_pct}% cross-signal)</title>
              </g>
            );
          })}
        </svg>
      </div>

      {activeC && (
        <div className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 space-y-1 text-xs shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold text-slate-800 whitespace-nowrap">{activeC.mirna}</span>
            <LabelPill label={activeC.assay_label} />
          </div>
          <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-slate-700">
            <span>RT window</span>
            <span><span className="seq">{_diffMarkup(activeC.rt_window_dna, target.rt_window_dna)}</span>
              <span className="text-slate-700"> ΔCq {activeC.rt?.delta_cq}
                {activeC.rt?.shift_range && ` (shift measured ${activeC.rt.shift_range[0]}–${activeC.rt.shift_range[1]} Ct, n = ${activeC.rt.shift_range[2]})`}
                {' — '}{activeC.rt?.basis}</span></span>
            <span>Forward</span>
            <span><span className="seq">{activeC.fwd ? _diffMarkup(activeC.fwd_window_dna, target.fwd_window_dna) : '—'}</span>
              <span className="text-slate-700">
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

      <div className="flex flex-wrap gap-2 items-center text-xs">
        {Object.keys(LABEL_COLOR).map((k) => <LabelPill key={k} label={k} />)}
        <span className="text-slate-700">Darker segment: the RT share of the ΔCq.</span>
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
            {['Off-target', 'RT window', 'ΔCq RT', 'ΔCq forward', 'ΔCq assay', 'Cross-signal', 'Label', 'Same seed?'].map((h) => (
              <th key={h} className="text-left px-2 py-1.5 font-semibold text-slate-700 whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {rows.map((c) => (
            <tr key={c.mirna}>
              <td className="px-2 py-1.5 text-slate-800 whitespace-nowrap">{c.mirna}</td>
              <td className="px-2 py-1.5 seq text-slate-700">{c.rt_window_dna}</td>
              <td className="px-2 py-1.5 tabular-nums text-slate-600" title={c.rt?.basis}>{c.rt?.delta_cq}</td>
              <td className="px-2 py-1.5 tabular-nums text-slate-600" title={c.fwd?.basis}>{c.fwd ? c.fwd.delta_cq : '—'}</td>
              <td className="px-2 py-1.5 tabular-nums font-semibold text-slate-700">{c.delta_cq}{c.delta_cq_is_lower_bound ? '+' : ''}</td>
              <td className="px-2 py-1.5 tabular-nums text-slate-600">≈{c.cross_reactivity_pct}%</td>
              <td className="px-2 py-1.5"><LabelPill label={c.assay_label} /></td>
              <td className="px-2 py-1.5 text-slate-700">{c.same_seed_family ? 'Yes' : 'No'}</td>
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
        Other miRBase entries for the same molecule (reported, not scored)
      </p>
      <ul className="text-xs text-slate-600 space-y-0.5">
        {entries.map((e) => (
          <li key={e.mirna}>
            <span className="text-slate-800 whitespace-nowrap">{e.mirna}</span>
            {' · '}{CATEGORY_TEXT[e.category] || e.category}
            {' · '}ΔCq {e.delta_cq}{e.delta_cq_high != null && e.delta_cq_high !== e.delta_cq ? `–${e.delta_cq_high}` : ''} (≈{e.cross_reactivity_pct}%)
            <span className="text-slate-700">. {e.note}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-slate-700">
        Synonyms, renamed entries or paralogues from another locus: no primer design separates them,
        so the signal is their sum (Magee et al. 2017). Biological isomiRs have no miRBase entries of
        their own; see the RT primer's isomiR flags.
      </p>
    </div>
  );
}

export default function OverhangCollisionPanel({ overhangCollision, hideTitle = false, closest = null }) {
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
          {!hideTitle && <p className="text-xs font-semibold text-slate-700">Assay specificity (ΔCq)</p>}
          <span className="text-xs font-medium px-1.5 py-0.5 rounded border bg-slate-50 border-slate-200 text-slate-700 whitespace-nowrap">RT 3′ overhang {overhang_len}{'\u00a0'}nt</span>
          <span className="text-xs font-medium px-1.5 py-0.5 rounded border bg-slate-50 border-slate-200 text-slate-700 whitespace-nowrap">
            Forward 5′ region {forward_specific_len}{'\u00a0'}nt{forward_axis_estimated ? ' (estimated)' : ''}
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
                      aria-pressed={view === v}
                      className={`px-2.5 py-1 font-medium capitalize transition-colors ${v === 'table' ? 'border-l border-slate-200 ' : ''}${view === v ? 'bg-teal-600 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'}`}>
                {v}
              </button>
            ))}
          </div>
        )}
      </div>

      {annotation_note && (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-1">
          {annotation_note}
        </p>
      )}

      {/* body */}
      {!hasCollisions ? (
        <p className="text-xs text-green-700">
          Every other miRNA screened ({n_screened}, {screenedLabel}) is predicted to be discriminated
          (assay ΔCq ≥ 4.3, &lt; 5% cross-signal).
        </p>
      ) : view === 'chart' ? (
        <BarView data={overhangCollision} />
      ) : (
        <TableView data={overhangCollision} />
      )}

      {hasCollisions && (
        <p className="text-xs text-slate-700">
          Worst other miRNA: <span className="font-semibold">{levelWord(worst_assay_label)}</span>
          {' · '}{summary['CO-AMPLIFIED'] || 0} co-amplified, {summary.PARTIAL || 0} partial,
          {' '}{summary.rt_identical || 0} share the RT overhang
          {summary.truncated ? ` (showing ${summary.n_reported} of ${summary.n_total_flagged})` : ''}
        </p>
      )}

      {/* The chart lists the miRNAs flagged by the design-level screen; the comparison table
          names each set's closest off-target over every miRNA screened. Say so when they
          differ, so the two never look contradictory. */}
      {hasCollisions && closest?.worst_target && closest.worst_target !== collisions[0]?.mirna && (
        <p className="text-xs text-slate-700" data-testid="closest-note">
          The comparison table names <span className="whitespace-nowrap font-medium">{closest.worst_target}</span>
          {closest.min_delta_cq != null && <> (ΔCq {Number(closest.min_delta_cq).toFixed(1)})</>} as the closest
          off-target of the top set: it is screened over every miRNA, while this chart lists the miRNAs flagged at
          design level
          {collisions[0]?.delta_cq === closest.min_delta_cq ? '; both are at the same ΔCq' : ''}.
        </p>
      )}

      <SameMoleculeList entries={same_molecule_entries} />

      {recommendation && recommendation.action && recommendation.action !== 'none' && (
        <div className="rounded-lg bg-white border border-slate-200 px-3 py-2 space-y-1">
          <p className="text-xs font-semibold text-slate-700">Recommendation</p>
          <p className="text-xs text-slate-700">{recommendation.reason}</p>
          {recommendation.off_label_warning && (
            <p className="text-xs text-amber-800 mt-1">{recommendation.off_label_warning}</p>
          )}
        </div>
      )}

      {overhangCollision.interpretation && (
        <details className="group text-xs text-slate-700">
          <summary className="cursor-pointer text-teal-700 font-medium hover:underline list-none marker:hidden">
            <span aria-hidden className="inline-block transition-transform group-open:rotate-90">▸</span> Method
          </summary>
          <p className="mt-1 leading-relaxed">
            An off-target gives signal only if the RT overhang captures it and the forward primer primes its
            cDNA; the two delays add (assay ΔCq = ΔCq<sub>RT</sub> + ΔCq<sub>forward</sub>; cross-signal ≈
            2<sup>−ΔCq</sup>). {overhangCollision.interpretation.replace(/^.*?\)\.\s*/, '')}
          </p>
        </details>
      )}
    </div>
  );
}
