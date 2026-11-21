import { test, expect } from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs';

const output = process.env.ECG_REVALIDATION_SHOTS || path.resolve(__dirname, '../../../research_extensions/validation/screenshots');
fs.mkdirSync(output, { recursive: true });
test.beforeEach(async ({ page }) => { await page.addInitScript(() => { localStorage.setItem('ecg_ai_welcome_v1', JSON.stringify({ version: 1, completed: true })); localStorage.setItem('ecg_ai_hunter_tutorial_v1', 'completed'); }); });

test('真实结果、折/类别切换、空状态与刷新', async ({ page, request }) => {
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  const data = await (await request.get('/api/rhythm/summary')).json();
  await page.goto('/rhythm-lab'); await page.waitForLoadState('networkidle');
  await expect(page.getByRole('heading', { name: '节律融合与可靠性实验室', exact: true })).toBeVisible();
  const a2 = data.models.find((m: any) => m.model === 'A2');
  await expect(page.getByRole('cell', { name: `${(a2.pooled.macro_f1 * 100).toFixed(2)}%`, exact: true })).toBeVisible();
  await page.getByRole('combobox', { name: '分组评价折' }).click(); await page.getByTitle('外层 Fold 2', { exact: true }).click();
  await expect(page.getByRole('cell', { name: `${(data.folds.find((r: any) => r.fold === 1 && r.model === 'A2').macro_f1 * 100).toFixed(2)}%`, exact: true })).toBeVisible();
  if (data.config.seeds.length > 1) {
    const nextSeed = data.config.seeds[1];
    await page.getByRole('combobox', { name: '实验随机种子' }).click(); await page.getByTitle(`seed ${nextSeed}`, { exact: true }).click();
    const expected = data.folds.find((r: any) => r.fold === 1 && r.model === 'A2' && r.seed === nextSeed).macro_f1;
    await expect(page.getByRole('cell', { name: `${(expected * 100).toFixed(2)}%`, exact: true })).toBeVisible();
  }
  await page.getByRole('combobox', { name: '分析类别' }).click(); await page.getByTitle('F 类', { exact: true }).click();
  await page.getByRole('tab', { name: 'N / V', exact: true }).click(); await expect(page.getByText(/N\/V 新消融尚未执行/)).toBeVisible();
  await page.getByRole('tab', { name: 'N / S / V / F', exact: true }).click();
  await page.getByRole('button', { name: '查看节律分支', exact: true }).click(); await expect(page.locator('.rhythm-architecture')).toHaveClass(/stage-1/);
  await page.reload(); await expect(page.getByRole('img', { name: '四模型真实消融指标', exact: true }).locator('canvas')).toBeVisible();
  expect(errors).toEqual([]);
});

for (const [width, height, reduced] of [[1440, 1000, false], [390, 844, true]] as const) {
  test(`真实单拍、独立阈值与布局 ${width}`, async ({ page, request }) => {
    const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
    await page.setViewportSize({ width, height }); if (reduced) await page.emulateMedia({ reducedMotion: 'reduce' });
    const samples = await (await request.get('/api/rhythm/samples?label=S')).json();
    const s = samples.samples.find((s: any) => s.record_id !== '114');
    await page.goto(`/rhythm-lab?record_id=${s.record_id}&annotation_sample=${s.annotation_sample}`); await page.waitForLoadState('networkidle');
    await expect(page.getByTestId('rhythm-beat-results')).toContainText(`样本 ${s.annotation_sample}`);
    await expect(page.getByRole('cell', { name: 'A2 · 节律形态融合', exact: true })).toHaveCount(3);
    await expect(page.getByRole('img', { name: '真实单拍滤波波形', exact: true }).locator('canvas')).toBeVisible();
    await page.getByRole('combobox', { name: '拒识指标', exact: true }).click(); await page.getByTitle('信息熵', { exact: true }).click();
    await expect(page.getByText('类别分数和熵均未经临床校准。', { exact: false })).toBeVisible();
    const extent = await page.evaluate(() => ({ viewport: innerWidth, page: document.documentElement.scrollWidth }));
    expect(extent.page).toBeLessThanOrEqual(extent.viewport + 1);
    if (reduced) expect(await page.locator('.rhythm-branch').first().evaluate(e => getComputedStyle(e).transitionDuration)).toBe('0s');
    await page.keyboard.press('Escape'); await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(output, `rhythm_top_${width}.png`) });
    await page.screenshot({ path: path.join(output, `rhythm_${width}.png`), fullPage: true });
    await page.reload(); await expect(page.getByTestId('rhythm-beat-results')).toContainText(`样本 ${s.annotation_sample}`);
    expect(errors).toEqual([]);
  });
}

test('研究未就绪与原页面回归', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  await page.route('**/api/rhythm/summary', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'not_ready', models: [], folds: [], per_class: [], patients: [], uncertainty: { status: 'not_ready' } }) }));
  await page.goto('/rhythm-lab'); await expect(page.getByText('完整分组实验尚未就绪，完成后重新加载可查看实际结果。')).toBeVisible();
  await page.unroute('**/api/rhythm/summary');
  for (const [route, heading] of [['dashboard', '项目总览'], ['experiments', 'AI 模型实验中心'], ['generalization', '错误与泛化分析'], ['gallery', '科研可视化图库'], ['ai-detection', 'ECG 心拍分析'], ['interactive-lab', '心电互动实验室']]) {
    await page.goto('/' + route); await expect(page.getByRole('heading', { name: new RegExp(heading) })).toBeVisible(); await page.waitForLoadState('networkidle');
  }
  expect(errors).toEqual([]);
});

test('Hunter 作答、计时、评分、历史与精确样本联动', async ({ page, request }) => {
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/interactive-lab/heartbeat-hunter');
  await expect(page.getByRole('link', { name: '查看模型如何识别这一心拍', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '开始挑战', exact: true }).click();
  await expect(page.getByText('挑战进行中', { exact: true })).toBeVisible();
  const sid = (await page.evaluate(() => localStorage.getItem('hunter.active.v1')))!;
  const session = await (await request.get(`/api/games/heartbeat-hunter/session/${sid}`)).json();
  await page.getByRole('button', { name: '候选心拍 1', exact: true }).click();
  await expect(page.getByRole('button', { name: '候选心拍 1', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: '候选心拍 1', exact: true }).click();
  await page.getByRole('button', { name: '暂停游戏', exact: true }).click();
  const remaining = await page.getByTestId('countdown').innerText(); await page.waitForTimeout(1100); expect(await page.getByTestId('countdown').innerText()).toBe(remaining);
  await page.getByRole('button', { name: '恢复游戏', exact: true }).click();
  await page.getByRole('button', { name: '提交答案', exact: true }).click();
  await expect(page.getByText('本关已完成', { exact: true })).toBeVisible();
  const result = await (await request.get(`/api/games/heartbeat-hunter/session/${sid}`)).json();
  expect(result.result.correct).toBe(0); expect(result.result.score).toBe(-20 * result.result.missed);
  await page.reload(); await expect(page.getByTestId('game-score')).toHaveText(String(result.result.score));
  const link = page.getByRole('link', { name: '查看模型如何识别这一心拍', exact: true });
  const href = await link.getAttribute('href'); expect(href).toContain(`record_id=${session.record_id}`);
  const position = new URL(href!, 'http://localhost').searchParams.get('annotation_sample'); expect(position).toBeTruthy();
  await link.click(); await expect(page.getByTestId('rhythm-beat-results')).toContainText(`样本 ${position}`);
  await page.goto('/interactive-lab'); await expect(page.locator('.hunter-history-row')).not.toHaveCount(0);
  expect(errors).toEqual([]);
});
