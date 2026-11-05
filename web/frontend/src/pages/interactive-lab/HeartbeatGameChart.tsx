import React, { memo, useEffect, useMemo, useRef } from 'react';
import * as echarts from 'echarts';
import { useMotionSettings } from '@/utils/motion';
import type { GameSession, GameStatus, ScoreEvent } from './gameApi';

interface Props { session: GameSession | null; selections: number[]; status: GameStatus; onSelect: (sample: number) => void; revealed: number; onReview: (sample: number) => void }
function HeartbeatGameChart(props: Props) {
  const { session, selections, status, revealed } = props;
  const { reduced } = useMotionSettings();
  const host = useRef<HTMLDivElement>(null), scan = useRef<HTMLDivElement>(null), ring = useRef<HTMLSpanElement>(null);
  const chart = useRef<echarts.ECharts>();
  const latest = useRef(props); latest.current = props;
  const data = useMemo(() => session?.signal.map((y, i) => [i / session.sampling_rate, y]) || [], [session?.signal]);
  useEffect(() => {
    if (!host.current) return;
    const instance = echarts.init(host.current); chart.current = instance;
    const positionRing = () => {
      const current=latest.current, s=current.session, sample=current.selections[current.selections.length-1];
      if(!ring.current||!s||sample===undefined)return;
      const xy=instance.convertToPixel({xAxisIndex:0,yAxisIndex:0},[(sample-s.start_sample)/s.sampling_rate,s.signal[sample-s.start_sample]]) as number[];
      ring.current.style.left=`${xy[0]}px`;ring.current.style.top=`${xy[1]}px`;
      ring.current.style.display=instance.containPixel('grid',xy)?'block':'none';
    };
    instance.on('rendered',positionRing);instance.on('datazoom',positionRing);
    const click = (event: any) => {
      const current = latest.current, s = current.session;
      if (!s || !instance.containPixel('grid', [event.offsetX, event.offsetY])) return;
      const [x] = instance.convertFromPixel({ gridIndex: 0 }, [event.offsetX, event.offsetY]) as number[];
      let sample = s.start_sample + Math.round(x * s.sampling_rate);
      if (current.status === 'finished') {
        const nearest = s.result?.answers.reduce((best, beat) => Math.abs(beat.sample - sample) < Math.abs(best.sample - sample) ? beat : best);
        if (nearest) current.onReview(nearest.sample);
        return;
      }
      if (current.status !== 'playing') return;
      if (s.candidate_samples.length) {
        const nearest = s.candidate_samples.reduce((a, b) => Math.abs(a - sample) < Math.abs(b - sample) ? a : b);
        if (Math.abs(nearest - sample) > s.sampling_rate * .1) return;
        sample = nearest;
      }
      current.onSelect(Math.max(s.start_sample, Math.min(s.end_sample - 1, sample)));
    };
    instance.getZr().on('click', click);
    const observer = new ResizeObserver(() => instance.resize()); observer.observe(host.current);
    return () => { observer.disconnect(); instance.dispose(); chart.current = undefined; };
  }, []);
  useEffect(() => {
    const instance = chart.current;
    if (!instance || !session) return;
    const s = session;
    const at = (sample: number) => [(sample - s.start_sample) / s.sampling_rate, s.signal[sample - s.start_sample] ?? 0];
    const events = s.result?.events.slice(0, revealed) || [];
    const eventMap = new Map<number, ScoreEvent>(events.map(e => [e.sample, e]));
    const finished = status === 'finished';
    const marks = finished ? s.result?.answers || [] : [];
    instance.setOption({
      animation: !reduced, animationDuration: 650, animationDurationUpdate: reduced ? 0 : 200,
      grid: { left: 60, right: 25, top: 42, bottom: 63 },
      tooltip: { show: false },
      xAxis: { type: 'value', min: 0, max: s.duration, name: '片段时间 (s)', nameLocation: 'middle', nameGap: 30,
        axisLine: { lineStyle: { color: '#a8bcd6' } }, axisLabel: { color: '#526785' },
        splitLine: { lineStyle: { color: '#dfecfa' } }, minorTick: { show: true, splitNumber: 5 }, minorSplitLine: { show: true, lineStyle: { color: '#eff5fc' } } },
      yAxis: { type: 'value', name: '振幅 (mV)', nameLocation: 'middle', nameGap: 43, scale: true, boundaryGap: ['25%', '35%'],
        axisLabel: { color: '#526785' }, splitLine: { lineStyle: { color: '#dfecfa' } }, minorTick: { show: true, splitNumber: 5 }, minorSplitLine: { show: true, lineStyle: { color: '#eff5fc' } } },
      dataZoom: [{ id: 'inside', type: 'inside', filterMode: 'none', disabled: s.difficulty === 'beginner' || (s.difficulty === 'challenge' && status === 'playing'), zoomOnMouseWheel: true, moveOnMouseMove: true },
        { id: 'slider', type: 'slider', height: 10, bottom: 3, show: s.difficulty !== 'beginner', showDetail: false, borderColor: 'transparent', fillerColor: '#1677ff20' }],
      series: [
        { id: 'signal', type: 'line', data, showSymbol: false, silent: true, lineStyle: { width: 1.9, color: '#1677ff', shadowColor: '#1677ff20', shadowBlur: 4 },
          markArea: { silent: true, itemStyle: { color: '#1677ff08' }, data: selections.map(sample => [{ xAxis: (sample-s.start_sample)/s.sampling_rate-.12 }, { xAxis: (sample-s.start_sample)/s.sampling_rate+.12 }]) } },
        { id: 'candidates', type: 'scatter', symbolSize: 15, z: 3, silent: true, itemStyle: { color: '#fff', borderColor: '#38bdf8', borderWidth: 2 },
          data: finished ? [] : s.candidate_samples.filter(a => !selections.includes(a)).map(at) },
        { id: 'selected', type: 'scatter', symbolSize: 23, z: 5, silent: true,
          data: selections.map(sample => ({ value: at(sample), itemStyle: { color: eventMap.has(sample) ? eventMap.get(sample)!.correct ? '#16a34a' : '#ef4444' : '#ec4899', borderColor: '#fff', borderWidth: 2 },
            label: { show: true, color: '#fff', formatter: eventMap.has(sample) ? eventMap.get(sample)!.correct ? '✓' : '×' : '✓', fontWeight: 'bold' } })) },
        { id: 'experts', type: 'scatter', z: 4, symbolSize: 12, silent: true,
          data: marks.map(a => ({ value: at(a.sample), itemStyle: { color: a.label === 'V' ? '#ec4899' : '#7aa6d8', borderColor: '#fff', borderWidth: 1 },
            label: { show: true, formatter: a.label, position: 'top', color: a.label === 'V' ? '#c72664' : '#526785', fontWeight: 'bold' } })) },
        { id: 'points', type: 'scatter', silent: true, symbolSize: 0, z: 6, data: events.map(e => ({ value: at(e.sample), label: { show: true, position: 'top', distance: 26, formatter: (e.delta > 0 ? '+' : '') + e.delta, color: e.correct ? '#16a34a' : '#ef4444', fontSize: 18, fontWeight: 'bold' } })) },
      ],
    }, { replaceMerge: ['series'] });
  }, [session, data, selections, status, revealed, reduced]);
  useEffect(() => {
    if (!session || !chart.current || status !== 'playing') { if (scan.current) scan.current.style.opacity = '0'; return; }
    let frame = 0, lastZoom = 0, lastDisplay = 0;
    const started = performance.now();
    const tick = (now: number) => {
      const instance = chart.current;
      if (!instance) return;
      const position = Math.min(session.duration, session.playback_position + (now-started)/1000*session.speed);
      if (host.current && now - lastDisplay > 100) { host.current.dataset.playback = position.toFixed(3); lastDisplay = now; }
      if (session.difficulty === 'challenge' && now-lastZoom > (reduced ? 300 : 120)) {
        const start = Math.min(Math.max(0, position-5), session.duration-6);
        instance.dispatchAction({ type: 'dataZoom', startValue: start, endValue: start+6 }, { silent: true }); lastZoom = now;
      }
      if (scan.current && !reduced) {
        const pixel = instance.convertToPixel({ xAxisIndex: 0 }, position) as number;
        scan.current.style.transform = `translateX(${pixel}px)`;
        scan.current.style.opacity = position < session.duration && pixel >= 60 && pixel <= (host.current?.clientWidth || 0)-25 ? '1' : '0';
      }
      if (position < session.duration) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(frame); if (scan.current) scan.current.style.opacity = '0'; };
  }, [session, status, reduced]);
  return <div className="hunter-wave-host">
    <div ref={host} className="hunter-wave" role="img" aria-label="真实 MIT-BIH 游戏心电图" data-testid="game-chart" />
    <div ref={scan} className="hunter-scan" aria-hidden="true"><i /></div>
    {selections.length>0&&status==='playing'&&<span ref={ring} key={selections.join(',')} className="hunter-selection-pulse" aria-hidden="true"/>}
    {!session && <div className="hunter-chart-empty"><span>准备好，捕捉不一样的心跳。</span><p>选择难度后开始挑战，加载真实 MIT-BIH 心电图</p><small>原始物理振幅 · 专家标注判分 · 本地教学数据</small></div>}
  </div>;
}
export default memo(HeartbeatGameChart);
