// NoBreak — render free text (API messages, notes) so that miRNA names, sequences and
// value+unit pairs never break across lines (UI review 2026-11-23):
//   "hsa-miR-16-5p", "UAGCAGCACG…", "39 °C", "25 bp", "−6.10 kcal/mol" stay on one line.
// The text itself is unchanged (copy/paste gives the same characters).
import { Fragment } from 'react';

const RX = new RegExp([
  String.raw`\b(?:[a-z]{3,5}-)?(?:miR|let|mir)-\d+[a-z]?(?:-\d+)?(?:-[35]p)?\b`,   // miRNA names
  String.raw`\b[ACGTU]{8,}\b`,                                                      // sequences
  String.raw`[5′3′']{1,2}-[ACGTU]{6,}-[35]['′]`,                                     // 5′-SEQ-3′
  String.raw`[−-]?\d+(?:\.\d+)?\s?(?:°C|nt|bp|mM|nM|µM|kcal/mol|%|s\b)`,             // value + unit
  String.raw`\b(?:Mg²⁺|Na⁺|K⁺)\s\d+(?:\.\d+)?`,
].join('|'), 'g');

export function noBreak(text) {
  if (typeof text !== 'string' || !text) return text;
  const out = [];
  let last = 0;
  for (const m of text.matchAll(RX)) {
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(<span key={m.index} className="whitespace-nowrap">{m[0]}</span>);
    last = m.index + m[0].length;
  }
  if (!out.length) return text;
  if (last < text.length) out.push(text.slice(last));
  return out.map((x, i) => (typeof x === 'string' ? <Fragment key={`t${i}`}>{x}</Fragment> : x));
}

export default function NoBreak({ children }) {
  return <>{noBreak(children)}</>;
}
