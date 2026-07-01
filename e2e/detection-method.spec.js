import { test, expect } from '@playwright/test';

test.describe('DetectionMethodGroup', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/search');
    // Open Primer Design Constraints then expand Advanced specificity options
    await page.getByText('Primer Design Constraints').click();
    await page.getByText('Advanced specificity options').click();
  });

  test('family discrimination checked by default', async ({ page }) => {
    const cb = page.getByLabel('Penalize off-target in same miRNA family');
    await expect(cb).toBeChecked();
  });

  test('precursor check unchecked by default', async ({ page }) => {
    const cb = page.getByLabel('Check cross-reactivity with pre-miRNA');
    await expect(cb).not.toBeChecked();
  });

  test('re-folding protocol checked by default', async ({ page }) => {
    const cb = page.getByLabel('Generate re-folding protocol in output');
    await expect(cb).toBeChecked();
  });

  test('toggling precursor check works', async ({ page }) => {
    const cb = page.getByLabel('Check cross-reactivity with pre-miRNA');
    await cb.check();
    await expect(cb).toBeChecked();
    await cb.uncheck();
    await expect(cb).not.toBeChecked();
  });
});
