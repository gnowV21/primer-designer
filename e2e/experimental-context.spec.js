import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:5173';

test.describe('ExperimentalContextGroup', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/design/advanced`);
    await page.getByText('Experimental Context').click();
  });

  test('Serum sample shows preset banner', async ({ page }) => {
    await page.getByLabel('Sample type').selectOption({ label: 'Serum' });
    await expect(page.getByText('Special sample type detected')).toBeVisible();
  });

  test('Apply preset updates amplicon range', async ({ page }) => {
    await page.getByLabel('Sample type').selectOption({ label: 'Serum' });
    await page.getByRole('button', { name: 'Apply' }).click();
    await expect(page.getByText('Special sample type detected')).not.toBeVisible();
  });

  test('Dismiss hides preset banner', async ({ page }) => {
    await page.getByLabel('Sample type').selectOption({ label: 'Serum' });
    await page.getByRole('button', { name: 'Dismiss' }).click();
    await expect(page.getByText('Special sample type detected')).not.toBeVisible();
  });

  test('qPCR system note updates on selection change', async ({ page }) => {
    await page.getByLabel('qPCR system').selectOption('abi');
    await expect(page.getByText('ROX passive reference')).toBeVisible();
  });
});
