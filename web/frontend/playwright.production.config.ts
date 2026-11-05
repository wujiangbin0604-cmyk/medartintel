import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';
export default defineConfig({
  testDir:'./tests',testMatch:'production.spec.ts',reporter:'list',workers:1,
  outputDir:'./test-results-production',
  use:{baseURL:'http://127.0.0.1:8132',channel:'chrome',...devices['Desktop Chrome']},
  webServer:{command:'.venv\\Scripts\\python.exe -m uvicorn web.backend.production:app --host 127.0.0.1 --port 8132 --log-level warning',cwd:path.resolve(__dirname,'../..'),url:'http://127.0.0.1:8132/api/health',reuseExistingServer:false,timeout:120000,env:{ECG_LOG_LEVEL:'WARNING'}},
});
