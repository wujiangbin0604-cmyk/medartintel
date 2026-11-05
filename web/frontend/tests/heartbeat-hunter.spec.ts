import { test, expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const root=path.resolve(__dirname,'../../..');
const screenshots=path.resolve(root,'web/docs/screenshots/heartbeat_hunter');
fs.mkdirSync(screenshots,{recursive:true});
const game='/interactive-lab/heartbeat-hunter';
const api='/api/games/heartbeat-hunter';
test.beforeEach(async({page})=>{await page.addInitScript(()=>{localStorage.setItem('ecg_ai_hunter_tutorial_v1','completed');});});
async function shot(page:Page,name:string){if(name!=='combo')await page.waitForTimeout(700);await page.screenshot({path:path.join(screenshots,name+'.png'),fullPage:true});}
async function open(page:Page){await page.goto(game);await expect(page.getByRole('button',{name:'开始挑战',exact:true})).toBeEnabled();}
async function start(page:Page){await page.getByRole('button',{name:'开始挑战',exact:true}).click();await expect(page.getByText('挑战进行中',{exact:true})).toBeVisible();}
async function difficulty(page:Page,name:string){await page.getByRole('combobox',{name:'游戏难度'}).click();await page.locator('.ant-select-item-option-content').filter({hasText:name}).click();}
async function sid(page:Page){return (await page.evaluate(()=>localStorage.getItem('hunter.active.v1')))!;}
function privateLevel(s:any){const index=JSON.parse(fs.readFileSync(path.join(root,'web/backend/game_data/heartbeat_levels.json'),'utf8'));return index.levels.find((l:any)=>l.record_id===s.record_id&&l.start_sample===s.start_sample&&l.difficulty===s.difficulty);}
async function session(page:Page){return (await page.request.get(api+'/session/'+await sid(page))).json();}
async function selectTargets(page:Page,s:any,includeWrong=false){
  const level=privateLevel(s);
  const wanted=level.answers.filter((a:any)=>a.label==='V');
  if(includeWrong)wanted.push(level.answers.find((a:any)=>a.label==='N'));
  for(const beat of wanted){const i=s.candidate_samples.indexOf(beat.sample);await page.getByRole('button',{name:`候选心拍 ${i+1}`,exact:true}).click();await expect(page.getByRole('button',{name:`候选心拍 ${i+1}`,exact:true})).toHaveAttribute('aria-pressed','true');}
  return level;
}
function shortenDeadline(id:string,remaining:number){
 const script="import sqlite3,json,time,sys; db=sqlite3.connect(sys.argv[1]); row=db.execute('SELECT data FROM hunter_sessions WHERE id=?',(sys.argv[2],)).fetchone(); s=json.loads(row[0]); s['deadline']=time.time()+float(sys.argv[3]); db.execute('UPDATE hunter_sessions SET data=? WHERE id=?',(json.dumps(s),sys.argv[2])); db.commit(); db.close()";
 execFileSync(path.join(root,'.venv/Scripts/python.exe'),['-c',script,path.join(root,'web/runtime/hunter_e2e.sqlite3'),id,String(remaining)]);
}

test('完整新手流程：真实波形、取消、评分、连击、解析、AI、下一关、刷新、历史',async({page})=>{
 await page.setViewportSize({width:1920,height:1080});
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/interactive-lab');await expect(page.getByRole('heading',{name:/心电互动实验室/})).toBeVisible();await shot(page,'lab_1920');
 await page.getByRole('button',{name:/进入心跳猎人/}).click();await expect(page.getByRole('button',{name:'开始挑战',exact:true})).toBeVisible();await shot(page,'ready');
 await start(page);let s=await session(page);for(let attempt=0;attempt<20&&privateLevel(s).answers.filter((a:any)=>a.label==='V').length<2;attempt++){await page.getByRole('button',{name:'重新挑战',exact:true}).click();await expect(page.getByText('挑战进行中',{exact:true})).toBeVisible();s=await session(page);}expect(privateLevel(s).answers.filter((a:any)=>a.label==='V').length).toBeGreaterThan(1);expect(s.signal).toHaveLength(3600);expect(s).not.toHaveProperty('answers');expect(s).not.toHaveProperty('result');await shot(page,'playing');
 const first=page.getByRole('button',{name:'候选心拍 1',exact:true});await first.click();await expect(first).toHaveAttribute('aria-pressed','true');await first.click();await expect(first).toHaveAttribute('aria-pressed','false');
 const level=await selectTargets(page,s);await shot(page,'selected');
 await page.getByRole('button',{name:'暂停游戏',exact:true}).click();await expect(page.getByText('已暂停',{exact:true})).toBeVisible();const left=await page.getByTestId('countdown').innerText();await page.waitForTimeout(1100);expect(await page.getByTestId('countdown').innerText()).toBe(left);
 await page.getByRole('button',{name:'恢复游戏',exact:true}).click();
 await page.getByRole('button',{name:'提交答案',exact:true}).click();
 if(level.answers.filter((a:any)=>a.label==='V').length>1){await expect(page.locator('.hunter-feedback').filter({hasText:'Combo'})).toBeVisible();await shot(page,'combo');}
 await expect(page.getByText('本关已完成',{exact:true})).toBeVisible();await shot(page,'answer_reveal');
 const scored=await session(page);expect(scored.result.correct).toBe(level.answers.filter((a:any)=>a.label==='V').length);expect(scored.result.incorrect).toBe(0);expect(scored.result.recall).toBe(1);
 await expect(page.getByTestId('game-score')).toHaveText(String(scored.result.score));
 await page.getByRole('button',{name:'查看成绩单'}).click();await expect(page.getByText('本关成绩单',{exact:true})).toBeVisible();await shot(page,'final');await page.getByRole('button',{name:'继续复盘'}).click();
 await page.getByRole('button',{name:'本页对比三个模型'}).click();await expect(page.locator('.hunter-model-results .ant-tag')).toHaveCount(3);await shot(page,'teaching');
 await page.reload();await expect(page.getByText('本关已完成',{exact:true})).toBeVisible();await expect(page.getByTestId('game-score')).toHaveText(String(scored.result.score));
 await page.getByRole('button',{name:'下一关',exact:true}).click();await expect(page.getByText('挑战进行中',{exact:true})).toBeVisible();const next=await session(page);expect(next.round).toBe(2);expect(next.start_sample!==s.start_sample||next.record_id!==s.record_id).toBeTruthy();
 await page.getByRole('button',{name:'重新挑战',exact:true}).click();await expect(page.getByText('挑战进行中',{exact:true})).toBeVisible();expect((await session(page)).round).toBe(1);
 await page.getByRole('link',{name:'互动实验室',exact:true}).click();await expect(page.locator('.hunter-history-row')).not.toHaveCount(0);expect(errors).toEqual([]);
});

test('真实波形点击、清除选择与误选判分',async({page})=>{
 await open(page);await start(page);const s=await session(page);const level=privateLevel(s);const beat=level.answers.find((a:any)=>a.label==='N');
 const host=page.getByTestId('game-chart'),box=(await host.boundingBox())!;
 const x=60+(box.width-85)*(beat.sample-s.start_sample)/(s.sampling_rate*s.duration);
 await host.click({position:{x,y:box.height/2}});await expect(page.locator('.hunter-selection-list')).toContainText('已选 1 个');
 await page.getByRole('button',{name:'清除选择'}).click();await expect(page.locator('.hunter-selection-list')).toContainText('已选 0 个');
 const index=s.candidate_samples.indexOf(beat.sample);await page.getByRole('button',{name:`候选心拍 ${index+1}`,exact:true}).click();await expect(page.locator('.hunter-selection-list')).toContainText('已选 1 个');
 await page.getByRole('button',{name:'提交答案'}).click();await expect(page.getByText('本关已完成',{exact:true})).toBeVisible();const scored=await session(page);expect(scored.result.incorrect).toBe(1);expect(scored.result.missed).toBeGreaterThan(0);expect(scored.result.score).toBe(-30-20*scored.result.missed);
});

test('标准模式：隐藏候选、倒计时、波形选择、缩放、超时自动结算',async({page})=>{
 await open(page);await difficulty(page,'标准模式');await start(page);const s=await session(page);expect(s.candidate_samples).toEqual([]);expect(s.remaining_seconds).toBeLessThanOrEqual(90);await expect(page.getByRole('button',{name:'暂停游戏'})).toBeDisabled();
 const before=await page.getByTestId('countdown').innerText();await page.waitForTimeout(1200);expect(await page.getByTestId('countdown').innerText()).not.toBe(before);
 const host=page.getByTestId('game-chart');await host.click({position:{x:200,y:140}});await expect(page.locator('.hunter-selection-list')).toContainText('已选 1 个');
 await host.hover();await page.mouse.wheel(0,-200);await page.waitForTimeout(300);
 shortenDeadline(await sid(page),9);await page.reload();await expect(page.locator('.hunter-urgent')).toBeVisible();await shot(page,'last_10_seconds');await expect(page.getByText('本关已完成',{exact:true})).toBeVisible({timeout:20000});expect((await session(page)).result.timed_out).toBeTruthy();
});

test('挑战模式：历史回放滚动、速度控制与页面清理',async({page})=>{
 await open(page);await difficulty(page,'挑战模式');await start(page);const host=page.getByTestId('game-chart');
 await expect(host).toHaveAttribute('data-playback',/\d/);const a=Number(await host.getAttribute('data-playback'));await page.waitForTimeout(1800);const b=Number(await host.getAttribute('data-playback'));expect(b-a).toBeGreaterThan(1);
 await page.getByRole('combobox',{name:'回放速度'}).click();await page.locator('.ant-select-item-option-content').filter({hasText:'2×'}).click();expect((await session(page)).speed).toBe(2);
 await page.waitForTimeout(2500);await shot(page,'challenge_replay');await page.getByRole('link',{name:'互动实验室',exact:true}).click();await expect(page.getByTestId('game-chart')).toHaveCount(0);
 await page.getByRole('button',{name:/进入心跳猎人/}).click();await expect(page.getByText('挑战进行中',{exact:true})).toBeVisible();const restored=await session(page);expect(restored.difficulty).toBe('challenge');
});

test('reduced motion：完整作答、音效设置、网络错误后重试',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});await open(page);await expect(page.locator('.hunter-reduced')).toBeVisible();
 await page.route('**/api/games/heartbeat-hunter/start',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'测试网络中断，请重试'})}));
 await page.getByRole('button',{name:'开始挑战',exact:true}).click();await expect(page.getByText('测试网络中断，请重试')).toBeVisible();await page.unroute('**/api/games/heartbeat-hunter/start');await page.getByRole('button',{name:'重新加载',exact:true}).click();await expect(page.getByText('挑战进行中',{exact:true})).toBeVisible();
 await expect(page.locator('.hunter-scan')).toBeHidden();await page.getByRole('switch',{name:'游戏音效'}).click();await expect(page.getByRole('slider',{name:'音量'})).toBeVisible();await page.getByRole('switch',{name:'游戏音效'}).click();
 await page.getByRole('button',{name:'提交答案',exact:true}).click();await expect(page.getByText('本关已完成',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'提交答案',exact:true})).toBeDisabled();await shot(page,'reduced_motion');
});

for(const [width,height] of [[1920,1080],[1440,900],[1366,768]]){
 test(`视觉与原页面回归 ${width}x${height}`,async({page})=>{
   await page.setViewportSize({width,height});await page.goto('/interactive-lab');await expect(page.getByRole('button',{name:/进入心跳猎人/})).toBeVisible();await shot(page,`lab_${width}x${height}`);await open(page);await shot(page,`ready_${width}x${height}`);await start(page);const s=await session(page);await selectTargets(page,s);await shot(page,`selected_${width}x${height}`);await page.getByRole('button',{name:'提交答案'}).click();await expect(page.getByText('本关已完成',{exact:true})).toBeVisible();await shot(page,`result_${width}x${height}`);
   const layout=await page.evaluate(()=>({width:innerWidth,body:document.documentElement.scrollWidth}));expect(layout.body).toBeLessThanOrEqual(layout.width+1);
   await page.goto('/ai-detection');await expect(page.locator('.waveform-chart canvas').first()).toBeVisible();
 });
}

test('游戏渲染帧间隔采样',async({page})=>{
 await open(page);await difficulty(page,'挑战模式');await start(page);
 const frames=await page.evaluate(()=>new Promise<number[]>(resolve=>{const samples:number[]=[];let last=performance.now();const until=last+3000;const tick=(now:number)=>{samples.push(now-last);last=now;if(now<until)requestAnimationFrame(tick);else resolve(samples);};requestAnimationFrame(tick);}));
 frames.sort((a,b)=>a-b);const report={count:frames.length,median_ms:frames[Math.floor(frames.length*.5)],p95_ms:frames[Math.floor(frames.length*.95)],over_50ms:frames.filter(x=>x>50).length};fs.writeFileSync(path.resolve(root,'web/docs/games/heartbeat_hunter_performance.json'),JSON.stringify(report,null,2));expect(report.count).toBeGreaterThan(30);
});

test('连续十次进出游戏：恢复会话、移除图表、无页面异常',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await open(page);await start(page);const original=await sid(page);
 for(let i=0;i<10;i++){
   await page.getByRole('link',{name:'互动实验室',exact:true}).click();await expect(page.getByTestId('game-chart')).toHaveCount(0);
   await page.getByRole('button',{name:/进入心跳猎人/}).click();await expect(page.getByText('挑战进行中',{exact:true})).toBeVisible();
   expect(await sid(page)).toBe(original);await expect(page.getByTestId('game-chart').locator('canvas')).toHaveCount(1);
 }
 expect(errors).toEqual([]);
});
