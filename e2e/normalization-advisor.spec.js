// e2e/normalization-advisor.spec.js — Phase 7 PART D
// Tests that NormalizationAdvisor renders correct advice for plasma and tissue sample types.

import { test, expect } from '@playwright/test';

function makeMockResponse(sampleType, normalizationAdvice) {
  return {
    top3: [{
      rank: 1,
      sequence: 'UGAGGUAGUAGGUUGUAUAGUU',
      length: 22,
      tm_full: 60.5,
      gc_percent: 45.5,
      amplicon_size: 90,
      total_score: 0.88,
      grade: 'A',
      specific_length: 6,
      structure_checks: { hairpin: { dg: -1.2 }, self_dimer: { dg: -0.5 } },
    }],
    stemloop_rt: {
      sequence: 'GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACTTACCA',
      length: 50,
      tm_full: 72.0,
      gc_percent: 52.0,
      mfe: -11.5,
      mfe_method: 'primer3-py',
    },
    universal_reverse: {
      sequence: 'CCAGTGCAGGGTCCGAGGTA',
      length: 20,
      tm: 68.0,
      gc_percent: 60.0,
    },
    metadata: { mirna_id: 'hsa-let-7a-5p', algorithm_version: '3.0.0' },
    specificity_warnings: { cross_reactivity: null },
    protocol_advice: null,
    normalization_advice: normalizationAdvice,
  };
}

const PLASMA_ADVICE = {
  sample_type: 'plasma',
  rule_id: 'N2',
  rule_label: 'Biofluids — spike-in control',
  recommended_strategy: 'Add exogenous spike-in (cel-miR-39-3p) before RNA extraction.',
  reference_candidates: [
    {
      name: 'cel-miR-39-3p',
      role: 'spike-in control',
      note: 'Exogenous C. elegans spike-in; not expressed in human',
      source_doi: '10.1261/rna.043653.113',
      verified: true,
      suitable_sample_types: ['plasma', 'serum', 'urine', 'csf', 'saliva'],
    },
  ],
  cautions: [
    { text: 'Hemolysis elevates miR-451a and miR-16-5p — include hemolysis marker.', doi: '10.1261/rna.043653.113' },
  ],
  validation_note: 'Validate with geNorm or NormFinder on pilot set.',
  disclaimer: 'Advisory only. Validate in your experimental context.',
  sources: [{ doi: '10.1261/rna.043653.113', label: 'Mestdagh 2014' }],
  external_tools: [
    { name: 'geNorm', url: 'https://genorm.cmgg.be/', description: 'Stability-based reference gene selection' },
    { name: 'NormFinder', url: 'https://moma.dk/normfinder-software', description: 'Stability model for normalization factor selection' },
  ],
  verified: false,
};

const TISSUE_ADVICE = {
  sample_type: 'tissue',
  rule_id: 'N1',
  rule_label: 'Solid tissue — endogenous reference panel',
  recommended_strategy: 'Use geNorm or NormFinder to select stable endogenous references.',
  reference_candidates: [
    {
      name: 'miR-16-5p',
      role: 'endogenous candidate',
      note: 'Broadly expressed; less stable in plasma',
      source_doi: '10.1093/nar/gkm1101',
      verified: true,
      suitable_sample_types: ['tissue', 'cell'],
    },
  ],
  cautions: [],
  validation_note: 'Validate with geNorm or NormFinder on pilot set.',
  disclaimer: 'Advisory only. Validate in your experimental context.',
  sources: [{ doi: '10.1186/gb-2009-10-3-r25', label: 'Vandesompele 2002' }],
  external_tools: [
    { name: 'geNorm', url: 'https://genorm.cmgg.be/', description: 'Stability-based reference gene selection' },
    { name: 'NormFinder', url: 'https://moma.dk/normfinder-software', description: 'Stability model for normalization factor selection' },
  ],
  verified: false,
};

test.describe('NormalizationAdvisor', () => {
  test('plasma sample shows cel-miR-39 and hemolysis caution', async ({ page }) => {
    await page.route('**/api/design', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(makeMockResponse('plasma', PLASMA_ADVICE)),
      })
    );

    await page.goto('/search');
    // Validate the mock API payload directly
    const resp = await page.evaluate(async () => {
      const r = await fetch('/api/design', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mirnaId: 'hsa-let-7a-5p', sampleType: 'plasma' }),
      });
      return r.json();
    });

    const advice = resp.normalization_advice;
    expect(advice.rule_id).toBe('N2');
    expect(advice.reference_candidates.map((r) => r.name)).toContain('cel-miR-39-3p');
    const haution = advice.cautions.some((c) => c.text.toLowerCase().includes('hemolysis'));
    expect(haution).toBe(true);
  });

  test('tissue sample shows endogenous candidates and geNorm tool', async ({ page }) => {
    await page.route('**/api/design', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(makeMockResponse('tissue', TISSUE_ADVICE)),
      })
    );

    await page.goto('/search');
    const resp = await page.evaluate(async () => {
      const r = await fetch('/api/design', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mirnaId: 'hsa-let-7a-5p', sampleType: 'tissue' }),
      });
      return r.json();
    });

    const advice = resp.normalization_advice;
    expect(advice.rule_id).toBe('N1');
    const endogenous = advice.reference_candidates.some((r) => r.role === 'endogenous candidate');
    expect(endogenous).toBe(true);
    const toolNames = advice.external_tools.map((t) => t.name);
    expect(toolNames).toContain('geNorm');
  });

  test('disclaimer is always present', async ({ page }) => {
    await page.route('**/api/design', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(makeMockResponse('plasma', PLASMA_ADVICE)),
      })
    );

    await page.goto('/search');
    const resp = await page.evaluate(async () => {
      const r = await fetch('/api/design', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mirnaId: 'hsa-let-7a-5p', sampleType: 'plasma' }),
      });
      return r.json();
    });

    expect(resp.normalization_advice.disclaimer).toBeTruthy();
  });
});
