import { test, expect } from '@playwright/test';

test.describe('Form submit button', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/search');
  });

  test('submit button disabled with no sequence', async ({ page }) => {
    const btn = page.getByRole('button', { name: 'Design Primers →' });
    await expect(btn).toBeDisabled();
  });

  test('submit button shows Fix errors state on validation error', async ({ page }) => {
    // Open Primer Design Constraints to access thermodynamic inputs
    await page.getByText('Primer Design Constraints').click();
    const saltInput = page.locator('#thermo-na');
    await saltInput.fill('');
    await saltInput.blur();
    await expect(page.getByText('Fix errors to continue')).toBeVisible();
  });

  test('NumInput clear shows empty field not zero', async ({ page }) => {
    await page.getByText('Primer Design Constraints').click();
    const saltInput = page.locator('#thermo-na');
    await saltInput.click();
    await saltInput.selectText();
    await saltInput.press('Delete');
    await expect(saltInput).toHaveValue('');
  });

  test('NumInput focus selects all text', async ({ page }) => {
    await page.getByText('Primer Design Constraints').click();
    const saltInput = page.locator('#thermo-na');
    await saltInput.click();
    // After click, value should be selected (verify by typing immediately)
    await saltInput.type('99');
    // If all text was selected, typing replaces it; field should not show "5099"
    const val = await saltInput.inputValue();
    expect(val).toBe('99');
  });

  test('page title is HG Lab | Primer Designer', async ({ page }) => {
    await expect(page).toHaveTitle('HG Lab | Primer Designer');
  });
});
