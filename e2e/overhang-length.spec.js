import { test, expect } from '@playwright/test';
import { PLACEHOLDER, openParameters } from './helpers.js';

// miR-21-5p 3' end ...GAUGUUGA — 2 G/C in the last 7 nt (28.6 %) but 33.3 % in the last 6.
// The GC-poor binding-region warning must therefore appear ONLY at 7 nt, and name "7 nt".
test("binding-region warning follows the 3' overhang length, not a fixed 6", async ({ page }) => {
  await page.goto('/design');
  await page.getByPlaceholder(PLACEHOLDER).fill('UAGCUUAUCAGACUGAUGUUGA');
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === 'Search');
    if (b) b.click();
  });

  const warn = page.getByText(/GC-poor binding region/);
  await expect(warn).toHaveCount(0);                       // 6 nt default → silent

  await openParameters(page);
  await page.getByText('Primer Design Constraints').click();
  await page.getByRole('button', { name: '7 nt', exact: true }).click();
  await expect(warn).toBeVisible();
  await expect(page.getByText(/most 7 nt contain only 2 G\/C/)).toBeVisible();

  await page.getByRole('button', { name: '5 nt', exact: true }).click();
  await expect(warn).toHaveCount(0);                       // 2/5 = 40 % → silent

  await page.getByRole('button', { name: '6 nt', exact: true }).click();
  await expect(warn).toHaveCount(0);
});
