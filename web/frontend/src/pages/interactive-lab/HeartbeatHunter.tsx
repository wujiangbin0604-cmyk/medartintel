import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, history as navigateHistory, useLocation } from '@umijs/max';
import { Alert, App, Button, Collapse, Modal, Progress, Select, Slider, Switch, Tag, Tooltip } from 'antd';
import { AimOutlined, ArrowRightOutlined, CheckCircleFilled, ClockCircleOutlined, CloseCircleFilled, ExpandOutlined, FireFilled, FlagOutlined, InfoCircleOutlined, LineChartOutlined, MutedOutlined, PauseOutlined, PlayCircleOutlined, QuestionCircleOutlined, ReloadOutlined, RobotOutlined, SendOutlined, SoundOutlined, ThunderboltOutlined, TrophyOutlined } from '@ant-design/icons';
import { AnimatePresence, motion } from 'motion/react';
import { useMotionSettings } from '@/utils/motion';
import { api } from '@/services/api';
import type { Prediction } from '@/types/ecg';
import HeartbeatGameChart from './HeartbeatGameChart';
import Gamepad from '@/components/GamepadIcon';
import { browserStorage } from '@/utils/browserStorage';
import { gameAnalysisUrl, TUTORIAL_KEY } from '@/components/onboarding/state';
import { gameApi, names, playerId, type Difficulty, type GameConfig, type GameSession, type GameStatus, type History } from './gameApi';
import './index.less';

const ACTIVE_KEY = 'hunter.active.v1';
const secondsText = (n: number) => { const total=Math.max(0,Math.ceil(n));return `${String(Math.floor(total/60)).padStart(2,'0')}:${String(total%60).padStart(2,'0')}`; };
function useSound() {
  const [enabled, setEnabled] = useState(false), [volume, setVolume] = useState(25);
  const context = useRef<AudioContext>();
  useEffect(() => () => { void context.current?.close(); }, []);
  const play = useCallback((kind: 'select' | 'correct' | 'wrong' | 'finish') => {
    if (!enabled) return;
    const ctx = context.current || (context.current = new AudioContext());
    void ctx.resume();
    const oscillator = ctx.createOscillator(), gain = ctx.createGain();
    oscillator.type = 'sine'; oscillator.frequency.setValueAtTime(kind === 'wrong' ? 220 : kind === 'select' ? 520 : 740, ctx.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(kind === 'wrong' ? 150 : 1000, ctx.currentTime + .12);
    gain.gain.setValueAtTime(volume/100*.12, ctx.currentTime); gain.gain.exponentialRampToValueAtTime(.001, ctx.currentTime+.18);
    oscillator.connect(gain); gain.connect(ctx.destination); oscillator.start(); oscillator.stop(ctx.currentTime+.2);
    oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); };
  }, [enabled, volume]);
  return { enabled, setEnabled, volume, setVolume, play };
}
function AnimatedScore({ value }: { value: number }) {
  const { reduced } = useMotionSettings(); const [shown, setShown] = useState(value);
  const last = useRef(value);
  useEffect(() => { if (reduced) { setShown(value); last.current=value; return; } const start=performance.now(), from=last.current; let frame=0; const tick=(now:number)=>{const p=Math.min(1,(now-start)/450);setShown(Math.round(from+(value-from)*(1-(1-p)**3)));if(p<1)frame=requestAnimationFrame(tick);};frame=requestAnimationFrame(tick);last.current=value;return()=>cancelAnimationFrame(frame); }, [value,reduced]);
  return <strong data-testid="game-score">{shown}</strong>;
}

export default function HeartbeatHunter() {
  const location = useLocation();
  const [fromWelcome] = useState(() => new URLSearchParams(location.search).get('welcome') === '1');
  const [firstTutorial] = useState(() => !browserStorage.getItem(TUTORIAL_KEY));
  const { message } = App.useApp(), { reduced } = useMotionSettings(); const sound = useSound();
  const [player] = useState(playerId), [difficulty, setDifficulty] = useState<Difficulty>('beginner');
  const [config, setConfig] = useState<GameConfig>(), [history, setHistory] = useState<History>();
  const [configRetry, setConfigRetry] = useState(0);
  const [session, setSession] = useState<GameSession | null>(null), [status, setStatus] = useState<GameStatus>('idle');
  const [selections, setSelections] = useState<number[]>([]), [remaining, setRemaining] = useState(120), [revealed, setRevealed] = useState(0);
  const [error, setError] = useState(''), [tutorial, setTutorial] = useState(firstTutorial), [resultOpen, setResultOpen] = useState(false);
  const [review, setReview] = useState<number>(), [models, setModels] = useState<Prediction[]>([]), [aiBusy, setAiBusy] = useState(false);
  const busy = useRef(false), selectionBusy = useRef(false), action = useRef<AbortController>();
  const mounted = useRef(true), selectionQueue = useRef(Promise.resolve());
  const clock = useRef({ at: performance.now(), remaining: 120 });
  const latest = useRef({ session, selections, status }); latest.current = { session, selections, status };
  const chartShell = useRef<HTMLDivElement>(null);
  const accept = useCallback((s: GameSession) => {
    clock.current = { at: performance.now(), remaining: s.remaining_seconds };
    setSession(s); setSelections(s.samples); setRemaining(s.remaining_seconds); setDifficulty(s.difficulty);
    setStatus(s.status === 'abandoned' ? 'idle' : s.status);
    if (s.result) { setRevealed(s.result.events.length); setReview(s.result.answers.find(a=>a.label==='V')?.sample); }
  }, []);
  const refreshHistory = useCallback(() => { gameApi.history(player).then(h => { if (mounted.current) setHistory(h); }).catch(() => {}); }, [player]);
  useEffect(() => {
    mounted.current = true; const controller = new AbortController();
    Promise.all([gameApi.config(controller.signal), gameApi.history(player, controller.signal)]).then(([c,h])=>{if(c.level_count<1)throw new Error('暂无可用关卡');setConfig(c);setHistory(h);}).catch(e=>{if(!controller.signal.aborted){setConfig(undefined);setError(`游戏暂时不可用：${e.message}`);}});
    const active = browserStorage.getItem(ACTIVE_KEY);
    if (fromWelcome) { browserStorage.removeItem(ACTIVE_KEY); navigateHistory.replace(location.pathname); }
    if (active && !fromWelcome && !firstTutorial) gameApi.session(active,controller.signal).then(s=>{if(!controller.signal.aborted)accept(s);}).catch(()=>browserStorage.removeItem(ACTIVE_KEY));
    return () => { mounted.current=false; controller.abort(); action.current?.abort(); };
  }, [player, accept, configRetry]);
  // Reconcile the authoritative server clock after tab suspension or a browser refresh.
  useEffect(() => { const sync=()=>{const current=latest.current;if(document.visibilityState==='visible' && current.session && ['playing','paused'].includes(current.status)) gameApi.session(current.session.session_id).then(s=>{if(mounted.current&&!busy.current)accept(s);}).catch(()=>{});};document.addEventListener('visibilitychange',sync);return()=>document.removeEventListener('visibilitychange',sync);}, [accept]);
  const start = async (next = false) => {
    if (busy.current || tutorial || !config?.level_count) return; busy.current=true; action.current?.abort(); const controller=new AbortController();action.current=controller;
    setError('');setStatus('loading');setResultOpen(false);setModels([]);setReview(undefined);setRevealed(0);
    try {
      const previous=latest.current.session;
      if (!next && previous && ['playing','paused'].includes(previous.status)) await gameApi.control(previous.session_id,'abandon',1,controller.signal);
      const s=await gameApi.start(player,difficulty,next?previous?.session_id:undefined,controller.signal);
      if(!mounted.current)return;browserStorage.setItem(ACTIVE_KEY,s.session_id);accept(s);
    } catch(e) {if(mounted.current&&!controller.signal.aborted){setError((e as Error).message);setStatus('error');}}
    finally {busy.current=false;}
  };
  const toggle = useCallback((sample: number) => {
    const current=latest.current; const s=current.session;
    if (!s || current.status!=='playing' || busy.current || selectionBusy.current) return;
    const tolerance=Math.round(s.sampling_rate*(config?.scoring.tolerance_seconds ?? .1));
    const existing=current.selections.find(x=>Math.abs(x-sample)<=tolerance);
    const next=existing!==undefined?current.selections.filter(x=>x!==existing):[...current.selections,sample].sort((a,b)=>a-b);
    // Keep the selection checkpoint ordered so a slower older request cannot overwrite it.
    selectionBusy.current=true;
    selectionQueue.current=selectionQueue.current.then(async()=>{
      try{const response=await gameApi.select(s.session_id,next);if(mounted.current){setSelections(response.samples);latest.current.selections=response.samples;sound.play('select');}}
      catch(e){if(mounted.current)setError((e as Error).message);}
      finally{selectionBusy.current=false;}
    });
  }, [config, sound.play]);
  const clear = async () => {if(!session||busy.current||selectionBusy.current)return;selectionBusy.current=true;try{await gameApi.select(session.session_id,[]);setSelections([]);latest.current.selections=[];}catch(e){setError((e as Error).message);}finally{selectionBusy.current=false;}};
  const submit = useCallback(async () => {
    const current=latest.current;if(!current.session||current.status!=='playing'||busy.current)return;
    busy.current=true;setStatus('submitting');setError('');
    try { await selectionQueue.current;const s=await gameApi.submit(current.session.session_id,latest.current.selections);if(!mounted.current)return;
      setSession({...current.session,...s});setRemaining(s.remaining_seconds);setStatus('revealing');setRevealed(0);setModels([]);setReview(s.result?.answers.find(a=>a.label==='V')?.sample);refreshHistory();
    }catch(e){if(mounted.current){setError((e as Error).message);setStatus('playing');clock.current={at:performance.now(),remaining:3};}}
    finally{busy.current=false;}
  }, [refreshHistory]);
  useEffect(() => { if(status!=='playing')return;const update=()=>{const left=Math.max(0,clock.current.remaining-(performance.now()-clock.current.at)/1000);setRemaining(left);if(left===0)void submit();};update();const timer=window.setInterval(update,150);return()=>clearInterval(timer);}, [status,submit]);
  useEffect(() => {
    if(status!=='revealing'||!session?.result)return;const count=session.result.events.length;
    const timer=window.setTimeout(()=>{if(revealed<count){setRevealed(v=>v+1);sound.play(session.result!.events[revealed].correct?'correct':'wrong');}else{setStatus('finished');sound.play('finish');}},reduced?0:revealed<count?500:450);
    return()=>clearTimeout(timer);
  }, [status,session?.result,revealed,reduced,sound.play]);
  const control = async (kind:'pause'|'resume'|'speed',speed=1) => {if(!session||busy.current)return;busy.current=true;try{const patch=await gameApi.control(session.session_id,kind,speed);accept({...session,...patch});}catch(e){setError((e as Error).message);}finally{busy.current=false;}};
  const compare = async () => {if(!session||review===undefined)return;setAiBusy(true);setModels([]);try{const response=await api.compare(session.record_id,review,'nv');if(mounted.current)setModels(response.models);}catch(e){message.error((e as Error).message);}finally{if(mounted.current)setAiBusy(false);}};
  const active=['playing','paused','submitting','revealing'].includes(status), finished=status==='finished';
  const result=session?.result, events=result?.events.slice(0,revealed)||[], currentEvent=events[events.length-1];
  const combo=finished?result?.max_combo||0:currentEvent?.combo||0;
  const score=finished?result?.score||0:events.reduce((total,e)=>total+e.delta,0);
  const reviewed=result?.answers.find(a=>a.sample===review);
  const spec=config?.difficulties[difficulty];
  const closeTutorial = () => { browserStorage.setItem(TUTORIAL_KEY,'completed'); setTutorial(false); };
  const answerSection = useRef<HTMLDivElement>(null);
  const goToAI = () => { if(session && review!==undefined) navigateHistory.push(gameAnalysisUrl(session.record_id,review,session.sampling_rate)); };
  const exploreWorkspace = () => navigateHistory.push(session&&review!==undefined?gameAnalysisUrl(session.record_id,review,session.sampling_rate,false):'/ai-detection');
  return <main className={`hunter-page ${reduced?'hunter-reduced':''}`}>
    <motion.div className="hunter-heading" initial={{opacity:0,y:reduced?0:8}} animate={{opacity:1,y:0}}><div><h1><Gamepad /> Heartbeat Hunter <span>· 心跳猎人</span><Tag color="blue">心电识别闯关游戏</Tag></h1><p>在真实 ECG 心电波形中寻找异常心拍。本次目标：AAMI V 组。</p></div><div className="hunter-heading-actions"><Link to="/interactive-lab">互动实验室</Link><Button icon={<QuestionCircleOutlined/>} onClick={()=>setTutorial(true)}>玩法说明</Button></div></motion.div>
    {error && <Alert type="error" title={error} showIcon closable onClose={()=>setError('')} action={!config?<div><Button onClick={()=>{setError('');setConfigRetry(v=>v+1);}}>重试连接</Button><Link to="/dashboard"><Button type="link">返回首页</Button></Link></div>:status==='error'?<Button onClick={()=>start()}>重新加载</Button>:undefined}/>}
    <div className="hunter-board"><div className="hunter-main">
      <section className="hunter-hud" aria-label="游戏状态">
        <div className="hunter-difficulty"><span className="hunter-hud-icon"><FlagOutlined/></span><div><b>Level {session?.round||1}</b><Select aria-label="游戏难度" value={difficulty} disabled={active||status==='loading'} onChange={d=>{setDifficulty(d);if(finished){setSession(null);setSelections([]);setStatus('idle');browserStorage.removeItem(ACTIVE_KEY);}setRemaining(config?.difficulties[d].seconds||120);}} options={(Object.keys(names) as Difficulty[]).map((key,i)=>({value:key,label:`${'★'.repeat(i+1)} ${names[key]}`}))}/><small>{difficulty==='beginner'?'候选心拍辅助 · 静态观察':difficulty==='standard'?'自主定位 · 缩放与平移':'历史信号回放 · 限时观察'}</small></div></div>
        <div className="hunter-hud-stat"><TrophyOutlined/><div><span>Score · 本关得分</span><AnimatedScore value={score}/></div></div>
        <div className={`hunter-hud-stat hunter-combo ${combo>=2?'is-combo':''}`}><ThunderboltOutlined/><div><span>Combo · 连击</span><motion.strong key={combo} animate={reduced?{}:{scale:[1.12,1]}}>×{combo}</motion.strong></div>{combo>=2&&<FireFilled className="hunter-fire"/>}</div>
        <div className={`hunter-hud-stat ${remaining<=10&&status==='playing'?'hunter-urgent':''}`}><ClockCircleOutlined/><div><span>Time · 剩余时间</span><strong data-testid="countdown">{secondsText(remaining)}</strong></div><Progress type="circle" percent={remaining/(spec?.seconds||120)*100} size={27} showInfo={false} strokeColor={remaining<=10?'#f59e0b':'#06b6d4'}/></div>
      </section>
      <section className="hunter-panel hunter-chart-card" ref={chartShell}>
        <div className="hunter-panel-heading"><h2><PlayCircleOutlined/> 心电图挑战</h2><span>{status==='playing'?'点击疑似 V 组心拍，可再次点击取消':status==='paused'?'游戏已暂停，恢复后继续选择':finished?'答案已揭晓 · 点击波形查看局部解析':'观察波形形态，找出 V 组心拍'}</span><div className="hunter-chart-tools"><Tag color={status==='playing'?'processing':finished?'success':'default'}>{({idle:'准备就绪',loading:'读取真实数据',playing:'挑战进行中',paused:'已暂停',submitting:'正在判分',revealing:'逐拍揭晓',finished:'本关已完成',error:'加载失败'})[status]}</Tag><Tooltip title={difficulty==='beginner'?'新手模式支持服务端暂停':'标准 / 挑战模式禁止暂停，计时由服务器管理'}><Button size="small" aria-label={status==='paused'?'恢复游戏':'暂停游戏'} icon={status==='paused'?<PlayCircleOutlined/>:<PauseOutlined/>} disabled={!['playing','paused'].includes(status)||difficulty!=='beginner'} onClick={()=>control(status==='paused'?'resume':'pause')}/></Tooltip><Select size="small" aria-label="回放速度" value={session?.speed||1} disabled={status!=='playing'||difficulty!=='challenge'} options={[.5,1,1.5,2].map(v=>({value:v,label:`${v}×`}))} onChange={v=>control('speed',v)}/><Button aria-label="全屏波形" size="small" icon={<ExpandOutlined/>} onClick={()=>chartShell.current?.requestFullscreen().catch(()=>message.info('当前浏览器不支持全屏'))}/></div></div>
        <div className="hunter-source"><span className="hunter-live-dot"/> {session?`MIT-BIH · Record ${session.record_id} · ${session.lead_name} · ${session.sampling_rate} Hz · 原始 mV`:'MIT-BIH Arrhythmia Database · 真实专家标注'}<span>历史信号游戏 · 非实时监测</span></div>
        <HeartbeatGameChart session={session} selections={selections} status={status} onSelect={toggle} revealed={revealed} onReview={s=>{setReview(s);setModels([]);}}/>
        <AnimatePresence>{status==='revealing'&&currentEvent&&<motion.div key={revealed} className={`hunter-feedback ${currentEvent.correct?'correct':'wrong'}`} initial={{opacity:0,y:reduced?0:8}} animate={{opacity:1,y:0}} exit={{opacity:0}} aria-live="polite">{currentEvent.correct?<CheckCircleFilled/>:<CloseCircleFilled/>} {currentEvent.delta>0?'+':''}{currentEvent.delta} {combo>=2&&<span><FireFilled/> Combo ×{combo}</span>}</motion.div>}</AnimatePresence>
        <div className="hunter-legend"><span><i className="candidate"/> 可选心拍（新手）</span><span><i className="selected"/> 已选择</span><span><i className="correct"/> 正确选择</span><span><i className="target"/> 专家 V 组（结算后）</span><span><i className="scan"/> 历史回放进度</span></div>
        <div className="hunter-game-actions"><Button aria-label={finished||active?'重新挑战':'开始挑战'} size="large" type="primary" icon={finished||active?<ReloadOutlined/>:<PlayCircleOutlined/>} loading={status==='loading'} disabled={status==='submitting'||status==='revealing'||tutorial||!config?.level_count} onClick={()=>start()}>{finished||active?'重新挑战':'开始挑战'}</Button><Button aria-label="提交答案" size="large" icon={<SendOutlined/>} loading={status==='submitting'} disabled={status!=='playing'} onClick={()=>submit()}>提交答案</Button><Button aria-label="清除选择" size="large" icon={<ReloadOutlined/>} disabled={status!=='playing'||!selections.length} onClick={clear}>清除选择</Button><Button aria-label="下一关" size="large" icon={<ArrowRightOutlined/>} disabled={!finished||(session?.round||1)>=5} onClick={()=>start(true)}>下一关</Button></div>
        {(difficulty==='beginner'&&session?.candidate_samples.length)&&<div className="hunter-candidate-list" aria-label="候选心拍快捷选择">{session.candidate_samples.map((s,i)=><Button key={s} size="small" aria-label={`候选心拍 ${i+1}`} aria-pressed={selections.includes(s)} type={selections.includes(s)?'primary':'default'} disabled={status!=='playing'} onClick={()=>toggle(s)}>{((s-session.start_sample)/session.sampling_rate).toFixed(2)} s</Button>)}</div>}
        <div className="hunter-selection-list" aria-live="polite">已选 {selections.length} 个{selections.length>0?'：点击标签可移除并重新定位。':' · 也可以不选择任何位置直接提交。'}{selections.map(s=><Tag key={s} closable={status==='playing'} onClose={e=>{e.preventDefault();toggle(s);}}>{((s-(session?.start_sample||0))/(session?.sampling_rate||360)).toFixed(2)} s</Tag>)}</div>
      </section>
    </div><aside className="hunter-rail">
      <section className="hunter-panel hunter-mission"><h2><AimOutlined/> 本关任务</h2><div>识别目标 <Tag color="magenta">室性异位心拍 · V 组</Tag></div><p>找出真实 ECG 中全部 AAMI V 组心拍。</p><p>比较形态，定位疑似目标。提交后揭晓专家类别与数量。</p><div className="hunter-mission-foot"><InfoCircleOutlined/> V 组包含 V、E 原始标注</div></section>
      <section className="hunter-panel"><h2><FlagOutlined/> 游戏进度</h2><div className="hunter-rounds">{Array.from({length:5},(_,i)=><span key={i} className={i+1<(session?.round||1)||finished&&i+1===session?.round?'done':i+1===(session?.round||1)?'current':''}>{i+1<(session?.round||1)?'✓':i+1}</span>)}</div><Progress percent={((session?.round||1)-1+(finished?1:0))/5*100} size="small" strokeColor="#1677ff"/><small>第 {session?.round||1} / 5 关 · 累计 {session?.total_score||0} 分</small></section>
      <section className="hunter-panel"><h2><LineChartOutlined/> 实时统计</h2><div className="hunter-stats-grid"><div><AimOutlined/><small>已选择</small><b>{selections.length}<em> 个</em></b></div><div><FireFilled/><small>{finished?'最高连击':'当前连击'}</small><b>×{combo}</b></div><div><TrophyOutlined/><small>个人最佳</small><b>{history?.best[difficulty]||0}</b></div></div><small className="hunter-note">{finished?`发现 V 组 ${result?.correct} 个 · 漏选 ${result?.missed} 个`:'发现数量与分数将在提交后统一揭晓'}</small></section>
      <section className="hunter-panel hunter-hints"><h2><QuestionCircleOutlined/> 观察提示</h2><Collapse ghost size="small" items={[{key:'1',label:'先观察形态，再判断类别',children:'对比相邻心拍的 QRS 波群形态与时序。形态差异是观察线索，最终答案以专家标注为准。'},{key:'2',label:'N 组也可能有较宽的 QRS',children:'N 组包括正常心拍、束支传导阻滞及部分逸搏。不要仅凭 QRS 宽度判断 V 组。'},{key:'3',label:'如何准确选择心拍',children:`新手点击候选标记。标准/挑战模式点击波形；匹配容差为 ±${config?.scoring.tolerance_seconds||.1} 秒。同一专家心拍只评分一次。`} ]}/></section>
      <section className="hunter-panel hunter-sound"><div><h2>{sound.enabled?<SoundOutlined/>:<MutedOutlined/>} 游戏音效</h2><Switch aria-label="游戏音效" checked={sound.enabled} onChange={sound.setEnabled} size="small"/></div>{sound.enabled&&<Slider ariaLabelForHandle="音量" min={0} max={100} value={sound.volume} onChange={sound.setVolume}/>}<small>原创合成提示音 · 默认静音</small></section>
    </aside></div>
    <section className="hunter-panel hunter-learning" ref={answerSection}><h2><CheckCircleFilled/> 本轮结果与学习反馈 {finished&&<Button size="small" onClick={()=>setResultOpen(true)}>查看成绩单</Button>}</h2>
      {result&&['revealing','finished'].includes(status)?<div className="hunter-result-grid"><div><div className={`hunter-result-banner ${result.incorrect||result.missed?'partial':''}`}><CheckCircleFilled/><b>{status==='revealing'?'正在揭晓答案…':result.grade}</b><span>{finished?`${result.score>0?'+':''}${result.score} 分`:'逐拍计分'}</span>{combo>=2&&<Tag color="volcano"><FireFilled/> 连击 ×{combo}</Tag>}</div><div className="hunter-result-metrics"><span>正确选择<b>{result.correct}</b></span><span>错误选择<b>{result.incorrect}</b></span><span>漏选心拍<b>{result.missed}</b></span><span>Precision<b>{(result.precision*100).toFixed(0)}%</b></span><span>Recall<b>{(result.recall*100).toFixed(0)}%</b></span></div><p className="hunter-note">连击奖励 +{result.combo_bonus} · 时间奖励 +{result.time_bonus} · 用时 {result.elapsed_seconds.toFixed(1)} s{result.timed_out?' · 到时自动结算':''}</p><Button onClick={()=>start()} icon={<ReloadOutlined/>}>{session?.round===5?'五关完成，再来一轮':'重新挑战本难度'}</Button></div><div className="hunter-explanation"><div className="hunter-local-beat">{reviewed&&session&&<svg viewBox="0 0 200 130" role="img" aria-label="选中心拍真实局部波形"><polyline fill="none" stroke="#1677ff" strokeWidth="2" points={(()=>{const start=Math.max(0,reviewed.sample-session.start_sample-108),clip=session.signal.slice(start,Math.min(session.signal.length,start+253)),min=Math.min(...clip),range=Math.max(.1,Math.max(...clip)-min);return clip.map((y,i)=>`${i/(clip.length-1)*190+5},${115-(y-min)/range*100}`).join(' ');})()}/></svg>}<Tag color={reviewed?.label==='V'?'magenta':'blue'}>{reviewed?.label||'—'}</Tag></div><div><h3><RobotOutlined/> 专家标签解析：{reviewed?.meaning}</h3><p>原始标注 {reviewed?.symbol} → AAMI {reviewed?.label} 组。{reviewed?.label==='V'?'本拍属于本关目标。':'本拍不属于本关目标；N 组并不代表所有形态均正常。'}选择下方心拍可逐一复盘。</p><div className="hunter-answer-list">{finished&&result.answers.map(a=><Button size="small" key={a.sample} type={review===a.sample?'primary':'default'} aria-label={`专家心拍 ${a.sample} ${a.label}`} onClick={()=>{setReview(a.sample);setModels([]);}}>{((a.sample-session!.start_sample)/session!.sampling_rate).toFixed(2)} s · {a.symbol}/{a.label}</Button>)}</div><div className="hunter-teaching-actions"><Button type="primary" icon={<RobotOutlined/>} disabled={!finished||!reviewed} loading={aiBusy} onClick={compare}>本页对比三个模型</Button><Link to={`/ai-detection?record=${session?.record_id}&task=nv&time=${(review||0)/(session?.sampling_rate||360)}`}><Button disabled={!finished||!reviewed}>在 ECG 工作台分析 <ArrowRightOutlined/></Button></Link></div>{models.length>0&&<div className="hunter-model-results">{models.map(m=><Tag key={m.model_id} color="blue">{m.model_id}：{m.predicted_class}</Tag>)}<small>模型预测仅供对比，不参与游戏判分。</small></div>}</div></div></div>:<div className="hunter-learning-empty"><div><AimOutlined/><b>先做出你的判断，再与专家一起复盘。</b><p>提交后展示真实标签、局部心拍和逐项得分，还可以对比已有 AI 模型。</p></div><span>观察 → 选择 → 揭晓 → 学习</span></div>}
      {finished&&<div className="hunter-postgame-actions" aria-label="游戏结束后继续探索"><Button onClick={()=>start()} aria-label="再来一次" icon={<ReloadOutlined/>}>再来一次</Button><Button onClick={()=>answerSection.current?.scrollIntoView({behavior:reduced?'auto':'smooth',block:'start'})}>查看本轮答案</Button><Button type="primary" onClick={goToAI} disabled={review===undefined} aria-label="看看 AI 如何判断" icon={<RobotOutlined/>}>看看 AI 如何判断</Button><Button onClick={exploreWorkspace}>探索 ECG 分析平台 <ArrowRightOutlined/></Button><small className="postgame-note">在检测页重新调用真实模型</small></div>}
    </section>
    <section className="hunter-history"><h3>最近挑战记录</h3><div>{history?.records.slice(0,5).map(r=><span key={r.session_id}>{names[r.difficulty]} · 第 {r.round} 关 <b>{r.score} 分</b><small>{new Date(r.completed_at*1000).toLocaleString('zh-CN')}</small></span>)}{!history?.records.length&&<p>完成首轮挑战后，成绩会保存在本地课程环境。</p>}</div></section>
    <p className="hunter-note hunter-disclaimer">V 指 MIT-BIH AAMI V 组，不等同于所有异常心律。积分仅用于娱乐与学习。<a href="https://physionet.org/content/mitdb/1.0.0/" target="_blank" rel="noreferrer">数据来源：PhysioNet MIT-BIH</a></p>
    <Modal title="心跳猎人 · 玩法说明" open={tutorial} onCancel={closeTutorial} footer={<Button type="primary" onClick={closeTutorial}>我已了解，进入准备页</Button>}><ol className="hunter-tutorial"><li><b>观察：</b>选择难度，观察真实 MIT-BIH 波形。首次建议新手模式，候选标记不显示专家类别。</li><li><b>选择：</b>点击疑似 V 组心拍，再次点击可取消；提交后才揭晓专家答案和积分。</li><li><b>学习：</b>完成后逐拍复盘，或进入 AI 检测工作台，让现有模型重新判断。</li></ol><Alert type="info" showIcon title="阅读教程不会开始计时" description="关闭教程后，仍需主动点击“开始挑战”才会创建游戏并开始倒计时。"/><p className="hunter-note">V 指 AAMI V 组，游戏积分仅供娱乐学习，不表示医学诊断能力。</p></Modal>
    <Modal title="本关成绩单" open={resultOpen} onCancel={()=>setResultOpen(false)} footer={<Button type="primary" onClick={()=>setResultOpen(false)}>继续复盘</Button>}><div className="hunter-final"><TrophyOutlined/><h2>{result?.grade}</h2><strong>{result?.score} 分</strong><p>正确 {result?.correct} · 误选 {result?.incorrect} · 漏选 {result?.missed}</p><p>Precision {((result?.precision||0)*100).toFixed(1)}% · Recall {((result?.recall||0)*100).toFixed(1)}%</p><p>连击奖励 +{result?.combo_bonus} · 时间奖励 +{result?.time_bonus}</p><small>本地匿名玩家 · 第 {session?.round} / 5 关 · 娱乐学习积分</small></div></Modal>
  </main>;
}
