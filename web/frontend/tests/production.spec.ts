import {expect,test} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
test.skip(({baseURL})=>!baseURL?.endsWith(':8132'),'run with playwright.production.config.ts');
test('built site operates without external network and records production timings',async({page,request})=>{
  test.setTimeout(120000);
  const result:any={environment:'Umi production build + FastAPI same-origin loopback / Chrome / CPU',pages:{},api:{}};
  fs.mkdirSync(path.resolve(__dirname,'../../docs/visual_fidelity/regression'),{recursive:true});
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{const url=new URL(route.request().url());return ['127.0.0.1','localhost'].includes(url.hostname)?route.continue():route.abort();});
  for(const [route,title] of [['dashboard','项目总览'],['experiments','AI 模型实验中心'],['generalization','错误与泛化分析'],['gallery','科研可视化图库'],['ai-detection','ECG 心拍分析']]){
    const start=performance.now();await page.goto('/'+route);await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();await page.waitForLoadState('networkidle');result.pages[route]=performance.now()-start;
  }
  // Use the actual ECharts annotation pixel and wait for the animated chart to settle.
  const early=await(await request.get('/api/ecg/annotations?record_id=200&start_sec=0&duration_sec=10&task=nv')).json();
  const mark=early.annotations.find((r:any)=>r.aami_label==='N');
  const chart=page.getByRole('img',{name:'MIT-BIH ECG waveform and annotations',exact:true});await chart.scrollIntoViewIfNeeded();
  await expect(chart).toHaveAttribute('data-markers',/487/);
  const rendered=JSON.parse((await chart.getAttribute('data-markers'))!).find((m:any)=>m.sample===mark.annotation_sample);
  const position={x:rendered.pixel[0],y:rendered.pixel[1]};
  await chart.hover({position});await expect(chart.getByText(`样本 ${mark.annotation_sample}`,{exact:false})).toBeVisible();
  await chart.click({position});await expect(page.locator('.beat-facts')).toContainText(`${mark.time_seconds.toFixed(3)} s`);
  await expect(page.getByTestId('single-prediction')).toHaveCount(0);
  await expect(page.locator('.prediction-pending')).not.toBeEmpty();
  await page.screenshot({path:path.resolve(__dirname,'../../docs/visual_fidelity/regression/waveform_real_marker_tooltip.png'),fullPage:true});
  await page.locator('button[data-testid^="beat-"]').first().click();await expect(page.getByTestId('single-prediction')).toBeVisible();
  const marks=await(await request.get('/api/ecg/annotations?record_id=200&start_sec=6&duration_sec=10&task=nv')).json();const sample=marks.annotations.find((r:any)=>r.within_task).annotation_sample;
  result.sample={record_id:'200',sample,time_seconds:sample/360};
  for(const endpoint of ['window','single','compare']){
    const times=[];
    for(let i=0;i<5;i++){const start=performance.now();const response=endpoint==='window'?await request.get('/api/ecg/window?record_id=200&start_sec=6&duration_sec=10&lead_name=MLII'):await request.post(`/api/inference/${endpoint==='single'?'beat':'compare'}`,{data:{record_id:'200',annotation_sample:sample,task:'nv',...(endpoint==='single'?{model_id:'cnn_1d'}:{})}});expect(response.ok()).toBeTruthy();times.push(performance.now()-start);}
    result.api[endpoint]={samples_ms:times,mean_ms:times.reduce((a,b)=>a+b,0)/times.length};
  }
  await page.getByRole('button',{name:'比较三个模型',exact:true}).click();await page.locator('.comparison-table summary').click();await expect(page.getByRole('cell',{name:'Logistic Regression',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'播放历史片段'}).click();await expect(page.getByRole('button',{name:'暂停'})).toBeVisible();await page.getByRole('button',{name:'暂停'}).click();
  result.errors=errors;expect(errors).toEqual([]);
  fs.writeFileSync(path.resolve(__dirname,'../../docs/phase5_performance_production.json'),JSON.stringify(result,null,2));
});
