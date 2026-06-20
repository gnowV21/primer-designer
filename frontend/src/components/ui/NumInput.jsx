import { useState, useEffect } from 'react';
import Tooltip from './Tooltip.jsx';

/**
 * Controlled number input that keeps a local raw string so the field can
 * display empty while the user is clearing/typing, instead of snapping
 * back to 0 (which happens when Number('') = 0 updates the parent state).
 *
 * Props:
 *   label    — optional; if omitted the label row is not rendered
 *   onChange — called with a synthetic { target: { value: string } } event
 *              so existing handlers that do e.target.value continue to work
 */
export default function NumInput({
  id, label, tooltip, value, onChange,
  min, max, step, unit, error,
}) {
  const [raw, setRaw] = useState(value !== undefined ? String(value) : '');

  useEffect(() => {
    if (value !== undefined) setRaw(String(value));
  }, [value]);

  function handleChange(e) {
    const str = e.target.value;
    setRaw(str);
    onChange({ target: { value: str } });
  }

  return (
    <div className="space-y-1">
      {label !== undefined && (
        <div className="flex items-center gap-1.5">
          <label htmlFor={id} className="text-sm font-medium text-gray-700 leading-snug">
            {label}
          </label>
          {tooltip && <Tooltip text={tooltip} />}
        </div>
      )}
      <div className="relative">
        <input
          id={id}
          type="number"
          min={min}
          max={max}
          step={step}
          value={raw}
          onChange={handleChange}
          onFocus={(e) => e.target.select()}
          className={`w-full text-sm border rounded-lg px-3 py-2 text-gray-900 focus:outline-none focus:ring-1 transition-colors
            ${unit ? 'pr-10' : 'pr-3'}
            ${error
              ? 'border-red-400 focus:border-red-400 focus:ring-red-200 bg-red-50'
              : 'border-gray-200 focus:border-teal-300 focus:ring-teal-100'
            }`}
        />
        {unit && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400 pointer-events-none">
            {unit}
          </span>
        )}
      </div>
      {error && <p className="text-xs text-red-600 mt-0.5">{error}</p>}
    </div>
  );
}
