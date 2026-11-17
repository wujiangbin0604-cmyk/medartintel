const {chromium,expect} = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../..');
const out = path.join(root, 'reports/demo_20261117');
fs.mkdirSync(out, {recursive:true});

(async()=>{
 const browser = await chromium.launch({channel:'chrome',headless:true});
 const context = await browser.newContext({viewport:{width:1672,height:1050},acceptDownloads:true});
 const page = await context.newPage();
 const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try {
  await page.goto('http://127.0.0.1:8144/ai-detection?record=200&time=6',{waitUntil:'networkidle'});
  fs.writeFileSync(path.join(out,'discovery.json'),JSON.stringify({buttons:await page.getByRole('button').allTextContents(),text:await page.locator('body').innerText()},null,2));
  await page.screenshot({path:path.join(out,'initial.png'),fullPage:true});
  if(process.argv.includes('--inspect'))return;
  const health=await (await context.request.get('http://127.0.0.1:8144/api/health')).json();
  assert.equal(health.models_loaded,6);
  const inference=page.waitForResponse(r=>r.url().endsWith('/api/inference/beat')&&r.request().method()==='POST'&&r.ok());
  await page.getByRole('button',{name:'开始分析',exact:true}).click();
  const prediction=await(await inference).json();
  await expect(page.getByTestId('single-prediction')).toBeVisible();
  assert.equal(prediction.prediction_source,'saved project model checkpoint');
  const comparison=page.waitForResponse(r=>r.url().endsWith('/api/inference/compare')&&r.ok());
  await page.getByRole('button',{name:'比较三个模型',exact:true}).click();
  const compared=await(await comparison).json();assert.equal(compared.models.length,3);
  assert(compared.models.every(m=>m.annotation_sample===prediction.annotation_sample));
  await page.waitForTimeout(800);
  await page.screenshot({path:path.join(out,'workbench_comparison.png'),fullPage:true});
  // Deliberate failure injection only verifies feedback; successful export below uses the real backend.
  await page.route('**/api/inference/report',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'验收故障注入：暂不可用'})}));
  await page.getByRole('button',{name:'导出分析报告',exact:true}).click();
  await expect(page.getByText('报告导出失败：验收故障注入：暂不可用',{exact:true})).toBeVisible();
  await page.unroute('**/api/inference/report');
  const downloadEvent=page.waitForEvent('download');
  await page.getByRole('button',{name:'导出分析报告',exact:true}).click();
  const download=await downloadEvent;const exportPath=path.join(out,download.suggestedFilename());await download.saveAs(exportPath);
  const report=JSON.parse(fs.readFileSync(exportPath,'utf8'));
  assert.equal(report.beat.annotation_sample,prediction.annotation_sample);
  assert.equal(report.expert_reference.aami_label,prediction.expert_label);
  assert.equal(report.selected_prediction.model_sha256,prediction.model_sha256);
  assert.equal(report.beat.filtered_amplitude_mv.length,253);
  assert.equal(report.comparison.models.length,3);
  assert.equal(report.provenance.normalization_fit_split,'train');
  await page.screenshot({path:path.join(out,'report_export_success.png'),fullPage:true});
  await page.getByRole('button',{name:'播放历史片段',exact:true}).click();
  await expect(page.getByRole('button',{name:'暂停',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'暂停',exact:true}).click();
  await page.screenshot({path:path.join(out,'historical_playback.png'),fullPage:true});
  await page.goto('http://127.0.0.1:8144/generalization',{waitUntil:'networkidle'});
  await page.getByRole('button',{name:'N → S',exact:true}).click();
  await expect(page.locator('.error-cases')).toContainText('2626');
  await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(700);
  await page.screenshot({path:path.join(out,'error_analysis.png'),fullPage:true});
  const errorLink=page.locator('.error-cases a').first();const errorHref=await errorLink.getAttribute('href');
  await errorLink.click();await page.waitForLoadState('networkidle');
  await expect(page.getByTestId('single-prediction')).toBeVisible();
  assert(page.url().includes('sample='));
  const visited=[];let gameSession;
  for(const [route,title] of [['experiments','AI 模型实验中心'],['gallery','科研可视化图库'],['interactive-lab/heartbeat-hunter','心跳猎人']]){
   await page.goto('http://127.0.0.1:8144/'+route,{waitUntil:'networkidle'});
   await expect(page.getByText(title,{exact:false}).first()).toBeVisible();
   if(route.includes('heartbeat-hunter')){
    const tutorial=page.getByRole('button',{name:'我已了解，进入准备页',exact:true});if(await tutorial.isVisible())await tutorial.click();
    const started=page.waitForResponse(r=>r.url().endsWith('/heartbeat-hunter/start')&&r.ok());
    await page.getByRole('button',{name:'开始挑战',exact:true}).click();gameSession=await(await started).json();
    assert(gameSession.signal.length>1000);assert.equal(gameSession.sampling_rate,360);
    await page.waitForTimeout(700);
   }
   visited.push(route);await page.screenshot({path:path.join(out,route.split('/').at(-1)+'.png'),fullPage:true});
  }
  await page.goto('http://127.0.0.1:8144/presentation-demo',{waitUntil:'networkidle'});
  await expect(page.getByText('课程答辩演示',{exact:true}).first()).toBeVisible();
  const welcome=page.getByRole('button',{name:'先逛逛平台',exact:true});if(await welcome.isVisible())await welcome.click();
  await page.screenshot({path:path.join(out,'presentation_demo.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({status:'passed',generated_at:new Date().toISOString(),environment:'Production build + real FastAPI / Chrome headless / loopback CPU; isolated game database',health,prediction,comparison:compared,report_file:path.relative(root,exportPath),error_drilldown_link:errorHref,visited,game:{record_id:gameSession.record_id,signal_points:gameSession.signal.length,sampling_rate:gameSession.sampling_rate},checks:['real_waveform','expert_annotation','actual_single_inference','same_beat_three_models','controlled_export_failure_feedback','real_report_download_and_hash','historical_playback_pause','saved_error_to_real_inference','experiments_gallery_game_render','real_game_start','presentation_route'],page_errors:errors,public_deployment_verified:false},null,2));
  console.log('PASS: 11 browser flow checks; real report downloaded; real game started; no page errors');
 } finally {await context.close();await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
