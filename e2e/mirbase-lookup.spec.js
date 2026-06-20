import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:5173';

test.describe('miRBase lookup', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/search`);
  });

  test('hsa-miR-21-5p Tab fills sequence', async ({ page }) => {
    const idInput = page.getByPlaceholder('e.g. hsa-miR-21-5p or MIMAT0000076');
    await idInput.fill('hsa-miR-21-5p');
    await idInput.press('Tab');
    const ta = page.locator('textarea').first();
    await expect(ta).toHaveValue('UAGCUUAUCAGACUGAUGUUGA', { timeout: 8000 });
  });

  test('MIMAT0000076 resolves same sequence', async ({ page }) => {
    const idInput = page.getByPlaceholder('e.g. hsa-miR-21-5p or MIMAT0000076');
    await idInput.fill('MIMAT0000076');
    await page.getByRole('button', { name: 'Search' }).click();
    const ta = page.locator('textarea').first();
    await expect(ta).toHaveValue('UAGCUUAUCAGACUGAUGUUGA', { timeout: 8000 });
  });

  test('invalid ID shows not-found error', async ({ page }) => {
    const idInput = page.getByPlaceholder('e.g. hsa-miR-21-5p or MIMAT0000076');
    await idInput.fill('invalid-id-xyz');
    await page.getByRole('button', { name: 'Search' }).click();
    await expect(page.locator('text=✗').first()).toBeVisible({ timeout: 8000 });
  });
});
