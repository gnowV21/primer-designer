// Number, unit and status formatting for the UI (UI review 2026-11-23).
// Same conventions as the PDF/CSV (backend utils/report_text.py):
//   60.0 °C · 47.6% · −6.10 (true minus) · value and unit joined by a no-break space.
// Status vocabulary: Pass / Warning / Fail, in status colours that are never the brand.

export const NBSP = ' ';
export const MINUS = '−';

/** ASCII hyphen-minus before a digit → true minus sign. */
export function signed(text) {
  return String(text).replace(/(^|[^\w.])-(?=\d)/g, `$1${MINUS}`);
}

function num(v) {
  if (v === null || v === undefined || v === '' || typeof v === 'boolean') return null;
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

/** "40 bp", "25 nt", "200 nM" — never broken between value and unit. */
export function withUnit(v, unit) {
  if (v === null || v === undefined || v === '') return '—';
  return unit ? `${signed(v)}${unit === '%' ? '' : NBSP}${unit}` : signed(v);
}

export function fmtTm(v, digits = 1) {
  const x = num(v);
  return x === null ? '—' : `${signed(x.toFixed(digits))}${NBSP}°C`;
}

export function fmtPct(v, digits = 1) {
  const x = num(v);
  return x === null ? '—' : `${signed(x.toFixed(digits))}%`;
}

/** ΔG with 2 decimals and a true minus sign (unit carried by the label, or add it). */
export function fmtDg(v, { unit = false } = {}) {
  const x = num(v);
  if (x === null) return '—';
  const s = signed(x.toFixed(2));
  return unit ? `${s}${NBSP}kcal/mol` : s;
}

// API levels → the one status vocabulary.
const STATUS = {
  SAFE: 'Pass', PASS: 'Pass', OK: 'Pass', DISCRIMINATED: 'Pass', NONE: 'Pass', LOW: 'Pass',
  ACCEPTABLE: 'Pass',
  MEDIUM: 'Warning', PARTIAL: 'Warning', WARNING: 'Warning',
  HIGH: 'Fail', CRITICAL: 'Fail', 'CO-AMPLIFIED': 'Fail', IDENTICAL: 'Fail', FAIL: 'Fail',
};

/** 'SAFE' → 'Pass', 'PARTIAL' → 'Warning', 'CO-AMPLIFIED' → 'Fail'; '' when unknown. */
export function statusOf(level) {
  return STATUS[String(level ?? '').toUpperCase()] || '';
}

/** 'CO-AMPLIFIED' → 'Co-amplified', 'SAFE' → 'Safe' (sentence case for API levels). */
export function levelWord(level) {
  const s = String(level ?? '').replace(/_/g, ' ').toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Tailwind classes of a status chip/box: green / amber / red, never brand. */
export const STATUS_CLASSES = {
  Pass:    'bg-green-50 border-green-200 text-green-700',
  Warning: 'bg-amber-50 border-amber-200 text-amber-800',
  Fail:    'bg-red-50 border-red-200 text-red-700',
  '':      'bg-slate-50 border-slate-200 text-slate-700',
};

export const STATUS_TEXT = {
  Pass: 'text-green-700', Warning: 'text-amber-800', Fail: 'text-red-700', '': 'text-slate-700',
};
