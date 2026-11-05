import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';

const projectRoot = path.resolve(__dirname, '../..');

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  expect: { timeout: 15000 },
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8131',
    channel: 'chrome',
    trace: 'retain-on-failure',
    actionTimeout: 15000,
    navigationTimeout: 30000,
    ...devices['Desktop Chrome'],
  },
  webServer: [
    {
      command: '.venv\\Scripts\\python.exe -m uvicorn web.backend.app:app --host 127.0.0.1 --port 8130 --log-level warning',
      cwd: projectRoot,
      url: 'http://127.0.0.1:8130/api/health',
      reuseExistingServer: false,
      env: { ECG_LOG_LEVEL: 'WARNING' },
      timeout: 120_000,
    },
    {
      command: 'node node_modules/@umijs/max/bin/max.js dev --port 8131',
      cwd: path.resolve(__dirname),
      url: 'http://127.0.0.1:8131/ai-detection',
      reuseExistingServer: false,
      env: { PORT: '8131', ECG_API_PROXY: 'http://127.0.0.1:8130' },
      timeout: 180_000,
    },
  ],
});
