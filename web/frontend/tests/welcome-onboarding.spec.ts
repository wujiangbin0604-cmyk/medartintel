import { test, expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const output=path.resolve(__dirname,'../../docs/screenshots/welcome_onboarding');fs.mkdirSync(output,{recursive:true});
const game='/interactive-lab/heartbeat-hunter',key='ecg_ai_welcome_v1';
async function shot(page:Page,name:string){await page.waitForTimeout(1300);const modal=/^(welcome_|hover_|reduced_motion|game_unavailable|first_game_tutorial)/.test(name);await page.screenshot({path:path.join(output,name+'.png'),fullPage:!modal});}
async function seed(page:Page,tutorial=false){await page.addInitScript(({tutorial,key})=>{localStorage.setItem(key,JSON.stringify({version:1,completed:true,doNotAutoShow:false}));if(tutorial)localStorage.setItem('ecg_ai_hunter_tutorial_v1','completed');},{tutorial,key});}
async function tutorial(page:Page){await expect(page.getByRole('dialog',{name:'心跳猎人 · 玩法说明'})).toBeVisible();await page.getByRole('button',{name:'我已了解，进入准备页'}).click();}

test('首次欢迎、跳过无游戏请求、勾选持久化、刷新不重现、清除后重现',async({page})=>{
 const gameRequests:string[]=[];page.on('request',r=>{if(r.url().includes('/api/games/'))gameRequests.push(r.url());});await page.goto('/');
 await expect(page.getByRole('dialog',{name:'欢迎来到 ECG-AI！'})).toBeVisible();await expect(page.getByText('心电波形预览',{exact:true})).toBeVisible();
 await page.getByRole('checkbox',{name:'下次不再自动显示'}).check();await page.getByRole('button',{name:'先逛逛平台',exact:true}).click();await expect(page.getByTestId('welcome-onboarding')).toBeHidden();await expect(page).toHaveURL(/\/dashboard$/);expect(gameRequests).toEqual([]);
 const state=await page.evaluate(key=>JSON.parse(localStorage.getItem(key)!),key);expect(state).toMatchObject({version:1,completed:true,choice:'browse',doNotAutoShow:true});
 await page.reload();await expect(page.getByRole('heading',{name:'项目总览',exact:true})).toBeVisible();await expect(page.getByTestId('welcome-onboarding')).toBeHidden();
 await page.evaluate(key=>localStorage.removeItem(key),key);await page.reload();await expect(page.getByTestId('welcome-onboarding')).toBeVisible();
});

test('欢迎进入真实游戏、首次教程不计时、手动开局、刷新恢复',async({page})=>{
 let starts=0;page.on('request',r=>{if(r.url().endsWith('/heartbeat-hunter/start'))starts++;});await page.goto('/dashboard');await page.getByRole('button',{name:'开始心跳挑战',exact:true}).click();await expect(page).toHaveURL(/heartbeat-hunter/);
 await expect(page.getByRole('dialog',{name:'心跳猎人 · 玩法说明'})).toBeVisible();await expect(page.getByTestId('countdown')).toHaveText('02:00');await page.waitForTimeout(1200);expect(starts).toBe(0);await expect(page.getByTestId('countdown')).toHaveText('02:00');await shot(page,'first_game_tutorial');
 await tutorial(page);await expect(page.getByRole('button',{name:'开始挑战',exact:true})).toBeEnabled();await shot(page,'game_ready');expect(starts).toBe(0);
 await page.getByRole('button',{name:'开始挑战',exact:true}).click();await expect(page.getByText('挑战进行中',{exact:true})).toBeVisible();expect(starts).toBe(1);
 const sid=await page.evaluate(()=>localStorage.getItem('hunter.active.v1'));await page.reload();await expect(page.getByText('挑战进行中',{exact:true})).toBeVisible();expect(await page.evaluate(()=>localStorage.getItem('hunter.active.v1'))).toBe(sid);expect(starts).toBe(1);
});

test('首页推荐卡、常驻侧栏子入口、手动重开欢迎均可访问',async({page})=>{
 await seed(page);await page.goto('/dashboard');await expect(page.getByRole('region',{name:'心跳猎人游戏推荐'})).toBeVisible();await page.getByRole('button',{name:'查看欢迎引导'}).click();await expect(page.getByTestId('welcome-onboarding')).toBeVisible();await page.getByRole('button',{name:'先逛逛平台'}).click();
 await page.getByRole('button',{name:'推荐卡开始挑战',exact:true}).click();await expect(page).toHaveURL(/heartbeat-hunter/);await tutorial(page);await expect(page.getByRole('button',{name:'开始挑战',exact:true})).toBeEnabled();
 await page.goto('/dashboard');await page.getByRole('link',{name:/Heartbeat Hunter · 心跳猎人/}).click();await expect(page).toHaveURL(/heartbeat-hunter/);await expect(page.getByText('准备就绪',{exact:true})).toBeVisible();
});

test('游戏结束：再玩、答案、真实 AI 同拍推理、探索工作台',async({page})=>{
 await seed(page,true);await page.goto(game);await page.getByRole('button',{name:'开始挑战',exact:true}).click();await expect(page.getByText('挑战进行中',{exact:true})).toBeVisible();await page.getByRole('button',{name:'提交答案',exact:true}).click();await expect(page.getByText('本关已完成',{exact:true})).toBeVisible();
 const actions=page.getByRole('generic',{name:'游戏结束后继续探索'});await expect(page.getByRole('button',{name:'再来一次',exact:true})).toBeEnabled();await page.getByRole('button',{name:'查看本轮答案',exact:true}).click();await expect(page.locator('.hunter-answer-list button').first()).toBeInViewport();await shot(page,'postgame_ai_entry');
 const selected=page.locator('.hunter-answer-list button.ant-btn-primary');const label=(await selected.getAttribute('aria-label'))!;const sample=Number(label.split(' ')[1]);
 const realInference=page.waitForResponse(r=>r.url().endsWith('/api/inference/beat')&&r.request().postDataJSON()?.annotation_sample===sample);
 await page.getByRole('button',{name:'看看 AI 如何判断',exact:true}).click();await expect(page).toHaveURL(new RegExp(`/ai-inference\\?.*annotation_sample=${sample}`));const response=await realInference;expect(response.status()).toBe(200);const inference=await response.json();expect(inference.annotation_sample).toBe(sample);expect(inference.task).toBe('nv');await expect(page.getByRole('heading',{name:'AI 智能检测',exact:true})).toBeVisible();await shot(page,'real_ai_inference');
 await page.goBack();await expect(page.getByText('本关已完成',{exact:true})).toBeVisible();await page.getByRole('button',{name:/探索 ECG 分析平台/}).click();await expect(page).toHaveURL(/\/ai-detection\?/);await expect(page.locator('.waveform-chart canvas').first()).toBeVisible();
});

test('游戏未就绪：欢迎保留首页，直接访问也可重试或返回',async({page})=>{
 let starts=0;page.on('request',r=>{if(r.url().endsWith('/heartbeat-hunter/start'))starts++;});await page.route('**/api/games/heartbeat-hunter/config',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'关卡服务离线'})}));
 await page.goto('/dashboard');await page.getByRole('button',{name:'开始心跳挑战',exact:true}).click();await expect(page.getByText('游戏暂时不可用',{exact:true})).toBeVisible();await expect(page).toHaveURL(/\/dashboard$/);expect(starts).toBe(0);await shot(page,'game_unavailable');
 await page.getByRole('button',{name:'先逛逛平台'}).click();await page.goto(game);await tutorial(page);await expect(page.getByText(/游戏暂时不可用：关卡服务离线/)).toBeVisible();await expect(page.getByRole('button',{name:'开始挑战',exact:true})).toBeDisabled();await expect(page.getByRole('link',{name:'返回首页'})).toBeVisible();
 await page.unroute('**/api/games/heartbeat-hunter/config');await page.getByRole('button',{name:'重试连接'}).click();await expect(page.getByRole('button',{name:'开始挑战',exact:true})).toBeEnabled();expect(starts).toBe(0);
});

test('存储不可用：欢迎可跳过、平台与游戏仍可使用',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await page.addInitScript(()=>{Storage.prototype.getItem=()=>{throw new DOMException('blocked','SecurityError');};Storage.prototype.setItem=()=>{throw new DOMException('blocked','SecurityError');};Storage.prototype.removeItem=()=>{throw new DOMException('blocked','SecurityError');};});
 await page.goto('/dashboard');await expect(page.getByTestId('welcome-onboarding')).toBeVisible();await page.getByRole('button',{name:'先逛逛平台'}).click();await expect(page.getByRole('heading',{name:'项目总览',exact:true})).toBeVisible();await page.getByRole('button',{name:'推荐卡开始挑战'}).click();await tutorial(page);await page.getByRole('button',{name:'开始挑战',exact:true}).click();await expect(page.getByText('挑战进行中',{exact:true})).toBeVisible();expect(errors).toEqual([]);
});

test('reduced motion、无等待交互、键盘关闭和不保存医学信息',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/dashboard');await expect(page.getByTestId('welcome-onboarding')).toHaveAttribute('data-reduced','true');const path=page.locator('.welcome-preview-chart svg path[stroke-width="2.8"]').first();await expect(path).toBeVisible();await shot(page,'reduced_motion');await page.keyboard.press('Escape');await expect(page.getByTestId('welcome-onboarding')).toBeHidden();
 const saved=await page.evaluate(key=>JSON.parse(localStorage.getItem(key)!),key);expect(Object.keys(saved).sort()).toEqual(['version','completed','choice','doNotAutoShow','completedAt'].sort());await page.reload();await expect(page.getByRole('heading',{name:'项目总览',exact:true})).toBeVisible();await expect(page.getByTestId('welcome-onboarding')).toBeHidden();
});

test('原有功能回归：Dashboard 筛选、ECG 心拍分析、AI 模型切换',async({page})=>{
 await seed(page,true);await page.goto('/dashboard');await expect(page.getByTestId('count-scale')).toHaveAttribute('data-mode','count');
 await page.getByText('对数',{exact:true}).click();await expect(page.getByTestId('count-scale')).toHaveAttribute('data-mode','log');await page.getByRole('button',{name:'筛选类别 V',exact:true}).click();await expect(page.locator('.split-focus')).toContainText('V');
 await page.getByRole('link',{name:'ECG 波形分析',exact:true}).click();await expect(page.locator('.waveform-chart canvas').first()).toBeVisible();const beat=page.locator('.annotation-shortcuts button').first();await expect(beat).toBeVisible();
 const prediction=page.waitForResponse(r=>r.url().endsWith('/api/inference/beat'));await beat.click();expect((await prediction).status()).toBe(200);await expect(page.getByTestId('single-prediction').first()).toBeVisible();
 await page.getByRole('link',{name:'AI 智能检测',exact:true}).click();await expect(page.getByRole('heading',{name:'AI 智能检测',exact:true})).toBeVisible();await expect(page.getByRole('combobox',{name:'推理模型'})).toBeEnabled();
 const changed=page.waitForResponse(r=>r.url().endsWith('/api/inference/beat')&&r.request().postDataJSON()?.model_id==='random_forest');await page.getByRole('combobox',{name:'推理模型'}).click();await page.locator('.ant-select-item-option-content').filter({hasText:/Random Forest|随机森林/}).click();const real=await changed;expect(real.status()).toBe(200);expect((await real.json()).model_id).toBe('random_forest');await expect(page.getByTestId('single-prediction').first()).toContainText('random forest');
});

test('普通 HTTP 服务器兼容：randomUUID 不可用时仍可创建匿名玩家并开始游戏',async({page})=>{
 await seed(page,true);await page.addInitScript(()=>{Object.defineProperty(crypto,'randomUUID',{value:undefined,configurable:true});});await page.goto(game);
 await expect(page.getByRole('button',{name:'开始挑战',exact:true})).toBeEnabled();await page.getByRole('button',{name:'开始挑战',exact:true}).click();await expect(page.getByText('挑战进行中',{exact:true})).toBeVisible();
 expect(await page.evaluate(()=>localStorage.getItem('hunter.player.v1'))).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});

for(const [width,height] of [[1920,1080],[1440,900],[1366,768],[745,900]]){
 test(`欢迎视觉与响应式 ${width}x${height}`,async({page})=>{
  await page.setViewportSize({width,height});await page.goto('/dashboard');await expect(page.getByTestId('welcome-onboarding')).toBeVisible();await shot(page,`welcome_${width}x${height}`);
  const button=page.getByRole('button',{name:'开始心跳挑战',exact:true});await button.hover();await shot(page,`hover_${width}x${height}`);
  const bounds=await page.locator('.welcome-onboarding-modal .ant-modal').boundingBox();expect(bounds!.x).toBeGreaterThanOrEqual(0);expect(bounds!.x+bounds!.width).toBeLessThanOrEqual(width+1);expect(bounds!.height).toBeLessThanOrEqual(height);
  const footer=page.locator('.welcome-footer');await expect(footer).toBeInViewport();await page.getByRole('button',{name:'先逛逛平台'}).click();await expect(page.getByRole('region',{name:'心跳猎人游戏推荐'})).toBeVisible();await shot(page,`dashboard_card_${width}x${height}`);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width+1);
 });
}
