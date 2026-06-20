import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:5173';

test.describe('DetectionMethodGroup', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/search`);
    // DetectionMethodGroup is defaultOpen — no need to expand
  });

  test('TaqMan selected by default, info box visible', async ({ page }) => {
    const radio = page.locator('input[name="signalMethod"][value="taqman"]');
    await expect(radio).toBeChecked();
    await expect(page.getByText('TaqMan mode')).toBeVisible();
  });

  test('switching to SYBR Green changes info box', async ({ page }) => {
    await page.locator('input[name="signalMethod"][value="sybr"]').check();
    await expect(page.getByText('SYBR Green mode')).toBeVisible();
    await expect(page.getByText('TaqMan mode')).not.toBeVisible();
  });

  test('Relative mode shows reference gene field', async ({ page }) => {
    await page.locator('input[name="quantMode"][value="relative"]').check();
    await expect(page.getByText('Reference gene')).toBeVisible();
  });

  test('Absolute mode hides reference gene field', async ({ page }) => {
    await page.locator('input[name="quantMode"][value="absolute"]').check();
    await expect(page.getByText('Reference gene')).not.toBeVisible();
  });
});
