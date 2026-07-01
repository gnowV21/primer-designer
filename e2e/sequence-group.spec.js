import { test, expect } from '@playwright/test';
import { PLACEHOLDER } from './helpers.js';

test.describe('SequenceGroup', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/search');
  });

  test('lowercase sequence input is accepted (auto-uppercase)', async ({ page }) => {
    const searchInput = page.getByPlaceholder(PLACEHOLDER);
    await searchInput.fill('uagcuuaucagacugauguuga');
    await page.getByRole('button', { name: 'Search' }).click();
    // Sequence accepted and result card shows length
    await expect(page.getByText('22 nt')).toBeVisible();
  });

  test("T character shows error", async ({ page }) => {
    const searchInput = page.getByPlaceholder(PLACEHOLDER);
    await searchInput.fill('TAGCUUAUCAGACUGAUGUUGA');
    await page.getByRole('button', { name: 'Search' }).click();
    await expect(page.getByText("Character 'T' detected")).toBeVisible();
  });

  test('valid sequence shows info bar', async ({ page }) => {
    const searchInput = page.getByPlaceholder(PLACEHOLDER);
    await searchInput.fill('UAGCUUAUCAGACUGAUGUUGA');
    await page.getByRole('button', { name: 'Search' }).click();
    await expect(page.getByText('22 nt')).toBeVisible();
  });

  test('sequence too short shows error', async ({ page }) => {
    const searchInput = page.getByPlaceholder(PLACEHOLDER);
    // 11 nt — long enough for detectInputType to classify as sequence (≥10),
    // but below the 15 nt minimum for validateSequence
    await searchInput.fill('UAGCUAAGCUU');
    await page.getByRole('button', { name: 'Search' }).click();
    await expect(page.getByText('too short')).toBeVisible();
  });
});
