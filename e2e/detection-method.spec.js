import { test, expect } from '@playwright/test';

// DetectionMethodGroup on the Advanced designer. The family-discrimination and
// pre-miRNA toggles were removed (audit SCI-09/ENG-02): the first always runs,
// the second was never computed.
test.describe('DetectionMethodGroup', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/design/advanced');
    await page.getByText('Detection Method', { exact: true }).click();
    await page.getByText('Advanced options').click();
  });

  test('dead toggles are gone', async ({ page }) => {
    await expect(page.getByLabel('Penalize off-target in same miRNA family')).toHaveCount(0);
    await expect(page.getByLabel('Check cross-reactivity with pre-miRNA')).toHaveCount(0);
  });

  test('pre-miRNA limitation is stated', async ({ page }) => {
    await expect(page.getByText(/pre-miRNA discrimination is\s+not computed/)).toBeVisible();
  });

  test('re-folding protocol checked by default', async ({ page }) => {
    const cb = page.getByLabel('Generate re-folding protocol in output');
    await expect(cb).toBeChecked();
  });
});
