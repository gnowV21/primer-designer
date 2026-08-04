// e2e/export-checklist.spec.js — Phase 7 PART E
// Tests that PDF/CSV exports include MIQE validation checklist.

import { test, expect } from '@playwright/test';

const SAMPLE_RESULTS = {
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
  specificity_warnings: {
    cross_reactivity: {
      cross_reactivity: [
        { sibling: 'hsa-let-7b-5p', risk: 'LOW', mismatch: 2, delta_tm: 5.5 },
      ],
    },
  },
};

test.describe('Export MIQE checklist', () => {
  test('CSV download contains VALIDATION CHECKLIST header', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const responseBody = await page.evaluate(async (results) => {
      const r = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format: 'csv', results, include_checklist: true }),
      });
      return r.text();
    }, SAMPLE_RESULTS);

    expect(responseBody).toContain('VALIDATION CHECKLIST');
  });

  test('CSV has 8 checklist items', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const responseBody = await page.evaluate(async (results) => {
      const r = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format: 'csv', results, include_checklist: true }),
      });
      return r.text();
    }, SAMPLE_RESULTS);

    const start = responseBody.indexOf('# VALIDATION CHECKLIST');
    expect(start).toBeGreaterThan(-1);
    const block = responseBody.slice(start);
    const dataRows = block
      .split('\n')
      .filter((l) => l && !l.startsWith('#') && !l.startsWith('Item,'));
    expect(dataRows.length).toBe(8);
  });

  test('CSV checklist omitted when include_checklist=false', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const responseBody = await page.evaluate(async (results) => {
      const r = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format: 'csv', results, include_checklist: false }),
      });
      return r.text();
    }, SAMPLE_RESULTS);

    expect(responseBody).not.toContain('VALIDATION CHECKLIST');
  });

  test('PDF download returns valid PDF bytes (or 503 if reportlab missing)', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const { status, contentType, firstBytes } = await page.evaluate(async (results) => {
      const r = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format: 'pdf', results, include_checklist: true }),
      });
      const buf = await r.arrayBuffer();
      const bytes = Array.from(new Uint8Array(buf.slice(0, 4)));
      return { status: r.status, contentType: r.headers.get('content-type'), firstBytes: bytes };
    }, SAMPLE_RESULTS);

    if (status === 503) {
      // reportlab not installed on this server — acceptable fallback
      expect(contentType).toContain('application/json');
    } else {
      expect(status).toBe(200);
      expect(contentType).toBe('application/pdf');
      // PDF magic: %PDF → [37, 80, 68, 70]
      expect(firstBytes).toEqual([37, 80, 68, 70]);
    }
  });
});
