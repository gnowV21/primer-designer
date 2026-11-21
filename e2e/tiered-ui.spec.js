// E2E — tiered ranking display (algorithm 4.0.0, docs/SPEC_ui_tiered_4.0.0.md §3 a–g).
// Real designs go through the UI with the frontend defaults (BLAST cache warmed by
// global-setup.js). Mocked cases take a real /api/design response and change only the
// fields under test (page.route + route.fetch), so the rest of the page stays real.
import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { PLACEHOLDER, DESIGN_TIMEOUT, WARM_MIRNAS } from './helpers.js';

const MIR21 = WARM_MIRNAS.find((m) => m.name === 'hsa-miR-21-5p').sequence;
const LET7A = WARM_MIRNAS.find((m) => m.name === 'hsa-let-7a-5p').sequence;

async function design(page, sequence) {
  await page.goto('/design');
  await page.getByPlaceholder(PLACEHOLDER).fill(sequence);
  await page.evaluate(() => {
    const s = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Search');
    if (s) s.click();
  });
  const btn = page.getByRole('button', { name: 'Design Primers →' });
  await expect(btn).toBeEnabled({ timeout: 8000 });
  await btn.click();
  await expect(page).toHaveURL('/results', { timeout: DESIGN_TIMEOUT });
}

/** Serve the real design response after `mutate(json)`. */
async function mockDesign(page, mutate) {
  await page.route('**/api/design', async (route) => {
    const response = await route.fetch();
    const json = await response.json();
    mutate(json);
    await route.fulfill({ response, json });
  });
}

const clone = (x) => JSON.parse(JSON.stringify(x));

// ── (a) grade + 3 tiers, no gauge ────────────────────────────────────

test('(a) a tiered card shows grade + three tiers and no score gauge', async ({ page }) => {
  await design(page, MIR21);
  const first = page.getByTestId('card-tier-header').first();
  await expect(first).toBeVisible();
  await expect(first.getByTestId('grade-badge')).toHaveText(/^[ABC]/);
  await expect(first).toContainText(/S \d+\/15/);
  const summary = page.getByTestId('tier-summary').first();
  await expect(summary.getByTestId('tier-specificity')).toContainText(/\d+\/15/);
  await expect(summary.getByTestId('tier-pcr')).toContainText(/\d+\/5/);
  await expect(summary.getByTestId('tier-flexible')).toContainText(/\d+\/20/);
  await expect(page.getByTestId('score-gauge')).toHaveCount(0);
  // The tie-break score is only in the collapsed detail table, with its label.
  await page.getByText('Criteria detail').first().click();
  await expect(page.getByText('Tie-break score — used only when all tiers are equal').first()).toBeVisible();
});

// ── (b) fallback banner on let-7a-5p ──────────────────────────────────

test('(b) hsa-let-7a-5p shows the specificity-fallback banner naming let-7d-5p', async ({ page }) => {
  await design(page, LET7A);
  const banner = page.getByTestId('banner-fallback');
  await expect(banner).toBeVisible();
  await expect(banner).toContainText('hsa-let-7d-5p');
  await expect(banner).toContainText('Include a cross-reactivity control (synthetic off-target) in the wet-lab run.');
  await expect(page.getByTestId('grade-badge').first()).toHaveText(/^C/);
});

// ── (c) rank reason: decided at S, and Equivalent in silico ──────────

test('(c1) rank reason names the specificity tier when S decides', async ({ page }) => {
  await mockDesign(page, (j) => {
    const r2 = j.top3[1].ranking;
    r2.specificity.blast = { ...r2.specificity.blast, score: 3, overall_risk: 'MEDIUM' };
    r2.specificity.total = j.top3[0].ranking.specificity.total - 2;
  });
  await design(page, MIR21);
  await expect(page.getByTestId('rank-reason')).toContainText(/^#1 is more specific \(S \d+ vs \d+\): BLAST \w+ vs MEDIUM/);
});

test('(c2) two sets equal on every tier are labelled "Equivalent in silico"', async ({ page }) => {
  await mockDesign(page, (j) => {
    const [a, b] = j.top3;
    b.ranking = { ...clone(a.ranking), detailed_score: a.ranking.detailed_score - 3 };
    b.v4_rule_violations = clone(a.v4_rule_violations || []);
    j.top3.length = 2;
  });
  await design(page, MIR21);
  await expect(page.getByTestId('rank-reason'))
    .toHaveText('Equivalent in silico on every tier; ordered by tie-break score (+3.0).');
  await expect(page.getByTestId('equivalent-label').first()).toContainText('Equivalent in silico to #');
});

// ── (d) blast_unavailable ─────────────────────────────────────────────

test('(d) BLAST unavailable: banner, S1 "not run", max 10, grade B', async ({ page }) => {
  await mockDesign(page, (j) => {
    j.ranking_summary.blast_available = false;
    j.ranking_summary.blast_unavailable_reason = 'BLAST+ not found';
    for (const s of j.top3) {
      const sp = s.ranking.specificity;
      sp.total -= sp.blast.score;
      sp.max = 10;
      sp.blast = { score: null, overall_risk: null, medium_hits: null, worst_hit: null };
      s.grade = 'B';
      s.grade_reasons = ['BLAST unavailable: S1 unknown, grade capped at B'];
    }
  });
  await design(page, MIR21);
  await expect(page.getByTestId('banner-blast-unavailable'))
    .toContainText('Specificity ranking reduced to S2 + S3 (BLAST not run)');
  await expect(page.getByTestId('card-tier-header').first()).toContainText(/S \d+\/10/);
  await expect(page.getByTestId('grade-badge').first()).toContainText('B — BLAST unavailable');
  await expect(page.getByTestId('tier-specificity').first()).toContainText('not run');
});

// ── (e) V4 response without ranking (U5) ─────────────────────────────

test('(e) a V4 response without ranking keeps the gauge + score breakdown', async ({ page }) => {
  await mockDesign(page, (j) => {
    for (const s of j.top3) { delete s.ranking; s.grade = 'Excellent'; s.grade_reasons = null; }
    delete j.ranking_summary;
    j.metadata.scoring_system = 'v4';
  });
  await design(page, MIR21);
  await expect(page.getByTestId('score-gauge').first()).toBeVisible();
  await expect(page.getByTestId('tier-summary')).toHaveCount(0);
  await expect(page.getByTestId('rank-reason')).not.toContainText('more specific');
});

// ── (f) old History record (saved before 4.0.0) ──────────────────────

test('(f) a History record saved before 4.0.0 shows the V4 score and opens', async ({ page, request }) => {
  const body = {
    sequence: { matureSequence: MIR21, mirnaId: 'hsa-miR-21-5p' }, scoringSystem: 'v4',
    thermodynamic: {}, primerConstraints: {}, qpcr: {}, detectionMethod: {}, experimentalContext: {},
  };
  const res = await request.post('/api/design', { data: body, timeout: 60_000 });
  const results = await res.json();
  delete results.metadata.scoring_system;           // a 3.8.x response had no such field
  await page.goto('/history');
  await page.evaluate(async ({ results, body }) => {
    await new Promise((resolve, reject) => {
      const req = indexedDB.open('hglab-primer-designer', 1);
      req.onupgradeneeded = () => req.result.createObjectStore('designs', { keyPath: 'id', autoIncrement: true });
      req.onsuccess = () => {
        const tx = req.result.transaction('designs', 'readwrite');
        tx.objectStore('designs').add({
          createdAt: Date.now(), mirnaId: 'hsa-miR-21-5p', sequence: body.sequence.matureSequence,
          topScore: results.top3[0].total_score, grade: results.top3[0].grade,
          algorithmVersion: '3.8.2', params: body, results,
        });
        tx.oncomplete = () => { req.result.close(); resolve(); };
        tx.onerror = () => reject(tx.error);
      };
      req.onerror = () => reject(req.error);
    });
  }, { results, body });
  await page.reload();
  const row = page.getByRole('button', { name: /hsa-miR-21-5p/ }).first();
  await expect(row).toContainText(/best [\d.]+ \(\w+\)/);
  await expect(row).toContainText('v3.8.2');
  await row.click();
  await expect(page).toHaveURL('/results');
  await expect(page.getByTestId('score-gauge').first()).toBeVisible();
  await expect(page.getByTestId('tier-summary')).toHaveCount(0);
});

// ── (g) CSV export columns ───────────────────────────────────────────

test('(g) the CSV export carries the tier columns', async ({ page }) => {
  await design(page, MIR21);
  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 15000 }),
    page.getByRole('button', { name: /Download CSV/ }).click(),
  ]);
  const text = readFileSync(await download.path(), 'utf8');
  const header = text.split(/\r?\n/).find((l) => l.startsWith('Set_Rank'));
  for (const col of ['scoring_system', 'grade', 'grade_reasons', 'S1', 'S2', 'S3', 'S_total', 'P_total',
    'F_total', 'structure_veto', 'binding_floor_fail', 'v4_rule_violations', 'tie_break_score']) {
    expect(header.split(',')).toContain(col);
  }
  expect(header).not.toContain('Total_Score');
  const row1 = text.split(/\r?\n/).find((l) => l.startsWith('1,Forward'));
  expect(row1).toContain(',tiered,');
});

// ── soft-veto and V4-rule chips on a real design ─────────────────────

test('hsa-miR-590-3p #1 shows the binding-floor chip, the V4-rule chip and grade B', async ({ page }) => {
  await design(page, WARM_MIRNAS.find((m) => m.name === 'hsa-miR-590-3p').sequence);
  const flags = page.getByTestId('tier-flags').first();
  await expect(flags).toContainText('Binding Tm < 39 °C');
  await expect(flags).toContainText('Outside V4 rule: No G/C in the last 3 nt');
  await expect(page.getByTestId('grade-badge').first()).toHaveText(/^B/);
  // advice for a binding Tm below the floor (review panel A5): on the open #1 card
  await expect(page.getByTestId('low-binding-tm').first()).toContainText('Ta ≈ 50 °C');
});

// ── review panel 2026-11-18: page order and the cut warnings ─────────

test('results read verdict → comparison → shared primers → cards, without the cut notes', async ({ page }) => {
  await design(page, LET7A);
  const y = async (id) => (await page.getByTestId(id).first().boundingBox()).y;
  const order = [await y('banner-fallback'), await y('rank-reason'), await y('set-comparison'),
    await y('shared-primers'), await y('card-tier-header')];
  expect([...order].sort((a, b) => a - b)).toEqual(order);
  await expect(page.getByTestId('set-comparison').locator('tbody tr')).toHaveCount(3);
  // the RT primer and the reverse appear once (shared), not again in each card
  await expect(page.getByText('RT (stem-loop)', { exact: true })).toHaveCount(0);
  for (const cut of ['3′ end is T', 'scored 75/100', 'SYBR Green mode', 'Tm (full)', 'Fwd × Universal Rev']) {
    await expect(page.getByText(cut)).toHaveCount(0);
  }
  // the 3′-isomiR finding is one line; the explanation is behind "Why"
  await expect(page.getByTestId('isomir-note')).toContainText('3′ isomiRs:');
  await expect(page.getByText('Nejad et al. 2018')).toBeHidden();
});

// ── 3′ isoforms (isomiRdb): table in "Why", dominant isoform on the main line ──

test('miR-21-5p: "Why" shows the 3′ isoform table with three variants', async ({ page }) => {
  await design(page, MIR21);
  const note = page.getByTestId('isomir-note');
  await expect(note).toContainText('3′ isomiRs:');
  await expect(page.getByTestId('isomir-table')).toBeHidden();
  await note.getByText('Why').click();
  const table = page.getByTestId('isomir-table');
  await expect(table).toContainText('Most common 3′ isoforms (isomiRdb, pooled)');
  await expect(table.getByTestId('isomir-row')).toHaveCount(3);
  await expect(table).toContainText('miRBase 22.1 end');
  await expect(table).toContainText('0–4 Ct later · n = 2 miRNAs');
  await expect(page.getByTestId('isomir-dominant')).toHaveCount(0);
});

test('miR-222-3p: the dominant 3′ isoform is on the main line, no extra banner', async ({ page }) => {
  await design(page, WARM_MIRNAS.find((m) => m.name === 'hsa-miR-222-3p').sequence);
  const line = page.getByTestId('isomir-dominant');
  await expect(line).toContainText('most common 3′ form +3 nt, 36% of reads (pooled) vs 9% with the miRBase end');
  await expect(page.getByText(/^Dominant 3' isoform:/)).toBeHidden();      // full text behind "Why"
  await expect(page.getByTestId('critical-warning').filter({ hasText: 'Dominant' })).toHaveCount(0);
  await page.getByTestId('isomir-note').getByText('Why').click();
  await expect(page.getByTestId('isomir-table')).toContainText('not measured (≥ 3 nt)');
  await expect(page.getByText(/^Dominant 3' isoform:/)).toBeVisible();
});

test('species "Other": the screen fell back to human and the page says so', async ({ page }) => {
  await mockDesign(page, (j) => {
    j.ranking_summary.screen_species = 'hsa';
    j.ranking_summary.screen_species_assumed = true;
  });
  await design(page, MIR21);
  await expect(page.getByTestId('banner-species-assumed')).toContainText('human (hsa)');
});

// ── OffTargetPanel: design-time BLAST, then the full hit list agrees (SPEC_ui §2.5) ──

test('"Show all hits" returns the same overall risk as the design-time BLAST', async ({ page }) => {
  await design(page, MIR21);
  const card = page.getByTestId('design-blast').first();
  await expect(card).toBeVisible();
  const designRisk = (await card.locator('span').first().textContent()).trim();
  await page.getByRole('button', { name: 'Show all hits' }).first().click();
  await expect(page.getByText('off-target risk').first()).toBeVisible({ timeout: 70_000 });
  await expect(page.getByTestId('blast-mismatch')).toHaveCount(0);
  await expect(page.getByText('RT step included').first()).toBeVisible();
  expect(designRisk).toMatch(/SAFE|MEDIUM|HIGH|CRITICAL/);
});

test('ThermoTable shows cycle-1 occupancy for tiered sets', async ({ page }) => {
  await design(page, MIR21);
  await page.getByRole('button', { name: /Show scientific details/ }).click();
  const row = page.getByRole('row', { name: /Cycle-1 occupancy/ });
  await expect(row).toContainText('%');
});
