import React, { useEffect, useRef, useState } from 'react';
import { Alert, Button, Skeleton, Typography } from 'antd';
import * as echarts from 'echarts';
import { request } from '@/services/api';
import { useMotionSettings } from '@/utils/motion';
import {AppstoreOutlined,ExperimentOutlined,BarChartOutlined,PictureOutlined} from '@ant-design/icons';

export type Row = Record<string, string>;
export interface ResearchData {
  metrics: Row[]; confusion: Row[]; per_class: Row[]; splits: Row[]; subjects: Row[];
  concentration: Row[]; cv: Row[]; weights: Row[]; sources: Record<string, string>;
  histories: Record<string, { rows: Row[]; best_epoch: number; source: string }>;
  weight_classes: Row[];
  subject_metrics: Row[];
}
export function useResource<T>(url: string) {
  const [data, setData] = useState<T>(); const [error, setError] = useState(''); const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setData(undefined); setError('');
    request<T>(url, { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setData(value); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [url, retry]);
  return { data, error, reload: () => setRetry(n => n + 1) };
}
export function ResourceState({ error, reload }: { error: string; reload: () => void }) {
  return error ? <Alert type="error" showIcon title="数据加载失败" description={error} action={<Button aria-label="重试" onClick={reload}>重试</Button>} /> : <Skeleton active paragraph={{ rows: 8 }} />;
}
export function PageHeading({ title, description, extra }: { title: string; description: string; extra?: React.ReactNode }) {
  const english=title==='项目总览'?'Dashboard':title.includes('实验')?'Model Experiments':title.includes('泛化')?'Generalization Analysis':'Research Gallery';
  const Icon=title==='项目总览'?AppstoreOutlined:title.includes('实验')?ExperimentOutlined:title.includes('泛化')?BarChartOutlined:PictureOutlined;
  return <div className="research-heading"><Icon className="page-title-icon"/><div><div className="heading-lockup"><Typography.Title level={1}>{title}</Typography.Title><span>/ {english}</span></div><Typography.Paragraph>{description}</Typography.Paragraph></div>{extra}</div>;
}
export function Chart({ option, height = 300, label, onClick }: { option: echarts.EChartsOption; height?: number; label: string; onClick?: (event: any) => void }) {
  const ref = useRef<HTMLDivElement>(null); const instance = useRef<echarts.ECharts>();
  const {reduced}=useMotionSettings(); const latest=useRef(onClick);latest.current=onClick;
  const legend=useRef<Record<string,boolean>>({});
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current); instance.current = chart;
    chart.on('click',(event)=>latest.current?.(event));
    chart.on('legendselectchanged',(event:any)=>{legend.current=event.selected;});
    chart.on('mouseover',(event:any)=>{if(event.seriesType!=='heatmap')return;const config=chart.getOption() as any;const cells=config.series[event.seriesIndex]?.data||[];chart.dispatchAction({type:'downplay',seriesIndex:event.seriesIndex});chart.dispatchAction({type:'highlight',batch:cells.flatMap((cell:any,index:number)=>{const value=cell.value||cell;return value[0]===event.value[0]||value[1]===event.value[1]?[{seriesIndex:event.seriesIndex,dataIndex:index}]:[];})});});
    chart.on('globalout',()=>chart.dispatchAction({type:'downplay'}));
    const observer = new ResizeObserver(() => chart.resize()); observer.observe(ref.current);
    return () => { observer.disconnect(); chart.dispose(); instance.current = undefined; };
  }, []);
  useEffect(() => { instance.current?.setOption({ textStyle: { fontFamily: '"Segoe UI", "Microsoft YaHei", sans-serif', color: '#64748B' }, tooltip: { trigger: 'axis', confine: true }, grid: { left: 52, right: 24, top: 42, bottom: 48 }, ...option, animation:!reduced,animationDuration:550,animationDurationUpdate:450,animationEasing:'cubicOut',legend:{...(!Array.isArray(option.legend)?option.legend:{}),selected:legend.current} }, {replaceMerge:['series']}); }, [option,reduced]);
  return <div ref={ref} style={{ height, width: '100%', minWidth: 0 }} role="img" aria-label={label} />;
}
export function Source({ children }: { children: React.ReactNode }) { return <p className="data-source">来源：{children}</p>; }
