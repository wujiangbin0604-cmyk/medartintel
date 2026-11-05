import { defineConfig } from '@playwright/test';
import hunter from './playwright.hunter.config';
export default defineConfig({ ...hunter, testMatch: ['welcome-onboarding.spec.ts', 'heartbeat-hunter.spec.ts'], outputDir: './test-results-onboarding' });
