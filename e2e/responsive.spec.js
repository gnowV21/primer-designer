// E2E — phone layout guard (320 px, the narrowest common width).
// Every page must fit without sideways scrolling, and all four nav tabs must be
// visible without scrolling the tab strip.

import { test, expect } from '@playwright/test';
import { PLACEHOLDER, DESIGN_TIMEOUT, WARM_MIRNAS } from './helpers.js';

async function horizontalOverflow(page) {
  return page.evaluate(() => {
    const main = document.querySelector('main');
    const strip = [...document.querySelectorAll('nav div')].find((d) => getComputedStyle(d).overflowX === 'auto');
    return {
      main: main.scrollWidth - main.clientWidth,
      nav: strip ? strip.scrollWidth - strip.clientWidth : 0,
    };
  });
}

test.describe('320 px layout', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 800 });
  });

  for (const path of ['/home', '/design', '/analyze', '/history', '/benchmark', '/no-such-page']) {
    test(`${path} fits without horizontal scroll`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
      expect(await horizontalOverflow(page)).toEqual({ main: 0, nav: 0 });
    });
  }

  test('/results fits without horizontal scroll', async ({ page }) => {
    await page.goto('/design');
    await page.getByPlaceholder(PLACEHOLDER).fill('UAGCUUAUCAGACUGAUGUUGA');
    await page.evaluate(() => {
      const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === 'Search');
      if (b) b.click();
    });
    const designBtn = page.getByRole('button', { name: 'Design Primers →' });
    await expect(designBtn).toBeEnabled({ timeout: 8000 });
    await designBtn.click();
    await expect(page).toHaveURL('/results', { timeout: 30000 });
    expect(await horizontalOverflow(page)).toEqual({ main: 0, nav: 0 });
  });
});

// Tiered cards (grade, tier chips, flags), the fallback banner and the expanded detail
// table (SPEC_ui_tiered_4.0.0 §3): no sideways scroll on common phone widths.
for (const width of [320, 360, 390]) {
  for (const m of WARM_MIRNAS) {
    test(`/results ${m.name} at ${width} px: tier cards and banners fit`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await page.goto('/design');
      await page.getByPlaceholder(PLACEHOLDER).fill(m.sequence);
      await page.evaluate(() => {
        const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === 'Search');
        if (b) b.click();
      });
      const designBtn = page.getByRole('button', { name: 'Design Primers →' });
      await expect(designBtn).toBeEnabled({ timeout: 8000 });
      await designBtn.click();
      await expect(page).toHaveURL('/results', { timeout: DESIGN_TIMEOUT });
      await expect(page.getByTestId('tier-summary').first()).toBeVisible();
      await page.getByText('Criteria detail').first().click();
      expect(await horizontalOverflow(page)).toEqual({ main: 0, nav: 0 });
    });
  }
}

// The 3′ isoform table inside the isomiR "Why" (isomiRdb, pooled) fits at phone widths.
for (const width of [360, 390]) {
  for (const name of ['hsa-miR-21-5p', 'hsa-miR-222-3p']) {
    test(`/results ${name} at ${width} px: 3′ isoform table fits`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await page.goto('/design');
      await page.getByPlaceholder(PLACEHOLDER).fill(WARM_MIRNAS.find((m) => m.name === name).sequence);
      await page.evaluate(() => {
        const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === 'Search');
        if (b) b.click();
      });
      const designBtn = page.getByRole('button', { name: 'Design Primers →' });
      await expect(designBtn).toBeEnabled({ timeout: 8000 });
      await designBtn.click();
      await expect(page).toHaveURL('/results', { timeout: DESIGN_TIMEOUT });
      await page.getByTestId('isomir-note').getByText('Why').click();
      await expect(page.getByTestId('isomir-table')).toBeVisible();
      expect(await horizontalOverflow(page)).toEqual({ main: 0, nav: 0 });
    });
  }
}

test('unknown address shows a not-found page with a way back', async ({ page }) => {
  await page.goto('/no-such-page');
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  await page.getByRole('link', { name: /Go to Designer/ }).click();
  await expect(page).toHaveURL('/design');
});
