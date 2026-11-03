import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  // The backend runs designs one at a time (process-wide primer3 thal lock,
  // AUDIT REV-07), ~2 s each. The default (half the cores: 8 here) queues >15 s
  // of designs and trips the 15 s design timeout; 4 keeps the worst wait ~8 s.
  workers: 4,
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
