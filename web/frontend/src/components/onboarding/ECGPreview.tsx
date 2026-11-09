import React, { useId } from 'react';
import { motion } from 'motion/react';
import { useMotionSettings } from '@/utils/motion';
import GamepadIcon from '@/components/GamepadIcon';

const path = 'M0 110h28l7-4 7 4h14l5-5 5-52 6 77 7-22 7 2 12-4 8 4h25l7-5 5-50 7 75 6-22 9 2 11-5 9 5h24l8-4 6 3 11-2 8-7 8 6 8 54 10-94 9 23 11 10 11 5 13-5 10 5h20l8-4 6-52 7 75 7-21 11 2 12-4 9 4h26l7-4 6-50 7 72 7-19 10 1h25';
export default function ECGPreview({ compact = false }: { compact?: boolean }) {
  const { reduced } = useMotionSettings(); const id = useId().replace(/:/g, '');
  return <div className={`welcome-ecg-preview ${compact ? 'compact' : ''}`} aria-label="Heartbeat Hunter 心电波形预览" role="img">
    {!compact && <div className="welcome-preview-top"><span><GamepadIcon/> Heartbeat Hunter</span><small>心跳猎人</small></div>}
    {!compact && <div className="welcome-preview-heart" aria-hidden="true"><svg viewBox="0 0 180 160"><defs><linearGradient id={`${id}heart`} x2="1" y2="1"><stop stopColor="#c8efff"/><stop offset="1" stopColor="#369eff"/></linearGradient></defs><path d="M90 139C72 125 25 88 25 54c0-36 46-45 65-15 20-30 65-21 65 15 0 34-47 71-65 85Z" fill={`url(#${id}heart)`} stroke="#fff" strokeWidth="3"/><path d="M18 82h43l11-23 16 50 14-36 10 9h48" fill="none" stroke="#fff" strokeWidth="3.5" strokeLinejoin="round"/><ellipse cx="90" cy="79" rx="83" ry="36" fill="none" stroke="#87cafa" transform="rotate(-30 90 79)"/></svg></div>}
    <div className="welcome-preview-chart">
      {!compact && <div className="welcome-preview-chart-label"><span>观察 · 发现 · 学习</span><b>目标 V 组</b></div>}
      <div className="welcome-preview-signal"><svg viewBox="0 0 480 205" aria-hidden="true" preserveAspectRatio="none">
        <defs><pattern id={`${id}grid`} width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="#dbeaf9" strokeWidth=".8"/></pattern><linearGradient id={`${id}line`}><stop stopColor="#1677ff"/><stop offset="1" stopColor="#06b6d4"/></linearGradient></defs>
        <rect width="480" height="205" fill={`url(#${id}grid)`}/>
        <rect x="266" width="45" height="205" fill="#fce7f355"/>
        <motion.path d={path} fill="none" stroke={`url(#${id}line)`} strokeWidth="2.8" strokeLinejoin="round" initial={{ pathLength: reduced ? 1 : 0 }} animate={{ pathLength: 1 }} transition={{ duration: reduced ? 0 : 1.2, ease: 'easeInOut' }}/>
      </svg>{!compact&&<div className="welcome-demo-marker" aria-hidden="true">✓<span>得分示意 +100</span><motion.i initial={{scale:1,opacity:reduced?0:.65}} animate={{scale:reduced?1:2.4,opacity:0}} transition={{duration:reduced?0:.9,delay:.4}}/></div>}</div>
      {!compact && <div className="welcome-preview-axis"><span>0 s</span><span>观察不同的心拍形态</span><span>10 s</span></div>}
    </div>
    {!compact && <div className="welcome-preview-demo">心电波形预览</div>}
  </div>;
}
