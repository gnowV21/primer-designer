import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  // The backend runs designs one at a time (process-wide primer3 thal lock,
  // AUDIT REV-07), ~2 s each. The default (half the cores: 8 here) queues >15 s
  // of designs and trips the 15 s design timeout; 4 keeps the worst wait ~8 s.
  workers: 4,
  // Algorithm 4.0.0 runs BLAST during the design (~10-13 s uncached, ~3 s cached):
  // the design wait is 30 s (SPEC_ui_tiered_4.0.0 §3), so a test needs more than
  // Playwright's 30 s default. global-setup warms the BLAST cache first.
  timeout: 90_000,
  globalSetup: './e2e/global-setup.js',
  retries: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'npm run dev --prefix frontend',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 60000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
