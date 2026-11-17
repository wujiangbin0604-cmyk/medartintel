const {chromium,expect}=require('@playwright/test');
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../../..');const out=path.join(root,'reports/demo_20261117');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-proxy-server']});
 const context=await browser.newContext({viewport:{width:1672,height:1050}});const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('http://47.83.150.55:8000/ai-detection?record=200&time=6',{waitUntil:'networkidle',timeout:30000});
  const welcome=page.getByRole('button',{name:'先逛逛平台',exact:true});if(await welcome.isVisible())await welcome.click();
  const event=page.waitForResponse(r=>r.url().endsWith('/api/inference/beat')&&r.ok());
  await page.getByRole('button',{name:'开始分析',exact:true}).click();const prediction=await(await event).json();
  await expect(page.getByTestId('single-prediction')).toBeVisible();
  assert.equal(prediction.model_sha256,'5c4ff92e89f881d532eebf4b7f5fe6e6a240a5a88b820ca1d289e4af1fd78648');
  const compared=page.waitForResponse(r=>r.url().endsWith('/api/inference/compare')&&r.ok());
  await page.getByRole('button',{name:'比较三个模型',exact:true}).click();const comparison=await(await compared).json();
  assert.equal(comparison.models.length,3);assert.deepEqual(errors,[]);
  await page.screenshot({path:path.join(out,'public_demo.png'),fullPage:true});
  fs.writeFileSync(path.join(out,'public_browser.json'),JSON.stringify({status:'passed',time:new Date().toISOString(),network:'Chrome direct (--no-proxy-server)',url:page.url(),prediction,comparison,page_errors:errors,local_changes_deployed:false},null,2));
  console.log('PASS: public direct browser waveform, actual inference and three-model comparison');
 }finally{await context.close();await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
