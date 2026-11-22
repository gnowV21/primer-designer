// E2E — criteria groups Required / Flexible and the UI default conditions (2026-11-22,
// docs/REVIEW_panel_4.0.0.md §13). Display and request-body changes only: algorithm
// 4.0.0 and the /api/design JSON are unchanged.
import { test, expect } from '@playwright/test';
import { DEFAULTS } from '../frontend/src/constants/defaults.js';
import { buildDesignBody, legacySaltNote, phApplied, thermoForRequest } from '../frontend/src/utils/designRequest.js';
import { taOutsideWindow } from '../frontend/src/utils/paramChecks.js';
import { PLACEHOLDER, DESIGN_TIMEOUT, WARM_MIRNAS, openParameters } from './helpers.js';

const MIR21 = WARM_MIRNAS.find((m) => m.name === 'hsa-miR-21-5p').sequence;

function defaultForm() {
  return {
    sequence: { ...DEFAULTS.sequence }, thermodynamic: { ...DEFAULTS.thermodynamic },
    primerConstraints: { ...DEFAULTS.primerConstraints }, qpcr: { ...DEFAULTS.qpcr },
    detectionMethod: { ...DEFAULTS.detectionMethod }, experimentalContext: { ...DEFAULTS.experimentalContext },
  };
}

// ── UI default conditions = API defaults (C1) ───────────────────────────

test.describe('UI default body', () => {
  test('sends 50 mM monovalent salt: K⁺ 0 and no pH unless the user changed it', () => {
    const body = buildDesignBody(defaultForm());
    expect(body.thermodynamic.saltConcentration).toBe(50);
    expect(body.thermodynamic.kPlusConc).toBe(0);
    expect('bufferPH' in body.thermodynamic).toBe(false);
    expect(phApplied(DEFAULTS.thermodynamic)).toBe(false);
  });
  test('a pH the user changed is sent (Tris term applied)', () => {
    const t = { ...DEFAULTS.thermodynamic, bufferPH: 8.0 };
    expect(phApplied(t)).toBe(true);
    expect(thermoForRequest(t).bufferPH).toBe(8.0);
  });
  test('a run designed with extra K⁺ gets one line; the default gets none', () => {
    expect(legacySaltNote(thermoForRequest(DEFAULTS.thermodynamic))).toBeNull();
    expect(legacySaltNote({ saltConcentration: 50, kPlusConc: 50, bufferPH: 8.4 }))
      .toBe('Designed with K⁺ 50 mM + Na⁺ 50 mM (effective 103.1 mM); current default is 50 mM total.');
  });
  test('the designer posts that body', async ({ page }) => {
    await page.route('**/api/design', (route) => route.abort());
    const posted = page.waitForRequest((r) => r.url().includes('/api/design') && r.method() === 'POST');
    await page.goto('/design');
    await page.getByPlaceholder(PLACEHOLDER).fill(MIR21);
    await page.evaluate(() => {
      const s = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Search');
      if (s) s.click();
    });
    const btn = page.getByRole('button', { name: 'Design Primers →' });
    await expect(btn).toBeEnabled({ timeout: 8000 });
    await btn.click();
    const t = (await posted).postDataJSON().thermodynamic;
    expect(t.kPlusConc).toBe(0);
    expect(t.saltConcentration).toBe(50);
    expect('bufferPH' in t).toBe(false);
  });
});

// ── C2: Ta outside the forward-primer Tm window ─────────────────────────

test.describe('Ta outside the Tm window (P2 cannot reach level 5)', () => {
  test('rule: Ta < tmMin − 1 or Ta > tmMax + 1', () => {
    expect(taOutsideWindow(56, 58, 62)).toBe(true);    // below the window
    expect(taOutsideWindow(57, 58, 62)).toBe(false);   // 1 °C below: Tm 58 still gives |Tm − Ta| ≤ 1
    expect(taOutsideWindow(60, 58, 62)).toBe(false);   // inside
    expect(taOutsideWindow(63, 58, 62)).toBe(false);
    expect(taOutsideWindow(64, 58, 62)).toBe(true);    // above the window
  });

  test('the warning shows at Ta 56 and 64, not at 57 or 60', async ({ page }) => {
    await page.goto('/design');
    await openParameters(page);
    await page.getByText('Flexible', { exact: true }).click();
    const ta = page.locator('#qpcr-ta');
    const warn = page.getByTestId('ta-window-warning');
    await expect(warn).toHaveCount(0);                     // default 60
    for (const [v, shown] of [['56', true], ['57', false], ['60', false], ['64', true]]) {
      await ta.fill(v);
      await ta.blur();
      if (shown) {
        await expect(warn).toBeVisible();
        await expect(warn).toContainText('Ta is outside the forward-primer Tm window (58–62 °C), so P2 cannot reach its best level. Consider setting the window to Ta ± 2 °C.');
      } else {
        await expect(warn).toHaveCount(0);
      }
    }
  });
});

// ── Parameters grouped by effect; tooltips ──────────────────────────────

test('Parameters: Required, Flexible, Assay setup in that order, length marked unused', async ({ page }) => {
  await page.goto('/design');
  await openParameters(page);
  const titles = ['Required', 'Flexible', 'Assay setup', 'Detection Method', 'Experimental Context'];
  const tops = [];
  for (const t of titles) tops.push((await page.getByText(t, { exact: true }).first().boundingBox()).y);
  for (let i = 1; i < tops.length; i++) expect(tops[i]).toBeGreaterThan(tops[i - 1]);
  await page.getByText('Assay setup', { exact: true }).click();
  await expect(page.getByText('Primer length (nt) — not used by the ranking (engine uses 18–27 nt)')).toBeVisible();
  await page.getByText('Flexible', { exact: true }).click();
  await expect(page.getByText(/Monovalent cations \(Na\+\/K\+ total\), mM/)).toBeVisible();
  await expect(page.locator('#thermo-k')).toHaveValue('0');
});

// ── Results: criteria panel and the legacy K⁺ line ──────────────────────

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

test('the criteria panel opens from a card and explains the default Ta', async ({ page }) => {
  await design(page, MIR21);
  await expect(page.getByTestId('legacy-salt-note')).toHaveCount(0);
  await page.getByTestId('open-criteria').first().click();
  const panel = page.getByTestId('criteria-panel');
  await expect(panel).toBeVisible();
  await expect(panel.getByTestId('criteria-required')).toContainText('CO-AMPLIFIED eliminated');
  await expect(panel.getByTestId('criteria-flexible')).toContainText('1. No critical weakness');
  const why = panel.getByTestId('why-default-ta');
  await expect(why).toContainText('Why the default Ta equals the forward-primer Tm');
  await expect(why).toContainText('62.93 °C');
  await expect(why).toContainText('PRIMER_OPT_TM 60.0 °C');
  await expect(why).toContainText('so Tm(200 nM) ≈ Ta matches Ta ≈ Tm(real) − 3');
  await expect(panel).not.toContainText('V4');
  await page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
});

test('a History record designed with K⁺ 50 mM shows one line and is not changed', async ({ page, request }) => {
  const results = await (await request.post('/api/design', {
    data: { sequence: { matureSequence: MIR21, mirnaId: 'hsa-miR-21-5p' },
      thermodynamic: {}, primerConstraints: {}, qpcr: {}, detectionMethod: {}, experimentalContext: {} },
    timeout: 60_000,
  })).json();
  const params = { ...defaultForm(), sequence: { ...DEFAULTS.sequence, matureSequence: MIR21 },
    thermodynamic: { ...DEFAULTS.thermodynamic, kPlusConc: 50, bufferPH: 8.4 } };
  await page.goto('/history');
  await page.evaluate(async ({ results, params }) => {
    await new Promise((resolve, reject) => {
      const req = indexedDB.open('hglab-primer-designer', 1);
      req.onupgradeneeded = () => req.result.createObjectStore('designs', { keyPath: 'id', autoIncrement: true });
      req.onsuccess = () => {
        const tx = req.result.transaction('designs', 'readwrite');
        tx.objectStore('designs').add({ createdAt: Date.now(), mirnaId: 'legacy-k50', sequence: params.sequence.matureSequence,
          grade: results.top3[0].grade, scoringSystem: 'tiered', algorithmVersion: '4.0.0', params, results });
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      };
      req.onerror = () => reject(req.error);
    });
  }, { results, params });
  await page.reload();
  await page.getByText('legacy-k50').click();
  await expect(page).toHaveURL('/results');
  await expect(page.getByTestId('legacy-salt-note'))
    .toHaveText('Designed with K⁺ 50 mM + Na⁺ 50 mM (effective 103.1 mM); current default is 50 mM total.');
  // the stored record keeps its K⁺ 50 mM
  const k = await page.evaluate(() => new Promise((resolve) => {
    const req = indexedDB.open('hglab-primer-designer', 1);
    req.onsuccess = () => {
      const g = req.result.transaction('designs').objectStore('designs').getAll();
      g.onsuccess = () => resolve(g.result.find((d) => d.mirnaId === 'legacy-k50').params.thermodynamic.kPlusConc);
    };
  }));
  expect(k).toBe(50);
});
