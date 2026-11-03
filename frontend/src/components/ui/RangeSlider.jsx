import { useState } from 'react';
import Tooltip from './Tooltip.jsx';

// CSS variable — resolves to the active theme's brand-600 at runtime
const TRACK_FILL  = 'var(--brand-600)';
const TRACK_EMPTY = '#E5E7EB'; // gray-200

export default function RangeSlider({
  min,
  max,
  valueMin,
  valueMax,
  step = 1,
  unit = '',
  label,
  tooltip,
  onChange,
}) {
  const [dragging, setDragging] = useState(null); // 'min' | 'max' | null

  const range    = max - min || 1;
  const leftPct  = ((valueMin - min) / range) * 100;
  const rightPct = ((valueMax - min) / range) * 100;
  const trackStyle = {
    background: `linear-gradient(to right,
      ${TRACK_EMPTY} 0%,
      ${TRACK_EMPTY} ${leftPct}%,
      ${TRACK_FILL}  ${leftPct}%,
      ${TRACK_FILL}  ${rightPct}%,
      ${TRACK_EMPTY} ${rightPct}%,
      ${TRACK_EMPTY} 100%)`,
  };

  function onMinChange(e) {
    const next = Number(e.target.value);
    onChange(Math.min(next, valueMax - step), valueMax);
  }

  function onMaxChange(e) {
    const next = Number(e.target.value);
    onChange(valueMin, Math.max(next, valueMin + step));
  }

  const thumbCls = `
    appearance-none w-full h-1.5 rounded-full bg-transparent cursor-pointer absolute top-0 left-0 pointer-events-none
    [&::-webkit-slider-thumb]:appearance-none
    [&::-webkit-slider-thumb]:pointer-events-auto
    [&::-webkit-slider-thumb]:w-4
    [&::-webkit-slider-thumb]:h-4
    [&::-webkit-slider-thumb]:rounded-full
    [&::-webkit-slider-thumb]:bg-teal-600
    [&::-webkit-slider-thumb]:border-2
    [&::-webkit-slider-thumb]:border-white
    [&::-webkit-slider-thumb]:shadow-sm
    [&::-webkit-slider-thumb]:cursor-pointer
    [&::-webkit-slider-thumb]:hover:bg-teal-700
    [&::-webkit-slider-thumb]:transition-colors
    [&::-moz-range-thumb]:pointer-events-auto
    [&::-moz-range-thumb]:w-4
    [&::-moz-range-thumb]:h-4
    [&::-moz-range-thumb]:rounded-full
    [&::-moz-range-thumb]:bg-teal-600
    [&::-moz-range-thumb]:border-2
    [&::-moz-range-thumb]:border-white
    [&::-moz-range-thumb]:cursor-pointer
  `;

  return (
    <div className="space-y-1.5">
      {label && (
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-medium text-slate-700">{label}</span>
          {tooltip && <Tooltip text={tooltip} />}
        </div>
      )}

      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-500 w-8 shrink-0">{min}{unit}</span>

        {/* Track area — extra top padding to make room for drag callout */}
        <div className="relative flex-1" style={{ paddingTop: '1.25rem' }}>

          {/* Drag value callout bubble */}
          {dragging && (
            <div
              className="absolute top-0 z-20 pointer-events-none"
              style={{
                left: `${dragging === 'min' ? leftPct : rightPct}%`,
                transform: 'translateX(-50%)',
              }}
            >
              <span className="inline-block bg-teal-700 text-white text-xs font-bold px-1.5 py-0.5 rounded leading-none shadow-md tabular-nums whitespace-nowrap">
                {dragging === 'min' ? valueMin : valueMax}{unit}
              </span>
              {/* small arrow pointing down */}
              <span className="block w-0 h-0 mx-auto"
                style={{
                  borderLeft: '4px solid transparent',
                  borderRight: '4px solid transparent',
                  borderTop: '4px solid var(--brand-700)',
                }}
              />
            </div>
          )}

          {/* Slider track */}
          <div className="relative h-1.5">
            <div className="absolute inset-0 rounded-full" style={trackStyle} />

            <input
              type="range"
              min={min}
              max={max}
              step={step}
              value={valueMin}
              onChange={onMinChange}
              onPointerDown={() => setDragging('min')}
              onPointerUp={() => setDragging(null)}
              className={thumbCls}
            />

            <input
              type="range"
              min={min}
              max={max}
              step={step}
              value={valueMax}
              onChange={onMaxChange}
              onPointerDown={() => setDragging('max')}
              onPointerUp={() => setDragging(null)}
              className={thumbCls}
            />
          </div>

        </div>

        <span className="text-xs text-slate-500 w-8 shrink-0 text-right">{max}{unit}</span>
      </div>

      <div className="flex justify-between px-10">
        <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-teal-50 border border-teal-100 text-xs text-teal-700 font-semibold tabular-nums">
          {valueMin}{unit}
        </span>
        <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-teal-50 border border-teal-100 text-xs text-teal-700 font-semibold tabular-nums">
          {valueMax}{unit}
        </span>
      </div>
    </div>
  );
}
