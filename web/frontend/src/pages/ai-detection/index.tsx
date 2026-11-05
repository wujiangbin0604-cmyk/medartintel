import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Alert, App, Badge, Button, Card, Divider, Drawer, Empty, InputNumber, Select, Segmented, Skeleton, Space, Statistic, Tabs, Tag, Tooltip, Typography } from 'antd';
import { ApiOutlined, BookOutlined, CheckCircleOutlined, ClockCircleOutlined, DatabaseOutlined, HeartOutlined, InfoCircleOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import ECGWaveformChart from './components/ECGWaveformChart';
import BeatDetail from './components/BeatDetail';
import PredictionComparison from './components/ModelResults';
import {PlaybackClock} from '@/utils/playbackClock';
import {Reveal} from '@/components/Motion';
import {useLocation} from '@umijs/max';
import PlaybackControls from './components/PlaybackControls';
import { api } from '@/services/api';
import { CLASS_COLORS } from '@/design';
import { MODEL_LABELS, type BeatAnnotation, type BeatDetail as BeatData, type ModelId, type ModelStatus, type PlaybackSegment, type Prediction, type RecordSummary, type TaskName, type WaveWindow } from '@/types/ecg';
import './index.less';
import {PanelTitle} from '@/components/MedicalVisuals';
import {DeploymentUnitOutlined,SettingOutlined,PlayCircleOutlined,LineChartOutlined} from '@ant-design/icons';

const taskLabels: Record<TaskName, string[]> = { nv: ['N', 'V'], nsvf: ['N', 'S', 'V', 'F'] };
const taskText: Record<TaskName, string> = { nv: 'N / V 二分类', nsvf: 'N / S / V / F 四分类' };
const BEAT_SAFE_GUARD_SECONDS = 5.3; // 5 s bidirectional-filter guard + 0.3 s pre-beat window.

export default function AIDetectionPage({ presentationStep, demoPaused=false }: { presentationStep?: number; demoPaused?:boolean }) {
  const location=useLocation();const routeParams=new URLSearchParams(location.search);
  const requestedRecord=routeParams.get('record_id')||routeParams.get('record')||'200';
  const sampleParam=routeParams.get('annotation_sample')||routeParams.get('sample');
  const parsedSample=sampleParam===null?NaN:Number(sampleParam);
  const requestedSample=Number.isSafeInteger(parsedSample)&&parsedSample>=0?parsedSample:null;
  const focusMode=location.pathname==='/ai-inference';
  const [classFocus,setClassFocus]=useState('all');
  const [beatFocus,setBeatFocus]=useState(false);
  const [wide,setWide]=useState(window.innerWidth>=1500);
  useEffect(()=>{const media=matchMedia('(min-width:1500px)');const update=()=>setWide(media.matches);media.addEventListener('change',update);return()=>media.removeEventListener('change',update);},[]);
  const [clock]=useState(()=>new PlaybackClock());
  const { message } = App.useApp();
  const [records, setRecords] = useState<RecordSummary[]>([]);
  const [modelStatus, setModelStatus] = useState<Record<TaskName, ModelStatus[]>>({ nv: [], nsvf: [] });
  const [recordId, setRecordId] = useState(requestedRecord);
  const [task, setTask] = useState<TaskName>(routeParams.get('task')==='nsvf'?'nsvf':'nv');
  const [modelId, setModelId] = useState<ModelId>('cnn_1d');
  const [leadName, setLeadName] = useState<string>();
  const [startSec, setStartSec] = useState(routeParams.has('time')?Math.max(0,Number(routeParams.get('time'))-3):(presentationStep?6:0));
  const [durationSec, setDurationSec] = useState(10);
  const [waveform, setWaveform] = useState<WaveWindow | null>(null);
  const [annotations, setAnnotations] = useState<BeatAnnotation[]>([]);
  const [selected, setSelected] = useState<BeatAnnotation | null>(null);
  const [beat, setBeat] = useState<BeatData | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [comparison, setComparison] = useState<{ models: Prediction[]; all_models_agree: boolean; agreement_statement: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [windowLoading, setWindowLoading] = useState(false);
  const [inferenceLoading, setInferenceLoading] = useState(false);
  const [playbackLoading, setPlaybackLoading] = useState(false);
  const [playbackSegment, setPlaybackSegment] = useState<PlaybackSegment | null>(null);
  const [playing, setPlaying] = useState(false);
  const [playhead, setPlayhead] = useState<number | null>(null);
  const [speed, setSpeed] = useState(1);
  const [pinned, setPinned] = useState<BeatData[]>([]);
  const [guideOpen, setGuideOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [initError, setInitError] = useState('');
  const [retry, setRetry] = useState(0);
  const [run, setRun] = useState(0);
  const [activeTab, setActiveTab] = useState('waveform');
  const requestVersion = useRef(0);
  const lastTick = useRef<number | null>(null);
  const actionController = useRef<AbortController | null>(null);
  const actionBusy = useRef(false);

  const currentRecord = records.find((item) => item.record_id === recordId) || null;
  const usableModels = modelStatus[task].filter((item) => item.loaded);
  const recordCanInfer = Boolean(currentRecord?.model_inference_available);
  const matchingPlaybackAnnotation = playbackSegment?.annotations.find((item) => item.annotation_sample === selected?.annotation_sample);
  const currentPrediction = matchingPlaybackAnnotation?.predictions?.find((item) => item.model_id === modelId) || prediction;
  const chartPredictions = useMemo(() => {
    if (playbackSegment) return playbackSegment.annotations.flatMap((item) => item.predictions || []).filter((item) => item.model_id === modelId);
    return prediction ? [prediction] : [];
  }, [playbackSegment, modelId, prediction]);

  useEffect(() => {
    let alive = true;
    Promise.all([api.records(), api.models()]).then(([foundRecords, models]) => {
      if (!alive) return;
      setRecords(foundRecords);
      setModelStatus({ nv: models.tasks.nv.models, nsvf: models.tasks.nsvf.models });
      const initial = foundRecords.find((item) => item.record_id === requestedRecord) || foundRecords[0];
      if (initial) { setRecordId(initial.record_id); setLeadName(initial.signal_names.includes('MLII') ? 'MLII' : initial.signal_names[0]); }
    }).catch((error: Error) => { if (alive) setInitError(error.message); }).finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [message, retry]);

  useEffect(() => {
    if (!currentRecord) return;
    if (!currentRecord.signal_names.includes(leadName || '')) setLeadName(currentRecord.signal_names.includes('MLII') ? 'MLII' : currentRecord.signal_names[0]);
    setStartSec((value) => Math.min(value, Math.max(0, currentRecord.duration_seconds - durationSec)));
    setSelected(null); setBeat(null); setPrediction(null); setComparison(null); setPinned([]); setPlaybackSegment(null); setPlayhead(null); setPlaying(false);
  }, [recordId]); // record changes reset interaction state; the window effect below loads the selected time range.

  useEffect(() => {
    if (currentRecord) setStartSec((value) => Math.min(value, Math.max(0, currentRecord.duration_seconds - durationSec)));
  }, [durationSec, currentRecord?.duration_seconds]);

  useEffect(() => {
    if (!currentRecord) return;
    const controller = new AbortController();
    actionController.current?.abort(); actionBusy.current = false;
    requestVersion.current += 1;
    setSelected(null); setBeat(null); setPrediction(null); setComparison(null); setPinned([]);
    setPlaying(false); setPlaybackSegment(null); setPlayhead(null); setPlaybackLoading(false); setInferenceLoading(false);
    const start = Math.min(startSec, Math.max(0, currentRecord.duration_seconds - durationSec));
    setWindowLoading(true); setWaveform(null); setAnnotations([]);
    Promise.all([api.window(recordId, start, durationSec, leadName, controller.signal), api.annotations(recordId, start, durationSec, task, controller.signal)])
      .then(([signal, marks]) => { if (!controller.signal.aborted) { setWaveform(signal); setAnnotations(marks); } })
      .catch((error: Error) => { if (!controller.signal.aborted) message.error(`波形读取失败：${error.message}`); })
      .finally(() => { if (!controller.signal.aborted) setWindowLoading(false); });
    return () => controller.abort();
  }, [recordId, task, leadName, startSec, durationSec, currentRecord?.duration_seconds, message, retry]);

  useEffect(() => () => actionController.current?.abort(), []);

  useEffect(() => {
    if (requestedSample!==null || playbackSegment || playing || (!presentationStep&&!focusMode) || selected || !annotations.length) return;
    const candidate = annotations.find(item => item.within_task && item.time_seconds >= BEAT_SAFE_GUARD_SECONDS && ['N', 'V'].includes(item.aami_label || ''));
    if (candidate) setSelected(candidate);
  }, [presentationStep, annotations, selected]);

  useEffect(() => {
    if (!selected || !currentRecord) return;
    actionController.current?.abort(); actionBusy.current = false;
    const version = ++requestVersion.current;
    const controller = new AbortController();
    setInferenceLoading(true); setComparison(old=>old?.models[0]?.annotation_sample===selected.annotation_sample&&old.models[0]?.task===task?old:null); setBeat(null); setPrediction(null);
    const cachedPrediction = matchingPlaybackAnnotation?.predictions?.find((item) => item.model_id === modelId);
    const canInferSelected = recordCanInfer && leadName === 'MLII';
    api.beat(recordId, selected.annotation_sample, task, leadName, controller.signal)
      .then(async detail => {
        if (controller.signal.aborted || requestVersion.current !== version) return;
        setBeat(detail);
        const result = cachedPrediction || (canInferSelected && detail.inference_eligible && !playbackSegment && !playbackLoading && !playing && (presentationStep === undefined || presentationStep >= 3)
          ? await api.predict(recordId, selected.annotation_sample, task, modelId, controller.signal) : null);
        if (requestVersion.current !== version) return;
        setPrediction(result);
      }).catch((error: Error) => {
        if (requestVersion.current !== version) return;
        if (!controller.signal.aborted) message.warning(error.message);
      }).finally(() => { if (requestVersion.current === version) setInferenceLoading(false); });
    return () => { controller.abort(); requestVersion.current += 1; };
  }, [selected?.annotation_sample, recordId, task, modelId, leadName, recordCanInfer, matchingPlaybackAnnotation, run, presentationStep]);

  useEffect(() => {
    if (!playing || !playbackSegment || demoPaused) return;
    return clock.start(playbackSegment.start_sec,playbackSegment.start_sec+playbackSegment.duration_sec,speed,setPlayhead,()=>setPlaying(false));
  },[playing,playbackSegment,speed,demoPaused,clock]);
  useEffect(()=>{if(!playing)clock.seek(playhead);},[playhead,playing,clock]);
  useEffect(()=>()=>clock.stop(),[clock]);
  useEffect(()=>{if(requestedSample!==null&&recordId===requestedRecord&&!selected&&annotations.length){const mark=annotations.find(a=>a.annotation_sample===requestedSample);if(mark)setSelected(mark);}},[annotations,requestedSample,requestedRecord,recordId]);

  useEffect(() => {
    if (playhead === null || !playbackSegment) return;
    const previous = playbackSegment.annotations.filter((item) => item.within_task && item.time_seconds <= playhead).at(-1);
    if (previous && previous.annotation_sample !== selected?.annotation_sample) setSelected(previous);
    if (!previous && selected) { setSelected(null); setBeat(null); setPrediction(null); setComparison(null); }
  }, [Math.floor((playhead || 0) * 20), playbackSegment]);

  const selectAnnotation = useCallback((item: BeatAnnotation) => {
    setSelected(item); setActiveTab('waveform');
    if (!item.within_task) message.info(`标注 ${item.original_label}（AAMI ${item.aami_label || '未归类'}）不属于 ${taskText[task]} 推理范围。`);
  }, [message, task]);

  const runCompare = async () => {
    if (!selected || !recordCanInfer || !beat?.inference_eligible || actionBusy.current) return;
    actionController.current?.abort(); const controller = new AbortController(); actionController.current = controller; actionBusy.current = true;
    setInferenceLoading(true);
    try { const result = await api.compare(recordId, selected.annotation_sample, task, controller.signal); if (!controller.signal.aborted) { setComparison(result); setActiveTab('compare'); } }
    catch (error) { if (!controller.signal.aborted) message.error(`同拍对比失败：${(error as Error).message}`); }
    finally { if (!controller.signal.aborted) { setInferenceLoading(false); actionBusy.current = false; } }
  };

  const startPlayback = async () => {
    if (!currentRecord || actionBusy.current || windowLoading) return;
    actionController.current?.abort(); const controller = new AbortController(); actionController.current = controller; actionBusy.current = true;
    setPlaybackLoading(true);
    try {
      const actualDuration = Math.min(durationSec, currentRecord.duration_seconds - startSec);
      const segment = await api.playback(recordId, startSec, actualDuration, task,
        recordCanInfer ? ['logistic_regression', 'random_forest', 'cnn_1d'] : [], leadName, controller.signal);
      if (controller.signal.aborted) return;
      setPlaybackSegment(segment); clock.seek(startSec); setPlayhead(startSec); setPlaying(true); setActiveTab('waveform');
      message.success(`已载入 ${segment.predicted_beat_count} 个可推理标注心拍的历史回放结果。`);
    } catch (error) { if (!controller.signal.aborted) message.error(`历史片段加载失败：${(error as Error).message}`); }
    finally { if (!controller.signal.aborted) { setPlaybackLoading(false); actionBusy.current = false; } }
  };

  const stopPlayback = () => { clock.seek(null); setPlaying(false); setPlayhead(null); setPlaybackSegment(null); };
  const resumePlayback = () => {
    if (!playbackSegment) return;
    const end = playbackSegment.start_sec + playbackSegment.duration_sec;
    if (playhead === null || playhead >= end) {clock.seek(playbackSegment.start_sec);setPlayhead(playbackSegment.start_sec);}
    setPlaying(true);
  };
  const seekPlayback = (value: number) => { clock.seek(value); setPlayhead(value); if (playbackSegment && value <= playbackSegment.start_sec) setPlaying(false); };
  const pinBeat = () => {
    if (!beat || pinned.some((item) => item.annotation_sample === beat.annotation_sample)) return;
    setPinned((items) => items.length >= 2 ? items : [...items, beat]);
    message.success('已加入单拍形态对比。');
  };

  const mainChartAnnotations = playbackSegment ? playbackSegment.annotations : annotations;
  const counts = useMemo(() => {
    const result: Record<string, number> = {};
    annotations.forEach((item) => { const label = item.aami_label || '其他标注'; result[label] = (result[label] || 0) + 1; });
    return result;
  }, [annotations]);

  if (loading) return <div className="workspace-loading"><Skeleton active paragraph={{ rows: 8 }} /></div>;
  if (initError) return <div className="research-page"><Alert type="error" showIcon title="工作台初始化失败" description={initError} action={<Button aria-label="重试" onClick={() => { setInitError(''); setLoading(true); setRetry(n => n + 1); }}>重试</Button>} /></div>;

  const stepBeat=(direction:number)=>{const available=mainChartAnnotations.filter(a=>a.within_task);const time=playhead??selected?.time_seconds??startSec;const next=direction>0?available.find(a=>a.time_seconds>time+.001):available.filter(a=>a.time_seconds<time-.001).at(-1);if(next){if(playbackSegment)seekPlayback(next.time_seconds);else selectAnnotation(next);}};
  const playback=<section className="standalone-playback"><PanelTitle icon={<PlayCircleOutlined/>} zh="历史回放" en="Playback · Beat-level"/><PlaybackControls playing={playing} loading={playbackLoading} hasSegment={Boolean(playbackSegment)} start={startSec} end={startSec+Math.min(durationSec,Math.max(0,(currentRecord?.duration_seconds||0)-startSec))} playhead={playhead} speed={speed} onStart={startPlayback} onResume={resumePlayback} onPause={()=>{setPlayhead(clock.time);setPlaying(false);}} onStop={stopPlayback} onSeek={seekPlayback} onSpeed={setSpeed} onPrevious={()=>stepBeat(-1)} onNext={()=>stepBeat(1)}/><span className="playback-beat-count">心拍：{mainChartAnnotations.filter(a=>a.within_task&&a.time_seconds<=(playhead??selected?.time_seconds??startSec)).length} / {mainChartAnnotations.filter(a=>a.within_task).length}</span></section>;
  const detail=(variant:'full'|'waveform'|'result'='full')=><Reveal id={beat?.annotation_sample||0}><BeatDetail beat={beat} prediction={currentPrediction||null} onPin={pinBeat} pinnedCount={pinned.length} variant={variant}/></Reveal>;
  return <main className={`workspace-shell fidelity-workspace ${focusMode?'inference-workspace':''}`}><div className="workspace-content">
    <div className="page-heading"><LineChartOutlined className="page-title-icon"/><div><div className="heading-lockup"><Typography.Title level={2}>{focusMode?'AI 智能检测':'ECG 心拍分析'}</Typography.Title><span>/ {focusMode?'AI Detection Workspace':'Analysis Workspace'}</span></div><Typography.Paragraph>{focusMode?'选择真实心电心拍，切换不同模型执行检测，并对比预测结果。':'对指定心电记录进行波形分析、心拍检测与分类，查看多模型对比和节拍级可视化结果。'}</Typography.Paragraph></div><div className="page-heading-badges"><Button size="small" onClick={()=>setDetailOpen(true)}>心拍与记录详情</Button><Button size="small" icon={<BookOutlined/>} onClick={()=>setGuideOpen(true)}>操作指引</Button></div></div>
    <div className="workspace-grid">
    <aside className="control-rail"><Card className="rail-card" title={<PanelTitle icon={<SettingOutlined/>} zh={focusMode?'检测控制台':'分析控制台'} en="Analysis Console"/>}>
      <label className="field-label"><DatabaseOutlined/> 记录选择（Record）</label><Select aria-label="MIT-BIH 记录" showSearch value={recordId} onChange={setRecordId} optionFilterProp="label" options={records.map(r=>({value:r.record_id,label:`${r.record_id}（MIT-BIH · ${r.dataset_split==='excluded_from_model_dataset'?'仅浏览':r.dataset_split}）`}))}/>
      <label className="field-label"><LineChartOutlined/> 导联选择（Lead）</label><Select aria-label="ECG 导联" value={leadName} onChange={setLeadName} options={currentRecord?.signal_names.map(value=>({value,label:`${value}${value==='MLII'?'（模型输入）':''}`}))}/>
      <label className="field-label"><ApiOutlined/> 分类任务（Task）</label><Segmented block value={task} onChange={v=>{setTask(v as TaskName);setSelected(null);setBeat(null);setPrediction(null);setComparison(null);setPlaybackSegment(null);setPlaying(false);}} options={[{label:'N / V',value:'nv'},{label:'N / S / V / F',value:'nsvf'}]}/>
      <label className="field-label"><DeploymentUnitOutlined/> 模型选择（Model）</label><Select aria-label="推理模型" value={modelId} onChange={setModelId} disabled={!recordCanInfer||leadName!=='MLII'} options={usableModels.map(m=>({value:m.model_id,label:MODEL_LABELS[m.model_id]}))}/>
      {focusMode?<details className="ai-window-settings"><summary>片段时间设置</summary><div className="time-fields"><div><label className="field-label">起始时间 (s)</label><InputNumber aria-label="起始时间秒" min={0} max={Math.max(0,(currentRecord?.duration_seconds||0)-durationSec)} value={startSec} onChange={v=>setStartSec(Number(v||0))}/></div><div><label className="field-label">时长 (s)</label><InputNumber aria-label="窗口时长秒" min={1} max={30} value={durationSec} onChange={v=>setDurationSec(Math.min(30,Math.max(1,Number(v||10))))}/></div></div></details>:<div className="time-fields"><div><label className="field-label">起始时间 (s)</label><InputNumber aria-label="起始时间秒" min={0} max={Math.max(0,(currentRecord?.duration_seconds||0)-durationSec)} value={startSec} onChange={v=>setStartSec(Number(v||0))}/></div><div><label className="field-label">时长 (s)</label><InputNumber aria-label="窗口时长秒" min={1} max={30} value={durationSec} onChange={v=>setDurationSec(Math.min(30,Math.max(1,Number(v||10))))}/></div></div>}
      <Button className="analyze-button" aria-label={focusMode?'执行检测':'开始分析'} type="primary" block icon={<PlayCircleOutlined/>} loading={inferenceLoading||windowLoading} onClick={()=>{if(selected)setRun(n=>n+1);else{const candidate=annotations.find(a=>a.within_task&&a.time_seconds>=BEAT_SAFE_GUARD_SECONDS);if(candidate)selectAnnotation(candidate);else setRetry(n=>n+1);}}}>{focusMode?'执行检测':'开始分析'}</Button>
      <Button className="compare-action" aria-label="比较三个模型" icon={<ApiOutlined/>} block disabled={!beat?.inference_eligible||!recordCanInfer||leadName!=='MLII'} loading={inferenceLoading} onClick={runCompare}>比较三个模型</Button>
      {!recordCanInfer&&<Alert type="info" title="此记录不属于当前 44 条模型数据集，仅可浏览波形"/>}<div className="console-foot"><Badge status={usableModels.length===3?'success':'error'}/>{usableModels.length}/3 模型就绪 · {currentRecord?.sampling_frequency} Hz <Tooltip title="重新读取当前记录与时间窗口"><Button type="link" size="small" onClick={()=>setRetry(n=>n+1)}>读取真实波形窗口</Button></Tooltip></div>
    </Card></aside>
    <section className="main-stage"><Card className="signal-card" title={<PanelTitle icon={<LineChartOutlined/>} zh={focusMode?'选中心拍波形':'ECG 波形分析'} en={focusMode?'Selected Beat Waveform':'ECG Waveform Analysis'}/>}>
      {focusMode? <><div className="selected-beat-panel">{detail(wide?'waveform':'full')}</div><div className="parent-wave"><span>父级波形窗口 · 记录 {recordId}</span>{waveform&&<ECGWaveformChart compact waveform={waveform} annotations={mainChartAnnotations} selectedSample={selected?.annotation_sample??null} playhead={playhead} predictions={chartPredictions} onSelect={selectAnnotation} clock={clock}/>}</div></>:<>
      <div className="signal-context">记录：{recordId}　|　导联：{leadName}　|　任务：{taskLabels[task].join(' / ')}<span>{waveform?.point_count.toLocaleString()} 采样点</span></div>
      {windowLoading?<Skeleton active paragraph={{rows:6}}/>:waveform?<ECGWaveformChart waveform={waveform} annotations={mainChartAnnotations} selectedSample={selected?.annotation_sample??null} playhead={playhead} predictions={chartPredictions} onSelect={selectAnnotation} clock={clock} classFocus={classFocus} onClassFocus={setClassFocus} onUserZoom={()=>{if(playing){setPlayhead(clock.time);setPlaying(false);}}}/>:<Empty description="请选择记录并读取时间窗口"/>}
      <div className="chart-meta"><span><i className="line-key"/>ECG 波形</span>{['N','S','V','F'].map(l=><span key={l}><i className="dot-key" style={{background:CLASS_COLORS[l]}}/>{l}</span>)}<span>专家标注 · 单击查看详情</span></div></>}
      <div className="annotation-shortcuts"><span>可选标注</span>{annotations.filter(a=>a.annotation_kind==='mapped_beat'&&a.within_task&&a.time_seconds>=BEAT_SAFE_GUARD_SECONDS&&a.time_seconds<=startSec+durationSec-.05).slice(0,7).map(a=><Button size="small" key={a.annotation_sample} data-testid={`beat-${a.annotation_sample}`} onClick={()=>selectAnnotation(a)}>{a.aami_label} · {a.time_seconds.toFixed(2)}s</Button>)}</div>
      {inferenceLoading&&<div className="inline-loading">读取标注并运行真实模型…</div>}
    </Card></section>
    {wide&&<aside className="detail-rail" aria-label="当前心拍详情"><Card className="live-beat-card" title={<PanelTitle icon={<HeartOutlined/>} zh={focusMode?'检测结果':'节拍详情'} en={focusMode?'Inference Result':'Beat Detail'}/>}>{detail(focusMode?'result':'full')}</Card></aside>}
    </div>
    {!focusMode&&!wide&&selected&&<Card className="compact-beat-detail" title="当前节拍详情">{detail()}</Card>}
    {!focusMode&&playback}
    <PredictionComparison currentModel={modelId} onModelChange={setModelId} loading={inferenceLoading} result={matchingPlaybackAnnotation?.predictions?.length===3?{models:matchingPlaybackAnnotation.predictions,all_models_agree:new Set(matchingPlaybackAnnotation.predictions.map(p=>p.predicted_class)).size===1,agreement_statement:'当前历史心拍的真实三模型预测；专家标签仅供参考。'}:comparison}/>
    {focusMode&&playback}
    {playbackSegment&&<div className="playback-status">历史片段 · 已缓存 {playbackSegment.predicted_beat_count} 个可推理心拍 · 当前 {(playhead??startSec).toFixed(2)} s · {playbackSegment.notice}</div>}
    <details className="morphology-details"><summary>心拍形态对比与单拍工具</summary><Button className="beat-detail-toggle" disabled={!selected} onClick={()=>setBeatFocus(v=>!v)}>{beatFocus?'返回完整波形':'查看心拍细节'}</Button>{beatFocus&&<div className="beat-focus">{beat&&<div className="enlarged-beat"><BeatDetail beat={beat} prediction={null} onPin={pinBeat} pinnedCount={pinned.length} variant="waveform"/></div>}</div>}<Button disabled={!beat?.inference_eligible} loading={inferenceLoading} onClick={()=>setRun(n=>n+1)}>运行 {MODEL_LABELS[modelId]} 推理</Button><MorphologyCompare beats={pinned} onRemove={sample=>setPinned(items=>items.filter(b=>b.annotation_sample!==sample))}/></details>
    </div>
    <Drawer title="心拍与记录详情" open={detailOpen} onClose={() => setDetailOpen(false)} size={440}>
      <Typography.Paragraph>记录 {recordId} · {leadName} · {currentRecord?.dataset_split}</Typography.Paragraph>
      <BeatDetail beat={beat} prediction={currentPrediction || null} onPin={pinBeat} pinnedCount={pinned.length} />
      <Typography.Paragraph type="secondary">专家参考标签与 AI 预测分别展示。原始符号 {selected?.original_label || '—'} / AAMI {selected?.aami_label || '—'}。</Typography.Paragraph>
    </Drawer>
    <Drawer title="演示指引" open={guideOpen} onClose={() => setGuideOpen(false)} size={420}>
      <div className="guide-content"><Tag color="blue">课程演示路径</Tag><Typography.Title level={4}>从真实标注到模型结果</Typography.Title><ol><li><b>选择记录。</b>先选 200；右侧会显示记录、受试者分区和可用导联。</li><li><b>选择任务。</b>N/V 或 N/S/V/F 标签范围来自项目现有 AAMI 映射。</li><li><b>选取心拍。</b>读取时间窗后，点击图中的标注符号查看原始与滤波波形。</li><li><b>运行模型。</b>选一个模型做单拍推理，或比较三个模型对同一心拍的输出。</li><li><b>回放历史片段。</b>使用播放、暂停、倍速和时间滑块浏览实际记录。回放预测在加载片段时批量生成并缓存。</li></ol><Alert type="warning" showIcon title="范围说明" description="排除记录、非 MLII 导联及不属于当前任务的标注可用于数据浏览，但不会进入模型推理。这里的专家标签供回顾展示，不作为模型特征。" /><Alert className="guide-alert" type="info" showIcon title="结果解释" description="显示的是已保存课程模型对 MIT-BIH 历史样本的输出。训练/验证/测试分区仅用于追溯，不代表独立临床验证；模型概率未经校准。" /></div>
    </Drawer>
  </main>;
}

function MorphologyCompare({ beats, onRemove }: { beats: BeatData[]; onRemove: (sample: number) => void }) {
  if (!beats.length) return <div className="tab-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="在单拍分析中选择心拍并加入对比，最多比较两条" /></div>;
  const width = 760; const height = 310; const left = 55; const right = 18; const top = 24; const bottom = 42;
  const all = beats.flatMap((item) => item.raw_amplitude_mv); const min = Math.min(...all); const max = Math.max(...all); const span = Math.max(0.01, max - min);
  const colors = ['#1677FF', '#DC2626'];
  const paths = beats.map((beat, beatIndex) => beat.raw_amplitude_mv.map((value, index) => {
    const px = left + index / Math.max(1, beat.raw_amplitude_mv.length - 1) * (width - left - right);
    const py = top + (max - value) / span * (height - top - bottom);
    return `${index ? 'L' : 'M'}${px.toFixed(1)},${py.toFixed(1)}`;
  }).join(' '));
  const zeroX = left + (width - left - right) * 0.3 / 0.7;
  return <div className="morphology-panel"><Typography.Title level={5}>标注点对齐的原始心拍波形</Typography.Title><Typography.Paragraph type="secondary">所有片段以专家标注位置为 t=0；垂直轴使用真实 mV。最多固定两拍作形态观察。</Typography.Paragraph><div className="pinned-tags">{beats.map((beat) => <Tag closable onClose={() => onRemove(beat.annotation_sample)} key={`${beat.record_id}-${beat.annotation_sample}`}>记录 {beat.record_id} · {beat.original_label}→{beat.aami_label} · {beat.time_seconds.toFixed(2)}s</Tag>)}</div><div className="morphology-legend">{beats.map((beat, index) => <span key={beat.annotation_sample}><i style={{ background: colors[index] }} />记录 {beat.record_id} · {beat.original_label}→{beat.aami_label}</span>)}</div><svg className="morphology-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="两个或更少标注心拍的对齐形态对比">
    {[0, .25, .5, .75, 1].map((fraction) => { const value = max - span * fraction; const yy = top + (height - top - bottom) * fraction; return <g key={fraction}><line x1={left} x2={width - right} y1={yy} y2={yy} stroke="#f0dedd" strokeDasharray="3 4" /><text x={left - 8} y={yy + 4} textAnchor="end">{value.toFixed(2)}</text></g>; })}
    <line x1={zeroX} x2={zeroX} y1={top} y2={height - bottom} stroke="#9caeab" strokeDasharray="4 4" />{paths.map((path, index) => <path key={index} d={path} fill="none" stroke={colors[index]} strokeWidth="2" />)}
    <text x={left} y={height - 10}>−0.3 s</text><text x={zeroX} y={height - 10} textAnchor="middle">t=0</text><text x={width - right} y={height - 10} textAnchor="end">+0.4 s</text><text transform={`translate(14 ${height / 2}) rotate(-90)`} textAnchor="middle">振幅 (mV)</text>
  </svg></div>;
}



