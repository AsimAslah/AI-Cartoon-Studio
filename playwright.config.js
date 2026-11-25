const fs = require('fs');
const path = require('path');
const { defineConfig, devices } = require('@playwright/test');

const runtimeRoot = process.env.AI_CARTOON_E2E_ROOT;
if (!runtimeRoot) throw new Error('Run Playwright through npm run test:e2e so an isolated temporary root is configured.');
const localPython = path.join(__dirname, '.venv', 'Scripts', 'python.exe');
const python = process.env.AI_CARTOON_E2E_PYTHON || (fs.existsSync(localPython) ? localPython : 'python');

module.exports = defineConfig({
  testDir: './tests/e2e',
  outputDir: 'test-results/playwright',
  globalSetup: require.resolve('./tests/e2e/global-setup'),
  globalTeardown: require.resolve('./tests/e2e/global-teardown'),
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI
    ? [['line'], ['html', { outputFolder: 'playwright-report', open: 'never' }]]
    : [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:8765',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
  },
  webServer: {
    command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8765`,
    url: 'http://127.0.0.1:8765/api/capabilities',
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      ...process.env,
      AI_CARTOON_RUNTIME_ROOT: runtimeRoot,
      AI_CARTOON_ENABLE_REMOTE_VIDEO: '0',
      AI_CARTOON_HF_TOKEN: '',
    },
  },
  projects: [
    { name: 'chromium-desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } },
    { name: 'firefox-desktop', use: { ...devices['Desktop Firefox'], viewport: { width: 1440, height: 1000 } } },
    { name: 'webkit-desktop', use: { ...devices['Desktop Safari'], viewport: { width: 1440, height: 1000 } } },
    { name: 'chromium-mobile', use: { ...devices['Pixel 7'] } },
  ],
});
