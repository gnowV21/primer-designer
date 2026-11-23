// Seed families for which a 7-nt RT overhang may help tell members apart (a suggestion
// only: 7 nt is off-label, RequiredGroup shows the warning). Matched on the seed (nt 2–8)
// of the mature sequence, the rule the family data uses, not on a family label: the
// label is a derived name and a substring match hit the wrong families (miR-290 for
// "mir-29", miR-302 for "mir-30") while the miR-17 family never matched (2026-11-23).
// Members: hsa, miRBase 22.1 mature.fa (backend/data/mirbase_22.1).
export const FAMILY_HINT_SEEDS = {
  GAGGUAG: {
    family: 'let-7',
    members: 'let-7a–i, miR-98 and 2 others (11 human miRNAs)',
  },
  AAAGUGC: {
    family: 'miR-17',
    members: 'miR-17, miR-20a/b, miR-106a/b, miR-93 and 2 others (8 human miRNAs)',
  },
  AGCACCA: {
    family: 'miR-29',
    members: 'miR-29a/b/c',
  },
  GUAAACA: {
    family: 'miR-30',
    members: 'miR-30a–e',
  },
};

/** Seed (nt 2–8) of a mature sequence, RNA letters; '' when too short. */
export function seedOf(matureSequence) {
  const s = (matureSequence || '').toUpperCase().replace(/T/g, 'U').replace(/[^ACGU]/g, '');
  return s.length >= 8 ? s.slice(1, 8) : '';
}

/** { family, text, suggestNt: 7 } for a sequence in one of the seed families, else null. */
export function getFamilyHint(matureSequence) {
  const fam = FAMILY_HINT_SEEDS[seedOf(matureSequence)];
  if (!fam) return null;
  return {
    family: fam.family,
    text: `This miRNA is in the ${fam.family} seed family (${fam.members}); members share the seed and differ only at a few 3′ positions, so a 7-nt overhang may help discriminate them.`,
    suggestNt: 7,
  };
}
