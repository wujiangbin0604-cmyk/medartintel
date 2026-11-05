import React from 'react';
import { Link } from '@umijs/max';
import { Button, Tag } from 'antd';
import { ArrowRightOutlined } from '@ant-design/icons';
import GamepadIcon from '@/components/GamepadIcon';
import ECGPreview from './ECGPreview';
import { GAME_PATH, showWelcome } from './state';
import './welcome.less';

export default function GameRecommendation() {
  return <section className="dashboard-game-recommendation" aria-label="心跳猎人游戏推荐">
    <div className="recommendation-game-icon"><GamepadIcon/></div>
    <div className="recommendation-copy"><h2>试试你的心电识别能力！</h2><p>在真实 ECG 波形中寻找 V 类心拍。</p><div><Tag color="blue">新手友好</Tag><Tag color="cyan">三种难度</Tag><span>Heartbeat Hunter · 心跳猎人</span></div></div>
    <div className="recommendation-preview"><ECGPreview compact/><small>装饰波形 · 视觉演示</small></div>
    <div className="recommendation-actions"><Link to={GAME_PATH}><Button type="primary" aria-label="推荐卡开始挑战">开始挑战 <ArrowRightOutlined/></Button></Link><Button type="link" onClick={showWelcome}>查看欢迎引导</Button></div>
  </section>;
}
