// Decisions of 2026-11-23 (docs/REVIEW_ui_polish_2026-11.md, "Decisions"):
//  - the 7-nt overhang hint is matched on the seed of the mature sequence, not on a
//    substring of the family label;
//  - free Mg²⁺ warns only below 0.5 mM (the standard Taq mix, 1.5 mM Mg²⁺ + 0.8 mM dNTP,
//    leaves 0.7 mM and must not warn).
import { test, expect } from '@playwright/test';
import { getFamilyHint, seedOf } from '../frontend/src/utils/familyHint.js';
import { openParameters, openGroup } from './helpers.js';

test.describe('family hint (pure function)', () => {
  const cases = [
    ['hsa-let-7a-5p', 'UGAGGUAGUAGGUUGUAUAGUU', 'let-7'],
    ['hsa-miR-17-5p', 'CAAAGUGCUUACAGUGCAGGUAG', 'miR-17'],
    ['hsa-miR-20a-5p', 'UAAAGUGCUUAUAGUGCAGGUAG', 'miR-17'],
    ['hsa-miR-29a-3p', 'UAGCACCAUCUGAAAUCGGUUA', 'miR-29'],
    ['hsa-miR-30a-5p', 'UGUAAACAUCCUCGACUGGAAG', 'miR-30'],
  ];
  for (const [name, seq, fam] of cases) {
    test(`${name} gets the ${fam} hint`, () => {
      expect(getFamilyHint(seq)?.family).toBe(fam);
      expect(getFamilyHint(seq).suggestNt).toBe(7);
    });
  }
  // Their old family labels contained "mir-29" / "mir-30" and got the hint by substring.
  const none = [
    ['hsa-miR-371a-5p', 'ACUCAAACUGUGGGGGCACU'],
    ['hsa-miR-302a-3p', 'UAAGUGCUUCCAUGUUUUGGUGA'],
    ['hsa-miR-296-5p', 'AGGGCCCCCCCUCAAUCCUGU'],
    ['hsa-miR-21-5p', 'UAGCUUAUCAGACUGAUGUUGA'],
  ];
  for (const [name, seq] of none) {
    test(`${name} gets no hint`, () => {
      expect(getFamilyHint(seq)).toBeNull();
    });
  }
  test('DNA letters and short input', () => {
    expect(seedOf('TGAGGTAGTAGGTTGTATAGTT')).toBe('GAGGUAG');
    expect(getFamilyHint('UGAG')).toBeNull();
    expect(getFamilyHint('')).toBeNull();
  });
});

test('free Mg²⁺ at the defaults passes; below 0.5 mM it warns', async ({ page }) => {
  await page.goto('/design');
  await openParameters(page);
  await openGroup(page, 'Flexible');
  const box = page.getByTestId('free-mg');
  await expect(box).toContainText(/0\.70\s?mM/);
  await expect(box).toContainText(/Pass \(≥ 0\.5\smM\)/);
  await expect(box).not.toContainText('Warning');
  await expect(box).toContainText('project threshold');
  await page.locator('#thermo-mg').fill('1');
  await page.locator('#thermo-mg').blur();
  await expect(box).toContainText(/Warning: below 0\.5\smM/);
});
