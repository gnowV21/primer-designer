import Tooltip from './Tooltip.jsx';

export default function Toggle({ checked, onChange, label, tooltip, disabled = false }) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={`
          relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent
          transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-teal-100 focus:ring-offset-1
          ${disabled ? 'cursor-not-allowed opacity-50' : ''}
          ${checked ? 'bg-teal-600' : 'bg-slate-200'}
        `}
      >
        <span
          className={`
            pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow
            transform transition-transform duration-200 ease-in-out
            ${checked ? 'translate-x-4' : 'translate-x-0'}
          `}
        />
      </button>

      {label && (
        <span className={`text-xs font-medium ${checked ? 'text-teal-700' : 'text-slate-500'}`}>
          {typeof label === 'string' ? label : (checked ? 'ON' : 'OFF')}
        </span>
      )}
      {tooltip && <Tooltip text={tooltip} />}
    </div>
  );
}
