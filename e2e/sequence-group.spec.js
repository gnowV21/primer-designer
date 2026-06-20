import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:5173';

test.describe('SequenceGroup', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/search`);
  });

  test('sequence textarea auto-uppercase', async ({ page }) => {
    const ta = page.locator('textarea').first();
    await ta.fill('uagcuuaucagacugauguuga');
    await expect(ta).toHaveValue('UAGCUUAUCAGACUGAUGUUGA');
  });

  test("T character shows English error", async ({ page }) => {
    const ta = page.locator('textarea').first();
    await ta.fill('TAGCUUAUCAGACUGAUGUUGA');
    await ta.blur();
    await expect(page.getByText("Character 'T' detected")).toBeVisible();
  });

  test('valid sequence shows info bar', async ({ page }) => {
    const ta = page.locator('textarea').first();
    await ta.fill('UAGCUUAUCAGACUGAUGUUGA');
    await ta.blur();
    await expect(page.getByText('22 nt')).toBeVisible();
  });

  test('sequence too short shows error', async ({ page }) => {
    const ta = page.locator('textarea').first();
    await ta.fill('UAGCU');
    await ta.blur();
    await expect(page.getByText('too short')).toBeVisible();
  });
});
