// E2E — phone layout guard (320 px, the narrowest common width).
// Every page must fit without sideways scrolling, and all four nav tabs must be
// visible without scrolling the tab strip.

import { test, expect } from '@playwright/test';
import { PLACEHOLDER } from './helpers.js';

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
    await expect(page).toHaveURL('/results', { timeout: 15000 });
    expect(await horizontalOverflow(page)).toEqual({ main: 0, nav: 0 });
  });
});

test('unknown address shows a not-found page with a way back', async ({ page }) => {
  await page.goto('/no-such-page');
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  await page.getByRole('link', { name: /Go to Designer/ }).click();
  await expect(page).toHaveURL('/design');
});
