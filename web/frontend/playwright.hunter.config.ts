import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';
export default defineConfig({
  testDir: './tests', testMatch: 'heartbeat-hunter.spec.ts', workers: 1, retries: 0,
  timeout: 90000, expect: { timeout: 15000 }, reporter: [['list']], outputDir: './test-results-hunter',
  use: { baseURL: 'http://127.0.0.1:8136', channel: 'chrome', ...devices['Desktop Chrome'], trace: 'retain-on-failure' },
  webServer: { command: '.venv\\Scripts\\python.exe -m uvicorn web.backend.production:app --host 127.0.0.1 --port 8136 --log-level warning',
    cwd: path.resolve(__dirname, '../..'), url: 'http://127.0.0.1:8136/api/health', timeout: 180000, reuseExistingServer: false,
    env: { ECG_LOG_LEVEL: 'WARNING', ECG_HUNTER_DATABASE: path.resolve(__dirname,'../runtime/hunter_e2e.sqlite3') } },
});
