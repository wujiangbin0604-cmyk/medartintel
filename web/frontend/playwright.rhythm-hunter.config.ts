import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';
import os from 'node:os';
export default defineConfig({
  testDir: './tests', testMatch: 'rhythm-hunter-regression.spec.ts', workers: 1, retries: 0,
  timeout: 90000, expect: { timeout: 20000 }, reporter: [['list'], ['json', { outputFile: '../../research_extensions/validation/hunter_browser_results.json' }]],
  outputDir: process.env.ECG_E2E_OUTPUT || path.join(os.tmpdir(), 'ecg-hunter-tests'),
  use: { baseURL: 'http://127.0.0.1:8142', channel: 'chrome', ...devices['Desktop Chrome'], trace: 'off' },
  webServer: { command: '.venv\\Scripts\\python.exe -B -m uvicorn web.backend.production:app --host 127.0.0.1 --port 8142 --log-level warning',
    cwd: path.resolve(__dirname, '../..'), url: 'http://127.0.0.1:8142/api/health', timeout: 180000, reuseExistingServer: false,
    env: { ECG_LOG_LEVEL: 'WARNING', ECG_HUNTER_DATABASE: path.resolve(__dirname, '../../research_extensions/validation/hunter.sqlite3'), OMP_NUM_THREADS: '2', MKL_NUM_THREADS: '2' } },
});
