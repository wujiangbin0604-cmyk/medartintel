import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';

const root = path.resolve(__dirname, '../..');
const evidence = path.join(root, 'research_extensions/validation/revalidation_20261119_browser');
process.env.ECG_REVALIDATION_SHOTS = path.join(evidence, 'screenshots');
process.env.ECG_HUNTER_DATABASE = path.join(evidence, 'hunter.sqlite3');

export default defineConfig({
  testDir: './tests', testMatch: ['rhythm-lab.spec.ts', 'rhythm-hunter-regression.spec.ts'],
  workers: 1, retries: 0, timeout: 90000, expect: { timeout: 20000 },
  reporter: [['list'], ['json', { outputFile: path.join(evidence, 'results.json') }]],
  outputDir: path.join(evidence, 'artifacts'),
  use: { baseURL: 'http://127.0.0.1:8142', channel: 'chrome', ...devices['Desktop Chrome'], trace: 'retain-on-failure' },
  webServer: {
    command: '.venv\\Scripts\\python.exe -B -m uvicorn web.backend.production:app --host 127.0.0.1 --port 8142 --log-level warning',
    cwd: root, url: 'http://127.0.0.1:8142/api/health', timeout: 180000, reuseExistingServer: false,
    env: { ECG_LOG_LEVEL: 'WARNING', ECG_HUNTER_DATABASE: process.env.ECG_HUNTER_DATABASE,
      OMP_NUM_THREADS: '2', MKL_NUM_THREADS: '2' },
  },
});
