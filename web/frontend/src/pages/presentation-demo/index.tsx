import React, { useState } from 'react';
import { Link } from '@umijs/max';
import { Alert, App, Button, Card, Space, Steps } from 'antd';
import { PauseOutlined,PlayCircleOutlined,FullscreenOutlined } from '@ant-design/icons';
import Dashboard from '../dashboard';
import AIDetection from '../ai-detection';
import Experiments from '../experiments';
import Generalization from '../generalization';
import {Reveal} from '@/components/Motion';

const steps=['介绍项目','真实 ECG 波形','专家参考标注','CNN 真实推理','同拍三模型比较','历史波形回放','二分类与四分类','实验局限与总结'];
const guidance=[
  '介绍 MIT-BIH 历史数据、N/V 与 N/S/V/F 任务，以及 LR、RF、1D-CNN 三种已训练模型。',
  '已定位记录 200 的 6–16 秒片段，导联 MLII。波形和标注均由本机 WFDB 文件读取。',
  '点击波形标注，或使用下方带时间的标注按钮。重点区分专家参考标签与 AI 预测标签。',
  '点击“开始分析”。这会调用真实后端；可重复操作，显示结果与未经校准的模型概率。',
  '点击“比较三个模型”，固定当前真实心拍，观察类别、概率、与专家标签的匹配情况及耗时。',
  '点击“播放历史片段”，演示暂停、继续、倍速和时间定位。回放的是 MIT-BIH 历史记录。',
  '切换二分类与四分类，比较 Macro-F1、类别 Support、混淆矩阵和训练曲线。',
  '说明 S/F 少数类与患者集中度问题。项目串联了真实信号、模型推理、评估和错误诊断；现有结果用于研究教学。',
];
export default function PresentationDemo() {
  const [step,setStep]=useState(0);const [paused,setPaused]=useState(false); const {message}=App.useApp();
  const fullscreen=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch(e){message.warning(`无法进入全屏：${(e as Error).message}`);}};
  return <div className={`demo-page ${paused?'demo-paused':''}`}><div className="demo-toolbar"><div><strong>课程答辩演示</strong><span>第 {step+1} / 8 步</span></div><Space><Button aria-label={paused?'继续演示':'暂停演示'} icon={paused?<PlayCircleOutlined/>:<PauseOutlined/>} onClick={()=>setPaused(v=>!v)}>{paused?'继续演示':'暂停演示'}</Button><Button icon={<FullscreenOutlined />} onClick={fullscreen}>全屏</Button><Link to="/dashboard"><Button>退出演示</Button></Link></Space></div>
    <div className="demo-progress"><Steps size="small" current={step} onChange={v=>{if(!paused)setStep(v);}} items={steps.map(title=>({title}))} /></div>
    <Reveal id={step}><Alert className="demo-guidance" type="info" showIcon title={steps[step]} description={paused?'演示已暂停；历史回放时钟已停下，继续后从当前位置恢复。':guidance[step]} /></Reveal>
    <div hidden={step!==0}>{step===0&&<Dashboard />}</div>
    {step>=1&&step<=5&&<AIDetection presentationStep={step} demoPaused={paused} />}
    {step===6&&<Experiments />}{step===7&&<Generalization />}
    <div className="demo-navigation"><Button disabled={step===0||paused} onClick={()=>setStep(n=>n-1)}>上一页</Button><span>{steps[step]}</span>{step<7?<Button type="primary" disabled={paused} onClick={()=>setStep(n=>n+1)}>下一页</Button>:<Link to="/dashboard"><Button type="primary">完成演示</Button></Link>}</div>
  </div>;
}
