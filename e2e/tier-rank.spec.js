// Pure-function tests of the frontend tier key (frontend/src/utils/tierRank.js) and of
// rankReason, on all 8 branches of SPEC_ui_tiered_4.0.0 §2.4. Run by Playwright in Node
// (no page): the frontend has no unit-test runner and no dependency is added.
import { test, expect } from '@playwright/test';
import {
  bestRunIndices, compareTiered, decidingStep, equivalentInSilico, equivalentRanks, hasTiers,
  KEY_STEPS, tierKey, tierReason,
} from '../frontend/src/utils/tierRank.js';
import { rankReason } from '../frontend/src/utils/rankReason.js';

/** A tiered set; `o` overrides tier totals and flags. */
function mk(o = {}) {
  const s = {
    rank: o.rank ?? 1,
    sequence: o.sequence ?? 'ACGTGCTAGCTTATCAGACTGA',
    grade: 'A',
    v4_rule_violations: o.v4 ?? [],
    total_score: o.detailed ?? 90,
    ranking: {
      system: 'tiered',
      specificity: {
        blast: { score: o.s1 ?? 5, overall_risk: o.risk ?? 'SAFE', worst_hit: o.worstHit ?? null },
        assay_dcq: { score: o.s2 ?? 5, min_delta_cq: o.dcq ?? 9.5, worst_target: 'hsa-miR-x' },
        tm_margin: { score: o.s3 ?? 5, margin: o.margin ?? 25, worst_target: 'hsa-miR-y' },
        total: (o.s1 ?? 5) + (o.s2 ?? 5) + (o.s3 ?? 5),
        max: 15,
      },
      pcr: { tm_vs_ta: { score: o.p ?? 5, tm: o.tm ?? 60.0, ta: 60.0, diff: Math.abs((o.tm ?? 60.0) - 60.0) }, total: o.p ?? 5, max: 5 },
      flexible: {
        gc: { score: o.f1 ?? 5 }, gc_clamp: { score: o.f2 ?? 5 },
        binding_tm: { score: o.f4 ?? 5 }, structure: { score: o.f5 ?? 5, sub_scores: o.sub ?? { hairpin_tm: 5, dimer_dg: 5, end_dimer_tm: 5 } },
        total: (o.f1 ?? 5) + (o.f2 ?? 5) + (o.f4 ?? 5) + (o.f5 ?? 5),
        max: 20,
      },
      structure_veto: o.veto ?? false,
      binding_floor_fail: o.floor ?? false,
      eliminated: false,
      detailed_score: o.detailed ?? 90,
    },
  };
  return s;
}

test.describe('tier key comparator', () => {
  test('key order matches the backend rank_key', () => {
    expect(KEY_STEPS).toEqual(['specificity', 'structure_veto', 'binding_floor_fail', 'v4_violation',
      'pcr', 'flexible', 'tie_break', 'tm_vs_ta', 'sequence']);
    expect(tierKey(mk({ s1: 4, veto: true, v4: ['gc_clamp_fail'], p: 3, tm: 61.5 })))
      .toEqual([-14, 1, 0, 1, -3, -20, -90, 1.5, 'ACGTGCTAGCTTATCAGACTGA']);
  });

  test('S beats every later step; vetoes only split equal S', () => {
    const better = mk({ s1: 5, veto: true, floor: true, v4: ['gc_clamp_fail'], p: 1, f1: 1, detailed: 10 });
    const worse = mk({ s1: 4 });
    expect(compareTiered(better, worse)).toBeLessThan(0);
    const sorted = [mk({ veto: true, sequence: 'A' }), mk({ floor: true, sequence: 'B' }),
      mk({ v4: ['x'], sequence: 'C' }), mk({ sequence: 'D' })].sort(compareTiered);
    expect(sorted.map((s) => s.sequence)).toEqual(['D', 'C', 'B', 'A']);
  });

  test('Equivalent in silico = same S, vetoes, V4 step, P and F', () => {
    expect(equivalentInSilico(mk({ detailed: 95 }), mk({ detailed: 80 }))).toBe(true);
    expect(equivalentInSilico(mk(), mk({ f2: 4 }))).toBe(false);
    expect(equivalentInSilico(mk(), mk({ v4: ['gc_clamp_fail'] }))).toBe(false);
    const sets = [mk({ rank: 1 }), mk({ rank: 2, detailed: 70 }), mk({ rank: 3, s3: 4 })];
    expect(equivalentRanks(sets[0], sets)).toEqual([2]);
    expect(equivalentRanks(sets[2], sets)).toEqual([]);
  });

  test('V4 sets (no ranking) are not tiered', () => {
    expect(hasTiers({ total_score: 90, grade: 'Excellent' })).toBe(false);
    expect(equivalentInSilico({ total_score: 1 }, mk())).toBe(false);
  });

  test('best run by the same key', () => {
    expect(bestRunIndices([mk({ s1: 4 }), mk(), mk({ s1: 3 })])).toEqual([1]);
    expect(bestRunIndices([mk(), mk()])).toEqual([]);                 // all equal: no star
    expect(bestRunIndices([mk(), { total_score: 99 }])).toEqual([]);  // mixed: not comparable
  });
});

test.describe('rankReason — 8 branches (SPEC_ui §2.4)', () => {
  test('1. specificity', () => {
    const r = tierReason(mk(), mk({ s1: 3, risk: 'MEDIUM' }));
    expect(r.step).toBe('specificity');
    expect(r.text).toBe('#1 is more specific (S 15 vs 13): BLAST SAFE vs MEDIUM.');
  });
  test('2. structure veto', () => {
    const r = tierReason(mk(), mk({ veto: true, f5: 1, sub: { hairpin_tm: 5, dimer_dg: 1, end_dimer_tm: 5 } }));
    expect(r.step).toBe('structure_veto');
    expect(r.text).toBe('Same specificity; #2 has a structure veto (dimer ΔG).');
  });
  test('3. binding floor', () => {
    const r = tierReason(mk(), mk({ floor: true, f4: 1 }));
    expect(r.step).toBe('binding_floor_fail');
    expect(r.text).toContain('below the 39 °C floor');
  });
  test('4. V4 rule', () => {
    const r = tierReason(mk(), mk({ v4: ['gc_clamp_fail'] }));
    expect(r.step).toBe('v4_violation');
    expect(r.text).toBe('Same specificity; #2 is outside a V4 rule (gc_clamp_fail).');
  });
  test('5. PCR', () => {
    const r = tierReason(mk(), mk({ p: 4, tm: 61.4 }));
    expect(r.step).toBe('pcr');
    expect(r.text).toBe('Same specificity; #1 is closer to Ta (|ΔTm| 0.0 vs 1.4 °C).');
  });
  test('6. flexible', () => {
    const r = tierReason(mk(), mk({ f2: 3 }));
    expect(r.step).toBe('flexible');
    expect(r.text).toBe('Same specificity and PCR; #1 scores higher on flexible criteria (F 20 vs 18): GC clamp 5 vs 3.');
  });
  test('7. tie-break', () => {
    const r = tierReason(mk({ detailed: 92.3 }), mk({ detailed: 90.1 }));
    expect(r.step).toBe('tie_break');
    expect(r.text).toBe('Equivalent in silico on every tier; ordered by tie-break score (+2.2).');
  });
  test('8. identical (tail variants)', () => {
    const r = tierReason(mk({ sequence: 'AACGT' }), mk({ sequence: 'TTCGT' }));
    expect(r.step).toBe('identical');
    expect(r.text).toBe('Identical on every criterion (5′-tail variants); the order is arbitrary but fixed.');
    expect(decidingStep(mk({ sequence: 'AACGT' }), mk({ sequence: 'TTCGT' }))).toBe(8);
  });
  test('same tie-break score, closer to Ta (|Tm − Ta| step)', () => {
    const r = tierReason(mk({ tm: 60.2 }), mk({ tm: 60.4 }));
    expect(r.step).toBe('tm_vs_ta');
  });
  test('rankReason dispatches: tiered vs V4 (U5)', () => {
    expect(rankReason(mk(), mk({ s2: 3 }))).toMatch(/^#1 is more specific/);
    const v4a = { total_score: 92, scores: { gc_clamp: 100 }, weights: { gc_clamp: 0.06 } };
    const v4b = { total_score: 85, scores: { gc_clamp: 50 }, weights: { gc_clamp: 0.06 } };
    expect(rankReason(v4a, v4b)).toMatch(/^#1 ranks 7\.0 points above #2/);
  });
});
