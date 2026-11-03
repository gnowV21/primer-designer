// Shared test constants for E2E specs.
// Import from individual spec files instead of duplicating.

export const PLACEHOLDER = 'hsa-miR-21-5p · MIMAT0000076 · UAGCUUAUCAGACUGAUGUUGA';

/**
 * Open the folded "Parameters" panel on /design (every parameter group lives
 * inside it). No-op when it is already open.
 */
export async function openParameters(page) {
  const btn = page.getByRole('button', { name: /Parameters/ }).first();
  if ((await btn.getAttribute('aria-expanded')) !== 'true') await btn.click();
}

/** Unfold the scientific-details block on /results (ThermoTable, advisors, multiplex). */
export async function showScientificDetails(page) {
  await page.getByRole('button', { name: /Show scientific details/ }).click();
}
