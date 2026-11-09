import React, { useEffect, useRef, useState } from 'react';
import { history, useLocation } from '@umijs/max';
import { Alert, Button, Checkbox, Modal } from 'antd';
import { ArrowRightOutlined, CheckCircleOutlined, DatabaseOutlined, RobotOutlined } from '@ant-design/icons';
import { motion } from 'motion/react';
import { ECGMark } from '@/components/MedicalVisuals';
import { request } from '@/services/api';
import { useMotionSettings } from '@/utils/motion';
import ECGPreview from './ECGPreview';
import { completeWelcome, GAME_PATH, hasCompletedWelcome, WELCOME_EVENT } from './state';
import './welcome.less';

export default function WelcomeOnboarding() {
  const location = useLocation(); const { reduced } = useMotionSettings();
  const [open, setOpen] = useState(false), [remember, setRemember] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const controller = useRef<AbortController>(); const inFlight = useRef(false);
  useEffect(() => { if (['/', '/dashboard'].includes(location.pathname) && !hasCompletedWelcome()) setOpen(true); }, [location.pathname]);
  useEffect(() => { const show = () => { setError(''); setOpen(true); }; window.addEventListener(WELCOME_EVENT, show); return () => { window.removeEventListener(WELCOME_EVENT, show); controller.current?.abort(); }; }, []);
  const dismiss = (choice: 'browse' | 'close') => {
    controller.current?.abort(); inFlight.current = false; setBusy(false);
    completeWelcome(choice, remember); setOpen(false); setError('');
  };
  const enterGame = async () => {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError('');
    controller.current?.abort(); const pending = new AbortController(); controller.current = pending;
    try {
      // Skip never calls this endpoint. Readiness checks never create a timed session.
      const config = await request<{ level_count: number }>('/api/games/heartbeat-hunter/config', { signal: pending.signal });
      if (!Number.isInteger(config.level_count) || config.level_count < 1) throw new Error('当前没有可用的游戏关卡');
      if (pending.signal.aborted) return;
      completeWelcome('challenge', remember); setOpen(false);
      history.push(`${GAME_PATH}?welcome=1`);
    } catch (e) {
      if (!pending.signal.aborted) setError(`心跳猎人暂时不可用：${(e as Error).message}。可重试，或先逛逛平台。`);
    } finally { if (!pending.signal.aborted) { setBusy(false); inFlight.current = false; } }
  };
  return <Modal open={open} title="欢迎来到 ECG-AI！" footer={null} width={1080} centered onCancel={() => dismiss('close')}
    rootClassName={`welcome-onboarding-modal ${reduced ? 'welcome-reduced' : ''}`} maskClosable={false}
    transitionName="" maskTransitionName="" styles={{ body: { padding: 0 }, mask: { background: 'rgba(188, 211, 235, 0.54)', backdropFilter: 'blur(5px)' } }}
    modalRender={node => <motion.div initial={{ opacity: reduced ? 1 : 0, y: reduced ? 0 : 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduced ? 0 : .3 }}>{node}</motion.div>}>
    <div className="welcome-onboarding" data-testid="welcome-onboarding" data-reduced={reduced}>
      <div className="welcome-copy">
        <div className="welcome-brand"><span><ECGMark/></span><div><b>ECG-AI</b><small>医学人工智能，从一颗心跳开始</small></div></div>
        <motion.div className="welcome-intro" initial={{opacity:reduced?1:0}} animate={{opacity:1}} transition={{delay:reduced?0:.08,duration:reduced?0:.3}}>
          <span className="welcome-english">Welcome to ECG-AI</span><h1 id="welcome-title">欢迎来到 ECG-AI！</h1>
          <h2>你能在真实的心电图中<br/>发现异常心跳吗？</h2>
          <p>从 <strong>Heartbeat Hunter · 心跳猎人</strong> 开始你的医学人工智能探索之旅。</p>
        </motion.div>
        <motion.div className="welcome-features" initial={{opacity:reduced?1:0}} animate={{opacity:1}} transition={{delay:reduced?0:.14,duration:reduced?0:.3}}>
          <div><DatabaseOutlined/><span><b>真实 ECG，亲手发现</b><small>观察 MIT-BIH 波形，寻找 AAMI V 组心拍。</small></span></div>
          <div><CheckCircleOutlined/><span><b>轻松闯关，逐拍复盘</b><small>三种难度，专家标注揭晓每一次选择。</small></span></div>
          <div><RobotOutlined/><span><b>跟随好奇心，走近 AI</b><small>挑战结束后，在检测工作台比较真实模型预测。</small></span></div>
        </motion.div>
      </div>
      <div className="welcome-visual"><ECGPreview/></div>
      <div className="welcome-actions">
        {error && <Alert type="warning" showIcon title="游戏暂时不可用" description={error} />}
        <div className="welcome-buttons"><Button aria-label="开始心跳挑战" type="primary" size="large" loading={busy} onClick={enterGame}>开始心跳挑战 <ArrowRightOutlined/></Button><Button size="large" onClick={() => dismiss('browse')}>先逛逛平台</Button></div>
        <Checkbox checked={remember} onChange={e => setRemember(e.target.checked)}>下次不再自动显示</Checkbox>
        <small className="welcome-once-note">本版本默认仅自动展示一次；勾选后保留不再自动展示的偏好。</small>
      </div>
      <div className="welcome-footer"><span>医学人工智能教学与互动学习</span></div>
    </div>
  </Modal>;
}
