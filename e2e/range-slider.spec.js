import { test, expect } from '@playwright/test';
import { openParameters, openGroup } from './helpers.js';

test.describe('RangeSlider', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/design');
    // Open Required to access the Tm window slider
    await openParameters(page);
    await openGroup(page, 'Required');
  });

  test('Tm window label shows the default 58–62 °C under the thumbs', async ({ page }) => {
    // Thumbs this close share one centred label; value and unit never break apart.
    await expect(page.getByText(/^58–62\s°C$/).first()).toBeVisible();
  });

  test('drag callout bubble appears on pointer down', async ({ page }) => {
    // The bubble is shown while dragging; verify it renders during interaction
    const sliders = page.locator('input[type="range"]');
    await sliders.first().dispatchEvent('pointerdown');
    await expect(page.locator('.bg-teal-700').first()).toBeVisible();
    await sliders.first().dispatchEvent('pointerup');
  });
});
