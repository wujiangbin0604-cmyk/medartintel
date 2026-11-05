import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const out=path.resolve(__dirname,'../../docs/visual_fidelity/regression');
fs.mkdirSync(out,{recursive:true});
const docs=path.resolve(__dirname,'../../docs');
test.setTimeout(180_000);

async function settled(page: any) {
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.ant-skeleton')).toHaveCount(0);
  await page.waitForTimeout(250);
}

for(const [width,height] of [[1366,768],[1440,900],[1920,1080]]) {
  test(`real pages screenshot review ${width}x${height}`,async({page})=>{
    await page.setViewportSize({width,height});
    const errors:string[]=[];const failed:string[]=[];const warnings:string[]=[]; const checks:any[]=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('console',m=>{if(['error','warning'].includes(m.type()))warnings.push(m.text());});
    page.on('response',r=>{if(r.status()>=400)failed.push(`${r.status()} ${r.url()}`);});
    for(const route of ['dashboard','ai-detection','comparison','experiments','generalization','gallery']) {
      await page.goto(`/${route==='comparison'?'ai-detection':route}`);
      const headings:Record<string,string>={dashboard:'项目总览','ai-detection':'ECG 心拍分析',comparison:'ECG 心拍分析',experiments:'AI 模型实验中心',generalization:'错误与泛化分析',gallery:'科研可视化图库'};
      await expect(page.getByRole('heading',{name:headings[route],exact:true})).toBeVisible();
      await settled(page);
      await expect(page.locator('.platform-header')).toHaveCount(1);
      if(route==='comparison') {
        await page.locator('button[data-testid^="beat-"]').first().click();
        await expect(page.getByTestId('single-prediction')).toBeVisible();
        await page.getByRole('button',{name:'比较三个模型',exact:true}).click();
        await page.locator('.comparison-table summary').click();await expect(page.getByRole('cell',{name:'Logistic Regression',exact:true})).toBeVisible();
      }
      if(route==='gallery') {
        // Exercise native lazy loading across the complete real gallery before capture.
        const images=page.locator('.figure-preview img');
        for(let i=0;i<await images.count();i++)await images.nth(i).scrollIntoViewIfNeeded();
        await page.waitForLoadState('networkidle');await page.evaluate(()=>window.scrollTo(0,0));
        await expect(page.locator('.ant-image-error')).toHaveCount(0);
      }
      await page.screenshot({path:path.join(out,`${route}_${width}x${height}.png`),fullPage:true});
      const layout=await page.evaluate(()=>({body:document.body.scrollWidth,viewport:innerWidth,charts:[...document.querySelectorAll('[role="img"]')].map(e=>({label:e.getAttribute('aria-label'),width:e.getBoundingClientRect().width})),overflow:[...document.querySelectorAll('.ant-card,.research-heading,.platform-header,.workspace-grid')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>e.className)}));
      checks.push({route,...layout});expect(layout.body).toBeLessThanOrEqual(width+1);expect(layout.overflow).toEqual([]);
      if(route==='experiments') {
        await page.getByText('行归一化',{exact:true}).click();
        await page.getByRole('tab',{name:'N / S / V / F 四分类'}).click();await settled(page);
        await page.screenshot({path:path.join(out,`experiments_nsvf_${width}x${height}.png`),fullPage:true});
      }
    }
    fs.writeFileSync(path.join(docs,`phase5_regression_browser_${width}.json`),JSON.stringify({checks,errors,failed,warnings},null,2));
    expect(errors).toEqual([]);expect(failed).toEqual([]);
  });
}

test('complete eight-step presentation with real inference and playback',async({page})=>{
  await page.goto('/presentation-demo');await settled(page);
  await page.getByRole('button',{name:'全屏'}).click();
  await expect.poll(()=>page.evaluate(()=>Boolean(document.fullscreenElement))).toBe(true);
  await page.evaluate(()=>document.exitFullscreen());
  for(let step=0;step<8;step++) {
    await expect(page.locator('.demo-toolbar')).toContainText(`第 ${step+1} / 8 步`);
    await settled(page);
    if(step===2)await expect(page.locator('.beat-heading').first()).toBeVisible();
    if(step===3) {
      const response=page.waitForResponse(r=>r.url().includes('/api/inference/beat')&&r.request().method()==='POST');
      await page.getByRole('button',{name:'开始分析',exact:true}).click();
      const payload=await(await response).json();expect(payload.model_id).toBe('cnn_1d');expect(payload.record_id).toBe('200');
      await expect(page.getByTestId('single-prediction')).toBeVisible();
    }
    if(step===4){await page.getByRole('button',{name:'比较三个模型',exact:true}).click();await page.locator('.comparison-table summary').click();await expect(page.getByRole('cell',{name:'Logistic Regression',exact:true})).toBeVisible();}
    if(step===5){await page.getByRole('button',{name:'播放历史片段'}).click();await expect(page.locator('.playback-actions').getByRole('button',{name:'暂停'})).toBeVisible();await page.locator('.playback-actions').getByRole('button',{name:'暂停'}).click();}
    if(step===6){await page.getByRole('tab',{name:'N / S / V / F 四分类'}).click();}
    await page.screenshot({path:path.join(out,`demo_step${step+1}_1280x720.png`),fullPage:true});
    if(step<7)await page.getByRole('button',{name:'下一页',exact:true}).click();
  }
  await page.getByRole('button',{name:'上一页',exact:true}).click();await expect(page.locator('.demo-toolbar')).toContainText('第 7 / 8 步');
  await page.getByRole('button',{name:'退出演示',exact:true}).click();await expect(page).toHaveURL(/dashboard/);
});

test('gallery search preview report and original image download',async({page})=>{
  await page.goto('/gallery');await expect(page.getByRole('heading',{name:'科研可视化图库'})).toBeVisible();await settled(page);
  await page.getByRole('textbox',{name:'搜索科研图像'}).fill('confusion');
  await expect(page.locator('.figure-card').first()).toBeVisible();
  await page.locator('.figure-preview').first().click();await expect(page.locator('.ant-modal img')).toBeVisible();await page.locator('.ant-modal-close').click();
  await page.getByRole('button',{name:'来源报告'}).first().click();await expect(page.locator('.report-content')).not.toBeEmpty();await page.locator('.ant-drawer-close').click();
  const download=page.waitForEvent('download');await page.locator('a[download]').first().click();expect((await download).suggestedFilename()).toMatch(/\.png$/);
  await page.getByRole('textbox',{name:'搜索科研图像'}).fill('no-figure-matches-this');await expect(page.getByText('未找到匹配图像，请调整搜索或类别')).toBeVisible();
});

test('request errors timeout and missing images have visible recoverable states',async({page})=>{
  test.setTimeout(70000);
  await page.route('**/api/research/summary',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'测试注入：研究文件不可用'})}));
  await page.goto('/experiments',{waitUntil:'domcontentloaded'});await expect(page.getByText('测试注入：研究文件不可用')).toBeVisible();
  await page.unroute('**/api/research/summary');await page.getByRole('button',{name:'重试'}).click();await expect(page.getByRole('heading',{name:'AI 模型实验中心'})).toBeVisible();
  await page.route('**/api/research/figures/0*',r=>r.fulfill({status:404,body:'测试注入：图像缺失'}));
  await page.goto('/gallery');await expect(page.locator('.ant-image-error').first()).toBeVisible();
  await page.unroute('**/api/research/figures/0*');
  await page.route('**/api/ecg/records',()=>new Promise(()=>{}));
  await page.goto('/ai-detection',{waitUntil:'domcontentloaded'});await expect(page.getByText(/请求超时（30 秒）/)).toBeVisible({timeout:40_000});
  await page.unroute('**/api/ecg/records');await page.getByRole('button',{name:'重试',exact:true}).click();await expect(page.getByRole('heading',{name:'ECG 心拍分析'})).toBeVisible();
});

test('rapid model selection and record switch discard stale outputs',async({page})=>{
  await page.goto('/ai-detection');await settled(page);
  await page.locator('button[data-testid^="beat-"]').first().click();await expect(page.getByTestId('single-prediction')).toBeVisible();
  await page.route('**/api/inference/beat',async route=>{await new Promise(r=>setTimeout(r,1000));await route.continue().catch(()=>{});});
  const select=page.getByRole('combobox',{name:'推理模型',exact:true});
  for(const name of ['Random Forest','Logistic Regression','1D-CNN']){await select.click();await page.locator('.ant-select-dropdown:visible').getByText(name,{exact:true}).click();}
  await expect(page.getByTestId('single-prediction')).toContainText('cnn 1d');
  await page.getByRole('button',{name:'播放历史片段'}).click();await expect(page.locator('.playback-actions').getByRole('button',{name:'暂停'})).toBeVisible();
  await page.getByRole('combobox',{name:'MIT-BIH 记录',exact:true}).fill('100');await page.locator('.ant-select-dropdown:visible').getByText(/^100（/).click();
  await settled(page);await expect(page.getByRole('button',{name:'播放历史片段'})).toBeVisible();await expect(page.getByTestId('single-prediction')).toHaveCount(0);
  // View-only record and non-model lead remain browsable.
  await page.getByRole('combobox',{name:'MIT-BIH 记录',exact:true}).fill('102');await page.locator('.ant-select-dropdown:visible').getByText(/^102（/).click();await settled(page);
  await expect(page.getByText(/此记录不属于当前 44/)).toBeVisible();
});

test('real API and browser performance sampling',async({page,request})=>{
  const result:any={environment:'Umi development server / Chrome / local CPU',api:{},pages:{},playback:{}};
  const records=await(await request.get('/api/ecg/records')).json();expect(records.records.length).toBeGreaterThan(0);
  const marks=await(await request.get('/api/ecg/annotations?record_id=200&start_sec=6&duration_sec=10&task=nv')).json();
  const sample=marks.annotations.find((r:any)=>r.within_task).annotation_sample;
  for(const endpoint of ['window','single','compare']){
    const times=[];
    for(let i=0;i<5;i++){const start=performance.now();const response=endpoint==='window'?await request.get('/api/ecg/window?record_id=200&start_sec=6&duration_sec=10&lead_name=MLII'):await request.post(`/api/inference/${endpoint==='single'?'beat':'compare'}`,{data:{record_id:'200',annotation_sample:sample,task:'nv',...(endpoint==='single'?{model_id:'cnn_1d'}:{})}});expect(response.ok()).toBeTruthy();times.push(performance.now()-start);}
    result.api[endpoint]={samples_ms:times,mean_ms:times.reduce((a,b)=>a+b,0)/times.length};
  }
  const cdp=await page.context().newCDPSession(page);await cdp.send('HeapProfiler.enable');
  for(const route of ['dashboard','ai-detection','experiments','generalization','gallery']){const start=performance.now();await page.goto('/'+route);await settled(page);result.pages[route]=performance.now()-start;}
  await page.goto('/ai-detection');await settled(page);const calls:string[]=[];page.on('request',r=>{if(r.url().includes('/api/'))calls.push(r.url());});
  await page.getByRole('button',{name:'播放历史片段'}).click();await expect(page.locator('.playback-actions').getByRole('button',{name:'暂停'})).toBeVisible();
  const count=calls.length;await page.waitForTimeout(2500);result.playback={requests_after_loaded:calls.slice(count),all_requests:calls};await page.locator('.playback-actions').getByRole('button',{name:'暂停'}).click();
  await cdp.send('HeapProfiler.collectGarbage');result.heap_before=(await cdp.send('Runtime.getHeapUsage')).usedSize;
  for(let i=0;i<12;i++){await page.locator('.platform-nav').getByRole('link',{name:i%2?'ECG 波形分析':'项目总览',exact:true}).click();await settled(page);}
  await cdp.send('HeapProfiler.collectGarbage');result.heap_after=(await cdp.send('Runtime.getHeapUsage')).usedSize;
  fs.writeFileSync(path.join(docs,'phase5_performance_dev.json'),JSON.stringify(result,null,2));
  expect(result.playback.requests_after_loaded.filter((url:string)=>url.includes('/inference/')||url.includes('/playback/'))).toEqual([]);
});

