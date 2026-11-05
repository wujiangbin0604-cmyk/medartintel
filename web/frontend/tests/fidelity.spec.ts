import {test,expect} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs';
const stage=process.env.FIDELITY_STAGE||'before';
test.skip(!process.env.FIDELITY_STAGE,'Use explicit FIDELITY_STAGE to preserve before/after evidence.');
const out=path.resolve(__dirname,'../../docs/visual_fidelity',stage);fs.mkdirSync(out,{recursive:true});
for(const [width,height] of [[1672,941],[1920,1080],[1440,900],[1366,768],[745,671]])test(`fidelity ${stage} ${width}x${height}`,async({page})=>{
 test.setTimeout(150000);await page.setViewportSize({width,height});const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 async function shot(name:string){await page.waitForLoadState('networkidle');await page.waitForTimeout(850);await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(200);await page.screenshot({path:path.join(out,`${name}_${width}x${height}.png`)});await page.screenshot({path:path.join(out,`${name}_${width}x${height}_full.png`),fullPage:true});if(stage==='after')expect(await page.evaluate(()=>document.body.scrollWidth<=innerWidth+1)).toBe(true);}
 await page.goto('/dashboard');await expect(page.getByRole('heading',{name:'项目总览',exact:true})).toBeVisible();await shot('dashboard');
 await page.goto('/ai-detection');await expect(page.getByRole('heading',{name:'ECG 心拍分析',exact:true})).toBeVisible();await page.locator('button[data-testid^="beat-"]').first().click();await expect(page.getByTestId('single-prediction')).toBeVisible();await shot('ecg');
 await page.getByRole('button',{name:'比较三个模型',exact:true}).click();await expect(page.locator('.model-result-card .model-prediction')).toHaveCount(3);await shot('comparison');
 await page.goto('/ai-inference');await expect(page.getByRole('heading',{name:'AI 智能检测',exact:true})).toBeVisible();await expect(page.getByTestId('single-prediction')).toBeVisible();await page.getByRole('button',{name:'比较三个模型',exact:true}).click();await expect(page.locator('.model-result-card .model-prediction')).toHaveCount(3);await shot('ai');
 await page.goto('/experiments');await expect(page.getByRole('heading',{name:'AI 模型实验中心',exact:true})).toBeVisible();await shot('experiments');
 expect(errors).toEqual([]);fs.writeFileSync(path.join(out,`browser_${width}.json`),JSON.stringify({width,height,errors},null,2));
});
