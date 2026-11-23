// Pure checks behind Parameters warnings (no React), so e2e unit specs can import them.
import { TIERED_P2_BEST_C } from '../constants/defaults.js';

/** C2 (2026-11-22): Ta so far outside the forward-primer Tm window that no candidate can
 *  reach P2 level 5 (|Tm − Ta| ≤ 1 °C): Ta < tmMin − 1 or Ta > tmMax + 1. */
export function taOutsideWindow(ta, tmMin, tmMax) {
  return ta < tmMin - TIERED_P2_BEST_C || ta > tmMax + TIERED_P2_BEST_C;
}

/** Kept warning (condition unchanged): Ta more than 5 °C above the lower end of the window. */
export function taAboveWindowLow(ta, tmMin) {
  return ta > tmMin + 5;
}

/** True when the normalization reference names the target miRNA itself
 *  ("hsa-miR-16-5p" vs "miR-16"); same rule as the PDF (backend report_pdf.same_reference). */
export function sameReference(target, reference) {
  const norm = (x) => String(x || '').trim().toLowerCase()
    .replace(/^[a-z]{3,5}-(?=(mir|let)-)/, '')
    .replace(/-[35]p$/, '');
  const t = norm(target);
  const r = norm(reference);
  return Boolean(t) && Boolean(r) && t === r;
}
