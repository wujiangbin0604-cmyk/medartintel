import React, { useEffect, useState } from 'react';
import { Link } from '@umijs/max';
import { Alert, Button, Tag } from 'antd';
import { AimOutlined, ArrowRightOutlined, ExperimentOutlined, HeartOutlined, TrophyOutlined } from '@ant-design/icons';
import { gameApi, names, playerId, type History } from './gameApi';
import './index.less';

export function Gamepad() { return <svg viewBox="0 0 48 40" fill="none" aria-hidden="true"><path d="M13 8h22c5 0 8 5 9 12l2 10c1 7-5 9-9 4l-5-5H16l-5 5c-4 5-10 3-9-4l2-10C5 13 8 8 13 8Z" stroke="currentColor" strokeWidth="3"/><path d="M14 14v12M8 20h12" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/><circle cx="33" cy="16" r="2.5" fill="currentColor"/><circle cx="39" cy="23" r="2.5" fill="currentColor"/></svg>; }
export default function InteractiveLab() {
  const [history, setHistory] = useState<History>(); const [error, setError] = useState('');
  useEffect(() => { const controller = new AbortController(); gameApi.history(playerId(), controller.signal).then(setHistory).catch(e => { if (!controller.signal.aborted) setError(e.message); }); return () => controller.abort(); }, []);
  return <main className="hunter-page hunter-lab">
    <div className="hunter-heading"><div><h1><ExperimentOutlined /> 心电互动实验室</h1><p>ECG Interactive Lab · 从观察波形，到读懂每一次心跳。</p></div><Tag color="blue">真实数据，互动学习</Tag></div>
    {error && <Alert type="error" title={error} showIcon />}
    <section className="hunter-lab-feature"><div className="hunter-lab-copy"><Tag color="cyan">心电识别闯关游戏</Tag><h2><Gamepad /> Heartbeat Hunter</h2><h3>心跳猎人</h3><p>在真实 ECG 心电波形中寻找 V 组心拍。<br />从候选心拍辅助练习，到限时历史回放，逐步训练你的观察力。</p><div className="hunter-lab-facts"><span><HeartOutlined /> MIT-BIH 原始波形</span><span><AimOutlined /> 专家标签判分</span><span><TrophyOutlined /> 五关连续挑战</span></div><Link to="/interactive-lab/heartbeat-hunter"><Button type="primary" size="large">进入心跳猎人 <ArrowRightOutlined /></Button></Link></div><div className="hunter-lab-art" aria-hidden="true"><div className="hunter-heart"><HeartOutlined /></div><div className="hunter-art-label">观察 · 定位 · 揭晓 · 学习</div></div></section>
    <div className="hunter-lab-bottom"><section className="hunter-panel"><h2><TrophyOutlined /> 个人最高分</h2><div className="hunter-best-grid">{Object.entries(names).map(([key, label]) => <div key={key}><span>{label}</span><strong>{history?.best[key as keyof typeof names] || 0}<small> 分</small></strong></div>)}</div><p className="hunter-note">单关娱乐积分，保存在本地教学环境。</p></section><section className="hunter-panel"><h2>最近挑战</h2>{history?.records.length ? history.records.slice(0, 4).map(r => <div className="hunter-history-row" key={r.session_id}><span>{new Date(r.completed_at*1000).toLocaleString('zh-CN')}</span><span>{names[r.difficulty]} · 第 {r.round} 关</span><b>{r.score} 分</b></div>) : <p className="hunter-note">你的第一场心跳探索，从这里开始。</p>}</section></div>
    <p className="hunter-note">V 指 MIT-BIH 的 AAMI V 组（室性异位心拍），不等同于所有异常心律；游戏仅用于课程学习。</p>
  </main>;
}
