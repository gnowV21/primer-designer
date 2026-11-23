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

/** Unfold the scientific-details block on /results (ThermoTable, advisors). */
export async function showScientificDetails(page) {
  await page.getByRole('button', { name: /Show scientific details/ }).click();
}

/** Wait for a real /api/design (algorithm 4.0.0 BLASTs during the design). */
export const DESIGN_TIMEOUT = 30000;

/**
 * miRNAs the specs design through the UI with the frontend defaults; global-setup.js
 * sends the same requests first so the BLAST cache is warm (SPEC_ui_tiered_4.0.0 §3).
 */
export const WARM_MIRNAS = [
  { name: 'hsa-miR-21-5p', sequence: 'UAGCUUAUCAGACUGAUGUUGA' },
  { name: 'hsa-let-7a-5p', sequence: 'UGAGGUAGUAGGUUGUAUAGUU' },
  // #1 below the 39 °C binding-Tm floor and outside a V4 rule (gc_clamp_fail), grade B
  { name: 'hsa-miR-590-3p', sequence: 'UAAUUUUAUGUAUAAGCUAGU' },
  // most common 3′ isoform +3 nt (36 % pooled) vs 9 % with the miRBase end: dominant-isoform line
  { name: 'hsa-miR-222-3p', sequence: 'AGCUACAUCUGGCUACUGGGU' },
];

/**
 * Make sure a parameter group ("Required", "Flexible", "Assay setup", "Detection method",
 * "Experimental context") is open. On /design every group starts open once Parameters is
 * open (UI review 2026-11-23); in the re-run sidebar they start closed.
 */
export async function openGroup(page, title) {
  const btn = page.locator('button[aria-expanded]').filter({ hasText: new RegExp(`^\\W*${title}`) }).first();
  if ((await btn.getAttribute('aria-expanded')) !== 'true') await btn.click();
}

/** The designer's submit button (no decorative arrow since 2026-11-23). */
export const DESIGN_BUTTON = { name: /^Design primers$/ };
