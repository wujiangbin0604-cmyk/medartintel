import {defineConfig,devices} from '@playwright/test';
export default defineConfig({testDir:'./tests',testMatch:'fidelity.spec.ts',workers:1,reporter:'list',outputDir:'test-results-fidelity',expect:{timeout:15000},use:{...devices['Desktop Chrome'],channel:'chrome',baseURL:process.env.FIDELITY_URL||'http://127.0.0.1:8002'}});
