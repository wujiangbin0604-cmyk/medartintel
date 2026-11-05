import {expect,test} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs';
const out=path.resolve(__dirname,'../../docs/visual_fidelity/regression');fs.mkdirSync(out,{recursive:true});
test('phase4 smoke real pages',async({page})=>{
 test.setTimeout(120000);const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setViewportSize({width:1440,height:900});
 for(const [route,title] of [['dashboard','项目总览'],['ai-detection','ECG 心拍分析'],['experiments','AI 模型实验中心'],['generalization','错误与泛化分析'],['gallery','科研可视化图库']]){
  await page.goto('/'+route);await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible({timeout:60000});await page.waitForLoadState('networkidle');await page.waitForTimeout(700);
  if(route==='ai-detection'){await page.locator('button[data-testid^="beat-"]').first().click();await expect(page.getByTestId('single-prediction')).toBeVisible();await page.getByRole('button',{name:'比较三个模型',exact:true}).click();await page.locator('.comparison-table summary').click();await expect(page.getByRole('cell',{name:'Logistic Regression',exact:true})).toBeVisible();}
  await page.waitForTimeout(700);await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(150);
  await page.screenshot({path:path.join(out,`smoke_${route}.png`),fullPage:true});
  expect(await page.evaluate(()=>document.body.scrollWidth<=innerWidth+1)).toBe(true);
 }
 expect(errors).toEqual([]);
});

async function ready(page:any,title:string){await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible({timeout:60000});await page.waitForLoadState('networkidle');await page.waitForTimeout(650);}
async function shot(page:any,name:string){await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(650);await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});expect(await page.evaluate(()=>document.body.scrollWidth<=innerWidth+1)).toBe(true);}
for(const [width,height] of [[1366,768],[1440,900],[1920,1080]])test(`phase4 visual and linked state ${width}x${height}`,async({page})=>{
 test.setTimeout(180000);await page.setViewportSize({width,height});const errors:string[]=[];const failures:string[]=[];page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)failures.push(`${r.status()} ${r.url()}`);});
 await page.goto('/dashboard');await ready(page,'项目总览');await shot(page,`dashboard_${width}x${height}`);
 const pie=page.getByRole('img',{name:'交互心拍类别环形图'});await pie.scrollIntoViewIfNeeded();const pieBox=(await pie.boundingBox())!;await page.mouse.click(pieBox.x+pieBox.width/2+Math.min(pieBox.width,pieBox.height)*.36,pieBox.y+pieBox.height/2);await expect(page.locator('.split-focus')).toContainText('当前筛选：N');
 await page.getByRole('button',{name:'筛选类别 V',exact:true}).click();await expect(page.locator('.split-focus')).toContainText('当前筛选：V');await expect(page.getByText('当前筛选：V。按受试者分组，分区统计同步更新。')).toBeVisible();await shot(page,`dashboard_filter_${width}x${height}`);
 await page.getByRole('button',{name:'收起侧边栏',exact:true}).click();await expect(page.locator('.platform')).toHaveClass(/sidebar-collapsed/);await page.getByRole('button',{name:'展开侧边栏',exact:true}).click();
 await page.goto('/ai-detection');await ready(page,'ECG 心拍分析');await shot(page,`ecg_${width}x${height}`);
 await page.route('**/api/inference/beat',async route=>{await new Promise(r=>setTimeout(r,900));await route.continue().catch(()=>{});});
 await page.locator('button[data-testid^="beat-"]').first().click();await expect(page.locator('.inline-loading')).toContainText('运行真实模型');await page.screenshot({path:path.join(out,`inference_loading_${width}x${height}.png`),fullPage:true});await expect(page.getByTestId('single-prediction')).toBeVisible();await page.unroute('**/api/inference/beat');
 await shot(page,`beat_selected_${width}x${height}`);await page.locator('.morphology-details summary').click();await page.getByRole('button',{name:'查看心拍细节',exact:true}).click();await expect(page.locator('.beat-focus')).toBeVisible();await page.getByRole('button',{name:'返回完整波形',exact:true}).click();await page.locator('.morphology-details summary').click();
 await page.getByRole('button',{name:'比较三个模型',exact:true}).click();await expect(page.locator('.model-result-card .model-prediction')).toHaveCount(3);await page.waitForTimeout(600);
 await page.locator('.model-result-card').first().getByRole('button',{name:/N 类概率/}).click();await expect(page.locator('.model-cards .probability-selected')).toHaveCount(3);await shot(page,`comparison_${width}x${height}`);
 const selected=await page.locator('.beat-facts').first().innerText();await page.getByRole('button',{name:'选择模型卡片 Random Forest',exact:true}).click();await expect(page.locator('.model-result-card.current-model')).toContainText('Random Forest');await expect(page.locator('.beat-facts').first()).toHaveText(selected);await expect(page.locator('.model-result-card .model-prediction')).toHaveCount(3);
 await page.getByRole('button',{name:'播放历史片段'}).click();await expect(page.getByRole('button',{name:'暂停',exact:false})).toBeVisible();await expect.poll(async()=>Number(await page.locator('.playback-overlay').getAttribute('data-time'))).toBeGreaterThan(0);await shot(page,`playback_${width}x${height}`);
 await page.getByRole('button',{name:'暂停',exact:false}).click();const pause=await page.locator('.playback-overlay').getAttribute('data-time');await page.waitForTimeout(250);expect(await page.locator('.playback-overlay').getAttribute('data-time')).toBe(pause);
 await page.goto('/ai-inference');await ready(page,'AI 智能检测');await expect(page.getByTestId('single-prediction')).toBeVisible();await shot(page,`ai_detection_${width}x${height}`);
 await page.goto('/experiments');await ready(page,'AI 模型实验中心');await page.getByRole('tab',{name:'N / S / V / F 四分类'}).click();await shot(page,`experiment_nsvf_${width}x${height}`);
 const matrix=page.getByRole('img',{name:'N/S/V/F cnn_1d 真实标签与预测标签混淆矩阵'});await matrix.scrollIntoViewIfNeeded();const matrixBox=(await matrix.boundingBox())!;await page.mouse.click(matrixBox.x+75+(matrixBox.width-105)*1.5/4,matrixBox.y+32+(matrixBox.height-107)*.5/4);await expect(page.getByText('真实样本 · N → S')).toBeVisible();await expect(page.getByRole('link',{name:'查看 ECG 波形'}).first()).toBeVisible();await shot(page,`error_cases_${width}x${height}`);
 await page.goto('/generalization');await ready(page,'错误与泛化分析');await shot(page,`generalization_${width}x${height}`);
 await page.goto('/gallery');await ready(page,'科研可视化图库');await shot(page,`gallery_${width}x${height}`);
 await page.goto('/presentation-demo');await ready(page,'项目总览');await shot(page,`presentation_${width}x${height}`);
 expect(errors).toEqual([]);expect(failures).toEqual([]);fs.writeFileSync(path.resolve(__dirname,`../../docs/phase5_browser_${width}.json`),JSON.stringify({width,height,errors,failures},null,2));
});

test('phase4 reduced motion charts samples and gallery keyboard interaction',async({page})=>{
 test.setTimeout(120000);await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/dashboard');await ready(page,'项目总览');await expect(page.locator('html')).toHaveAttribute('data-motion','reduced');
 await page.getByRole('combobox',{name:'动画强度'}).click();await page.locator('.ant-select-dropdown:visible').getByText('完整动效',{exact:true}).click();await expect(page.locator('html')).toHaveAttribute('data-motion','reduced');
 await page.emulateMedia({reducedMotion:'no-preference'});await expect(page.locator('html')).toHaveAttribute('data-motion','full');
 await page.getByRole('combobox',{name:'动画强度'}).click();await page.locator('.ant-select-dropdown:visible').getByText('减少动效',{exact:true}).click();await expect(page.locator('html')).toHaveAttribute('data-motion','reduced');
 await page.goto('/experiments?task=nsvf');await ready(page,'AI 模型实验中心');await page.getByRole('button',{name:'N → S',exact:true}).click();const url=await page.getByRole('link',{name:'查看 ECG 波形'}).first().getAttribute('href');expect(url).toContain('record=');await page.getByRole('link',{name:'查看 ECG 波形'}).first().click();await ready(page,'ECG 心拍分析');await expect(page.locator('.beat-facts').first()).toBeVisible();
 const chart=page.getByRole('img',{name:'MIT-BIH ECG waveform and annotations'});await chart.hover();await page.mouse.wheel(0,-400);await expect(page.getByText('已缩放 · 可拖拽平移')).toBeVisible();await page.getByRole('button',{name:'重置视图',exact:true}).click();await expect(page.getByText('已缩放 · 可拖拽平移')).toHaveCount(0);
 await page.goto('/gallery');await ready(page,'科研可视化图库');await page.locator('.figure-preview').first().click();const title=await page.locator('.ant-modal-title').innerText();await page.keyboard.press('ArrowRight');await expect(page.locator('.ant-modal-title')).not.toHaveText(title);await page.getByRole('button',{name:'放大',exact:true}).click();await expect(page.getByText('125%',{exact:true})).toBeVisible();await page.keyboard.press('Escape');await expect(page.locator('.ant-modal')).not.toBeVisible();
 await page.goto('/presentation-demo');await ready(page,'项目总览');await page.getByRole('button',{name:'暂停演示',exact:true}).click();await expect(page.getByRole('button',{name:'下一页',exact:true})).toBeDisabled();await page.getByRole('button',{name:'继续演示',exact:true}).click();await expect(page.getByRole('button',{name:'下一页',exact:true})).toBeEnabled();
});

test('phase4 playback frame timing and short stability observation',async({page})=>{
 test.setTimeout(120000);await page.goto('/ai-detection');await ready(page,'ECG 心拍分析');await page.getByRole('spinbutton',{name:'窗口时长秒'}).fill('30');await page.getByRole('spinbutton',{name:'窗口时长秒'}).press('Tab');await page.waitForLoadState('networkidle');
 const cdp=await page.context().newCDPSession(page);await cdp.send('HeapProfiler.collectGarbage');const before=(await cdp.send('Runtime.getHeapUsage')).usedSize;
 const requests:string[]=[];page.on('request',r=>{if(r.url().includes('/api/'))requests.push(r.url());});await page.getByRole('button',{name:'播放历史片段'}).click();await expect(page.getByRole('button',{name:'暂停'})).toBeVisible({timeout:30000});const first=requests.length;
 const observationStart=performance.now();
 for(const speed of ['0.5×','2×','4×','1×']){await page.getByRole('combobox',{name:'回放速度'}).click();await page.locator('.ant-select-dropdown:visible').getByText(speed,{exact:true}).click();await expect(page.locator('.playback-actions .ant-select')).toContainText(speed);}
 const intervals=await page.evaluate(()=>new Promise<number[]>(resolve=>{const values:number[]=[];let last=performance.now();const end=last+6000;function tick(now:number){values.push(now-last);last=now;if(now>=end)resolve(values);else requestAnimationFrame(tick);}requestAnimationFrame(tick);}));
 await page.getByRole('button',{name:'暂停'}).click();const stopped=await page.locator('.playback-overlay').getAttribute('data-time');await page.waitForTimeout(300);expect(await page.locator('.playback-overlay').getAttribute('data-time')).toBe(stopped);
 const slider=page.locator('.playback-timeline .ant-slider');const bounds=(await slider.boundingBox())!;await slider.click({position:{x:bounds.width*.2,y:bounds.height/2}});const seek=Number(await page.locator('.playback-overlay').getAttribute('data-time'));await page.getByRole('button',{name:'继续',exact:false}).click();await page.waitForTimeout(300);expect(Number(await page.locator('.playback-overlay').getAttribute('data-time'))).toBeGreaterThan(seek);
 await page.waitForTimeout(12000);await page.getByRole('button',{name:'暂停'}).click();await cdp.send('HeapProfiler.collectGarbage');const after=(await cdp.send('Runtime.getHeapUsage')).usedSize;
 const sorted=intervals.slice(1).sort((a,b)=>a-b);const result={duration_seconds:(performance.now()-observationStart)/1000,raf_samples:sorted.length,median_frame_ms:sorted[Math.floor(sorted.length*.5)],p95_frame_ms:sorted[Math.floor(sorted.length*.95)],average_fps:1000/(sorted.reduce((a,b)=>a+b,0)/sorted.length),heap_before:before,heap_after:after,requests_after_loaded:requests.slice(first),repeated_inference_requests:requests.slice(first).filter(u=>u.includes('/inference/')||u.includes('/playback/')).length};fs.writeFileSync(path.resolve(__dirname,'../../docs/phase5_playback_performance.json'),JSON.stringify(result,null,2));expect(result.repeated_inference_requests).toBe(0);
});
