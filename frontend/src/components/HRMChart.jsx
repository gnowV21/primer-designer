import { useState } from 'react';

/**
 * HRMChart — melt-curve viewer.
 *
 * DISPLAY ONLY [SPEC_Phase1 §4.3]. Nothing drawn here is ever an input to the
 * analysis: every number the assistant quotes comes from the Python feature table.
 * This chart exists so a human can sanity-check that table, not so the model can
 * read a curve.
 *
 * Hand-rolled SVG on purpose — the project stack is fixed (React + Vite + Tailwind
 * + Router + Axios), so no charting library may be added.
 */

const VIEWS = [
  { key: 'normalized', label: 'Normalized',  yLabel: 'F_norm',  desc: 'Bilinear-normalized fluorescence (1.0 = dsDNA, 0.0 = ssDNA)' },
  { key: 'derivative', label: 'Derivative',  yLabel: '-dF/dT',  desc: 'Melt peak — the maximum of this curve is Tm' },
  { key: 'difference', label: 'Difference',  yLabel: 'Δ vs ctrl', desc: 'Each well minus the positive control' },
];

// Colour-blind-safe qualitative palette (Okabe-Ito). Cycles if there are more wells.
const PALETTE = ['#0F6E56', '#E69F00', '#56B4E9', '#D55E00', '#CC79A7', '#009E73', '#F0E442', '#0072B2'];

const W = 720;
const H = 280;
const PAD = { top: 16, right: 16, bottom: 36, left: 52 };

export default function HRMChart({ curves, features }) {
  const [view, setView] = useState('derivative');
  const [hidden, setHidden] = useState(() => new Set());

  if (!curves?.temp?.length) return null;

  const active = VIEWS.find((v) => v.key === view);
  const series = curves[view];

  // The difference curve only exists when a positive control was present.
  if (!series) {
    return (
      <div className="border border-gray-200 rounded-xl bg-white p-4">
        <ViewTabs view={view} setView={setView} available={curves} />
        <p className="text-xs text-gray-500 mt-4 text-center py-10">
          No difference curve — the uploaded file has no positive control column.
        </p>
      </div>
    );
  }

  const temp = curves.temp;
  const names = Object.keys(series).filter((n) => !hidden.has(n));

  // Scale to the VISIBLE series only, so hiding a saturating well rescales the rest.
  const visibleValues = names.flatMap((n) => series[n]).filter(Number.isFinite);
  const yMin = visibleValues.length ? Math.min(...visibleValues) : 0;
  const yMax = visibleValues.length ? Math.max(...visibleValues) : 1;
  const yPad = (yMax - yMin) * 0.08 || 0.1;

  const xScale = (t) =>
    PAD.left + ((t - temp[0]) / (temp[temp.length - 1] - temp[0])) * (W - PAD.left - PAD.right);
  const yScale = (v) =>
    H - PAD.bottom - ((v - (yMin - yPad)) / ((yMax + yPad) - (yMin - yPad))) * (H - PAD.top - PAD.bottom);

  const path = (values) =>
    values
      .map((v, i) => `${i === 0 ? 'M' : 'L'} ${xScale(temp[i]).toFixed(1)} ${yScale(v).toFixed(1)}`)
      .join(' ');

  const xTicks = ticks(temp[0], temp[temp.length - 1], 6);
  const yTicks = ticks(yMin - yPad, yMax + yPad, 5);

  const allNames = Object.keys(series);
  const colorOf = (n) => PALETTE[allNames.indexOf(n) % PALETTE.length];

  const toggle = (n) =>
    setHidden((prev) => {
      const next = new Set(prev);
      next.has(n) ? next.delete(n) : next.add(n);
      return next;
    });

  return (
    <div className="border border-gray-200 rounded-xl bg-white p-4">
      <ViewTabs view={view} setView={setView} available={curves} />

      <p className="text-[11px] text-gray-400 mt-2 mb-1">{active.desc}</p>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
           aria-label={`${active.label} melt curve chart`}>
        {/* Gridlines + y axis */}
        {yTicks.map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={yScale(v)} y2={yScale(v)}
                  stroke="#F1F5F9" strokeWidth="1" />
            <text x={PAD.left - 8} y={yScale(v) + 3} textAnchor="end"
                  className="fill-gray-400" fontSize="10">
              {fmtTick(v)}
            </text>
          </g>
        ))}

        {/* x axis */}
        {xTicks.map((t) => (
          <text key={t} x={xScale(t)} y={H - PAD.bottom + 15} textAnchor="middle"
                className="fill-gray-400" fontSize="10">
            {t.toFixed(0)}
          </text>
        ))}
        <line x1={PAD.left} x2={W - PAD.right} y1={H - PAD.bottom} y2={H - PAD.bottom}
              stroke="#CBD5E1" strokeWidth="1" />

        {/* Zero line — the meaningful baseline on the difference plot */}
        {view === 'difference' && yMin - yPad < 0 && yMax + yPad > 0 && (
          <line x1={PAD.left} x2={W - PAD.right} y1={yScale(0)} y2={yScale(0)}
                stroke="#94A3B8" strokeWidth="1" strokeDasharray="4 3" />
        )}

        {/* Axis labels */}
        <text x={(PAD.left + W - PAD.right) / 2} y={H - 4} textAnchor="middle"
              className="fill-gray-500" fontSize="10">
          Temperature (°C)
        </text>
        <text x={12} y={(PAD.top + H - PAD.bottom) / 2} textAnchor="middle"
              transform={`rotate(-90 12 ${(PAD.top + H - PAD.bottom) / 2})`}
              className="fill-gray-500" fontSize="10">
          {active.yLabel}
        </text>

        {/* Curves */}
        {names.map((n) => (
          <path key={n} d={path(series[n])} fill="none" stroke={colorOf(n)}
                strokeWidth="1.6" strokeLinejoin="round" />
        ))}

        {/* Tm markers — only on the derivative view, where the peak IS the Tm */}
        {view === 'derivative' && names.map((n) => {
          const tm = features?.[n]?.Tm;
          if (tm == null) return null;
          return (
            <line key={`tm-${n}`} x1={xScale(tm)} x2={xScale(tm)}
                  y1={PAD.top} y2={H - PAD.bottom}
                  stroke={colorOf(n)} strokeWidth="0.8" strokeDasharray="3 3" opacity="0.5" />
          );
        })}
      </svg>

      {/* Legend — click a well to hide it */}
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-2">
        {allNames.map((n) => {
          const isHidden = hidden.has(n);
          const tm = features?.[n]?.Tm;
          return (
            <button
              key={n}
              type="button"
              onClick={() => toggle(n)}
              title={isHidden ? `Show ${n}` : `Hide ${n}`}
              className={`flex items-center gap-1.5 text-[11px] transition-opacity ${
                isHidden ? 'opacity-35' : 'opacity-100'
              }`}
            >
              <span className="w-3 h-0.5 rounded-full shrink-0"
                    style={{ backgroundColor: colorOf(n) }} />
              <span className="text-gray-600">{n}</span>
              {view === 'derivative' && tm != null && (
                <span className="text-gray-400">({tm}°C)</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ViewTabs({ view, setView, available }) {
  return (
    <div className="flex gap-1">
      {VIEWS.map(({ key, label }) => {
        const disabled = !available[key];
        return (
          <button
            key={key}
            type="button"
            disabled={disabled}
            onClick={() => setView(key)}
            className={
              view === key
                ? 'px-3 py-1 rounded-lg text-xs font-semibold text-teal-700 bg-teal-50 border border-teal-200'
                : disabled
                ? 'px-3 py-1 rounded-lg text-xs font-medium text-gray-300 cursor-not-allowed'
                : 'px-3 py-1 rounded-lg text-xs font-medium text-gray-500 hover:text-teal-700 hover:bg-teal-50'
            }
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

/** `count` evenly spaced tick values across [min, max]. */
function ticks(min, max, count) {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return [min];
  const step = (max - min) / (count - 1);
  return Array.from({ length: count }, (_, i) => min + i * step);
}

function fmtTick(v) {
  if (Math.abs(v) >= 100) return v.toFixed(0);
  if (Math.abs(v) >= 1) return v.toFixed(1);
  return v.toFixed(2);
}
