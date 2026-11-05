import React from 'react';
import { Button, Select, Slider, Space, Tag, Typography } from 'antd';
import { PauseCircleOutlined, PlayCircleOutlined, ReloadOutlined, StepBackwardOutlined,StepForwardOutlined } from '@ant-design/icons';

interface Props {
  playing: boolean; loading: boolean; start: number; end: number; playhead: number | null;
  speed: number; hasSegment: boolean; onStart: () => void; onResume: () => void; onPause: () => void; onStop: () => void;
  onSeek: (value: number) => void; onSpeed: (value: number) => void;
  onPrevious?:()=>void;onNext?:()=>void;
}

export default function PlaybackControls(props: Props) {
  const { playing, loading, start, end, playhead, speed, hasSegment, onStart, onResume, onPause, onStop, onSeek, onSpeed } = props;
  const handlePlay = playing ? onPause : hasSegment ? onResume : onStart;
  const playLabel = playing ? '暂停' : hasSegment ? '继续' : '播放历史片段';
  return <div className="playback-bar"><div className="playback-actions"><Space size={8}>
    <Button type="primary" aria-label={playLabel} icon={playing ? <PauseCircleOutlined /> : <PlayCircleOutlined />} loading={loading} onClick={handlePlay}>{playLabel}</Button>
    <Button aria-label="上一心拍" title="上一心拍" icon={<StepBackwardOutlined/>} onClick={props.onPrevious}/><Button aria-label="下一心拍" title="下一心拍" icon={<StepForwardOutlined/>} onClick={props.onNext}/>
    <Button icon={<StepBackwardOutlined />} onClick={onStop} disabled={playhead === null}>停止</Button>
    <Button icon={<ReloadOutlined />} onClick={() => onSeek(start)} disabled={playhead === null}>回到起点</Button>
    <Select aria-label="回放速度" size="small" value={speed} onChange={onSpeed} options={[0.5, 1, 2, 4].map((value) => ({ value, label: `${value}×` }))} />
    <Tag color="blue">历史回放</Tag>
  </Space><Typography.Text type="secondary">不是实时监护</Typography.Text></div>
    <div className="playback-timeline"><span>{(playhead ?? start).toFixed(2)} s</span><Slider min={start} max={end} step={0.01} value={Math.min(end, Math.max(start, playhead ?? start))} onChange={onSeek} disabled={playhead === null} tooltip={{ formatter: (value) => `${Number(value).toFixed(2)} s` }} /><span>{end.toFixed(2)} s</span></div>
  </div>;
}
