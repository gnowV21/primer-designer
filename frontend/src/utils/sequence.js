// Normalise a pasted mature-miRNA sequence to RNA (audit UX-01).
// A pure DNA paste (T, no U) is converted T→U instead of rejected — the most
// common paste source (primer sheets, genome browsers) is DNA. A sequence that
// mixes T and U is ambiguous and is still rejected.
export const DNA_CONVERTED_NOTE = 'DNA sequence detected — converted T→U (RNA).';

export function toRna(raw) {
  const s = raw.trim().toUpperCase().replace(/\s+/g, '');
  const hasT = s.includes('T');
  if (hasT && s.includes('U')) {
    return { seq: s, converted: false, error: 'Sequence mixes T and U — paste either RNA (U) or DNA (T).' };
  }
  return { seq: hasT ? s.replace(/T/g, 'U') : s, converted: hasT, error: null };
}
