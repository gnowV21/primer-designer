import { test, expect } from '@playwright/test';

test.describe('RangeSlider', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/search');
    // Open Primer Design Constraints to access Tm slider
    await page.getByText('Primer Design Constraints').click();
  });

  test('Tm badge chips show default values 58°C and 62°C', async ({ page }) => {
    await expect(page.getByText('58°C').first()).toBeVisible();
    await expect(page.getByText('62°C').first()).toBeVisible();
  });

  test('drag callout bubble appears on pointer down', async ({ page }) => {
    // The bubble is shown while dragging; verify it renders during interaction
    const sliders = page.locator('input[type="range"]');
    await sliders.first().dispatchEvent('pointerdown');
    await expect(page.locator('.bg-teal-700').first()).toBeVisible();
    await sliders.first().dispatchEvent('pointerup');
  });
});
