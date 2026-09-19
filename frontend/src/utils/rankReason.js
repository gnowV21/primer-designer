// One-sentence, bench-level answer to "why is set #1 above set #2?" (audit UX-03).
// Uses the same effective weights as the total, so the named criteria are the
// ones that actually moved the ranking.
import { CRITERION_LABELS } from './scoreSeverity.js';

const TIE_POINTS = 1.0;       // total-score gap below which the sets are called a tie
const MIN_CONTRIB = 0.3;      // ignore criteria that moved the total by < 0.3 points

function contributions(a, b) {
  const w = a?.weights || {};
  return Object.keys(w)
    .filter((k) => typeof a.scores?.[k] === 'number' && typeof b.scores?.[k] === 'number')
    .map((k) => ({ key: k, pts: (a.scores[k] - b.scores[k]) * w[k] }))
    .filter((c) => Math.abs(c.pts) >= MIN_CONTRIB)
    .sort((x, y) => Math.abs(y.pts) - Math.abs(x.pts));
}

const label = (k) => CRITERION_LABELS[k] || k.replace(/_/g, ' ');
const list = (cs) => cs.map((c) => `${label(c.key)} (${c.pts > 0 ? '+' : ''}${c.pts.toFixed(1)})`).join(', ');

export function rankReason(first, second) {
  if (!first || !second) return null;
  const gap = (first.total_score ?? 0) - (second.total_score ?? 0);
  const cs = contributions(first, second);
  const ahead = cs.filter((c) => c.pts > 0).slice(0, 2);
  const behind = cs.filter((c) => c.pts < 0).slice(0, 1);
  if (gap < TIE_POINTS) {
    return `#1 and #2 are practically tied (${gap.toFixed(1)} points apart) — either is a sound choice; `
      + 'pick on practical grounds such as amplicon length or synthesis cost.';
  }
  let s = `#1 ranks ${gap.toFixed(1)} points above #2`;
  s += ahead.length ? `, mainly on ${list(ahead)}` : '';
  s += behind.length ? `; #2 is better on ${list(behind)}` : '';
  return `${s}.`;
}
