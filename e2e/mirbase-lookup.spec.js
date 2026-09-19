import { test, expect } from '@playwright/test';
import { PLACEHOLDER } from './helpers.js';

test.describe('miRBase lookup', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/design/advanced');
  });

  test('hsa-miR-21-5p search fills sequence', async ({ page }) => {
    const idInput = page.getByPlaceholder(PLACEHOLDER);
    await idInput.fill('hsa-miR-21-5p');
    await page.getByRole('button', { name: 'Search' }).click();
    await expect(page.getByPlaceholder(PLACEHOLDER)).toHaveValue('UAGCUUAUCAGACUGAUGUUGA', { timeout: 8000 });
  });

  test('MIMAT0000076 resolves same miRNA', async ({ page }) => {
    const idInput = page.getByPlaceholder(PLACEHOLDER);
    await idInput.fill('MIMAT0000076');
    await page.getByRole('button', { name: 'Search' }).click();
    await expect(page.getByPlaceholder(PLACEHOLDER)).toHaveValue('UAGCUUAUCAGACUGAUGUUGA', { timeout: 8000 });
  });

  test('invalid ID shows not-found error', async ({ page }) => {
    // Mock the backend so the not-found state renders immediately without external API latency
    await page.route('**/api/mirbase/**', (route) =>
      route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: 'Not found' }) })
    );
    const idInput = page.getByPlaceholder(PLACEHOLDER);
    await idInput.fill('invalid-id-xyz');
    await page.getByRole('button', { name: 'Search' }).click();
    await expect(page.getByText(/not found\. Please check the ID/)).toBeVisible({ timeout: 5000 });
  });
});
