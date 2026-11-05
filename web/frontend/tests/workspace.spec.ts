import { expect, test } from '@playwright/test';

test('real ECG selection, three-model inference, task switching and historical replay', async ({ page }) => {
  const pageErrors: string[] = [];
  const apiFailures: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('response', (response) => {
    if (response.url().includes('/api/') && response.status() >= 400) apiFailures.push(`${response.status()} ${response.url()}`);
  });
  await page.goto('/ai-detection');

  await expect(page.getByRole('heading', { name: 'ECG 心拍分析' })).toBeVisible({ timeout: 90_000 });
  await expect(page.locator('.signal-context')).toContainText('200');
  const beatButtons = page.locator('button[data-testid^="beat-"]');
  await expect(beatButtons.first()).toBeVisible({ timeout: 30_000 });
  await beatButtons.first().click();
  await expect(page.getByTestId('single-prediction')).toBeVisible({ timeout: 30_000 });

  const modelSelect = page.getByRole('combobox',{name:'推理模型'});
  for (const modelName of ['Random Forest', 'Logistic Regression', '1D-CNN']) {
    const predictionResponse = page.waitForResponse((response) => response.url().includes('/api/inference/beat') && response.request().method() === 'POST' && response.status() === 200);
    await modelSelect.click();
    const option = page.locator('.ant-select-dropdown:visible .ant-select-item-option').filter({ hasText: modelName });
    await expect(option).toBeVisible();
    await option.click();
    await predictionResponse;
    await expect(page.getByTestId('single-prediction')).toBeVisible();
  }

  await page.getByRole('button', { name: '比较三个模型' }).click();
  await page.locator('.comparison-table summary').click();await expect(page.getByRole('cell', { name: 'Logistic Regression', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'Random Forest', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: '1D-CNN', exact: true })).toBeVisible();

  await page.locator('.ant-segmented-item').nth(1).click();
  await expect(page.getByText('N / S / V / F', { exact: true }).first()).toBeVisible();
  await expect(page.locator('button[data-testid^="beat-"]').first()).toBeVisible();

  await page.getByRole('button', { name: '播放历史片段' }).click();
  await expect(page.getByText(/已缓存 \d+ 个可推理心拍/)).toBeVisible({ timeout: 60_000 });
  await page.getByRole('button', { name: '暂停' }).click();
  await page.locator('.playback-actions .ant-select').click();
  await page.getByText('2×', { exact: true }).click();
  await expect(page.locator('.playback-actions .ant-select')).toContainText('2×');
  await page.locator('.playback-timeline .ant-slider').click({ position: { x: 50, y: 8 } });
  await page.getByRole('button', { name: '继续' }).click();
  await page.getByRole('button', { name: '暂停' }).click();
  await page.getByRole('button', { name: '停止' }).click();

  expect(pageErrors).toEqual([]);
  expect(apiFailures).toEqual([]);
});
