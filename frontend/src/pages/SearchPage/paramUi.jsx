// Small layout pieces shared by the Parameters groups (Required / Flexible / Assay setup).

export function WarnBox({ text, testId }) {
  return (
    <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed"
      data-testid={testId}>
      {text}
    </p>
  );
}

export function SubDivider({ label, note }) {
  return (
    <div className="pt-1 space-y-0.5">
      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold text-slate-500 shrink-0">
          {label}
        </span>
        <div className="flex-1 h-px bg-slate-100" />
      </div>
      {note && <p className="text-xs text-slate-500">{note}</p>}
    </div>
  );
}
