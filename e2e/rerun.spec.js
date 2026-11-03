// E2E — tune parameters on /results and re-run (RerunBar).
// Covers: nothing runs until Re-run is pressed, the change list, the run
// switcher, the hand-back to the designer, and a failed re-run keeping the
// current result on screen.

import { test, expect } from '@playwright/test';
import { PLACEHOLDER } from './helpers.js';

const SEQUENCE = 'UAGCUUAUCAGACUGAUGUUGA';               // hsa-miR-21-5p
const BODY = 'GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGAC';
const RT_6NT = `${BODY}TCAACA`;                         // revcomp of the last 6 nt
const RT_7NT = `${BODY}TCAACAT`;                        // revcomp of the last 7 nt

async function designDefault(page) {
  await page.goto('/design');
  await page.getByPlaceholder(PLACEHOLDER).fill(SEQUENCE);
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === 'Search');
    if (b) b.click();
  });
  const designBtn = page.getByRole('button', { name: 'Design Primers →' });
  await expect(designBtn).toBeEnabled({ timeout: 8000 });
  await designBtn.click();
  await expect(page).toHaveURL('/results', { timeout: 15000 });
}

const rtPrimer = (page, seq) => page.getByText(seq, { exact: true }).first();

test('Re-run is disabled until a parameter changes', async ({ page }) => {
  await designDefault(page);
  await expect(page.getByText('6 nt overhang')).toBeVisible();
  await page.getByRole('button', { name: /Adjust & re-run/ }).click();
  await expect(page.getByRole('button', { name: /Re-run/ })).toBeDisabled();
  await expect(page.getByText('Change any parameter, then re-run.')).toBeVisible();
});

test('re-run with a 7-nt overhang adds a run; runs can be switched', async ({ page }) => {
  await designDefault(page);
  await expect(rtPrimer(page, RT_6NT)).toBeVisible();

  await page.getByRole('button', { name: /Adjust & re-run/ }).click();
  await page.getByRole('button', { name: '7 nt', exact: true }).click();
  await expect(page.getByText(/Overhang\s+6 nt →\s*7 nt/)).toBeVisible();
  await page.getByRole('button', { name: /Re-run/ }).click();

  const runs = page.getByRole('group', { name: 'Design runs' });
  await expect(runs).toBeVisible({ timeout: 15000 });
  await expect(runs.getByRole('button')).toHaveCount(2);
  await expect(rtPrimer(page, RT_7NT)).toBeVisible();

  await runs.getByRole('button', { name: /#1/ }).click();
  await expect(rtPrimer(page, RT_6NT)).toBeVisible();
  await expect(page.getByText('6 nt overhang')).toBeVisible();

  // The designer opens with the parameters of the run being viewed.
  await runs.getByRole('button', { name: /#2/ }).click();
  await page.getByRole('button', { name: /Back to designer/ }).click();
  await expect(page).toHaveURL('/design');
  await expect(page.getByText('7 nt overhang')).toBeVisible();
  await expect(page.getByText('1 changed')).toBeVisible();
});

test('a failed re-run keeps the current result and explains why', async ({ page }) => {
  await designDefault(page);
  await page.route('**/api/design', (route) =>
    route.fulfill({
      status: 422,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'No valid candidates found.', suggestion: 'Widen the Tm window.' }),
    })
  );
  await page.getByRole('button', { name: /Adjust & re-run/ }).click();
  await page.getByRole('button', { name: '5 nt', exact: true }).click();
  await page.getByRole('button', { name: /Re-run/ }).click();

  await expect(page.getByText('This run did not produce primers — the result below is unchanged.')).toBeVisible();
  await expect(rtPrimer(page, RT_6NT)).toBeVisible();
  await expect(page.getByRole('group', { name: 'Design runs' })).toHaveCount(0);
});
