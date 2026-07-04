// e2e/benchmark.spec.js — Phase 7 PART F
// Tests that /benchmark page shows limitation banner and handles both
// PENDING and available metric states.

import { test, expect } from '@playwright/test';

const PENDING_RESPONSE = {
  _metadata: {
    run_date: null,
    panel_size: 0,
    tool_version: 'algo-v3.0.0',
    comparison_note:
      'Design-characteristic comparison only. Stem-loop RT-qPCR primer sets differ chemically from linear RT primers used by mirPrimer/miPrimer. Tm, length, and structural scores are compared; absolute efficiency values are NOT directly comparable.',
    verified: false,
    status: 'PENDING',
  },
  metrics: null,
  per_assay: [],
};

const AVAILABLE_RESPONSE = {
  _metadata: {
    run_date: '2026-07-01',
    panel_size: 10,
    tool_version: 'algo-v3.0.0',
    comparison_note: 'Design-characteristic comparison only.',
    verified: false,
    status: 'DONE',
  },
  metrics: {
    forward_tm: { this_tool: 60.5, mirprimer: 58.2, miprimer: null },
    gc_percent: { this_tool: 45.5, mirprimer: 44.1, miprimer: 46.0 },
  },
  per_assay: [],
};

test.describe('/benchmark page', () => {
  test('limitation banner is always visible', async ({ page }) => {
    await page.route('**/api/benchmark', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(PENDING_RESPONSE),
      })
    );
    await page.goto('/benchmark');
    await page.waitForLoadState('networkidle');

    const banner = page.locator('[data-testid="benchmark-limitation-banner"]');
    await expect(banner).toBeVisible();
    // Banner must always be visible — not collapsible
    const closeBtn = banner.locator('button[aria-label="close"], button[aria-label="dismiss"]');
    expect(await closeBtn.count()).toBe(0);
  });

  test('limitation banner cannot be dismissed', async ({ page }) => {
    await page.route('**/api/benchmark', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(PENDING_RESPONSE),
      })
    );
    await page.goto('/benchmark');
    await page.waitForLoadState('networkidle');

    const banner = page.locator('[data-testid="benchmark-limitation-banner"]');
    await expect(banner).toBeVisible();
    // Verify it persists after any interaction
    await page.keyboard.press('Escape');
    await expect(banner).toBeVisible();
  });

  test('shows PENDING state when metrics is null', async ({ page }) => {
    await page.route('**/api/benchmark', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(PENDING_RESPONSE),
      })
    );
    await page.goto('/benchmark');
    await page.waitForLoadState('networkidle');

    // Page should indicate PENDING — look for text containing PENDING
    const body = await page.locator('body').textContent();
    expect(body).toMatch(/PENDING|not yet available|run benchmark/i);
  });

  test('shows metrics when available', async ({ page }) => {
    await page.route('**/api/benchmark', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(AVAILABLE_RESPONSE),
      })
    );
    await page.goto('/benchmark');
    await page.waitForLoadState('networkidle');

    // Check that at least one metric label is rendered
    const body = await page.locator('body').textContent();
    // 'forward_tm' or 'Forward Tm' or 'Tm' should appear
    expect(body).toMatch(/[Tt]m|gc_percent|GC/);
  });

  test('comparison_note is displayed on page', async ({ page }) => {
    await page.route('**/api/benchmark', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(PENDING_RESPONSE),
      })
    );
    await page.goto('/benchmark');
    await page.waitForLoadState('networkidle');

    const banner = page.locator('[data-testid="benchmark-limitation-banner"]');
    const bannerText = await banner.textContent();
    // Banner should contain chemistry difference disclaimer
    expect(bannerText).toMatch(/[Ss]tem.loop|[Cc]hemist|[Cc]ompar/);
  });
});
