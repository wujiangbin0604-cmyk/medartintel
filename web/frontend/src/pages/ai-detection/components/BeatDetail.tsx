import React from 'react';
import { Button, Empty, Tag, Typography } from 'antd';
import type { BeatDetail, Prediction } from '@/types/ecg';
import { CLASS_COLORS } from '@/design';
import {ProbabilityBar} from '@/components/Motion';
import {Chart} from '@/components/Research';

interface Props { beat: BeatDetail | null; prediction: Prediction | null; onPin: () => void; pinnedCount: number; variant?:'full'|'waveform'|'result' }

export default function BeatDetail({ beat, prediction, onPin, pinnedCount,variant='full' }: Props) {
  if (!beat) return <div className="beat-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="点击 ECG 上的专家标注点，查看单拍波形与模型结果" /></div>;
  return <div className="beat-detail">
    {variant!=='result'&&<><div className="beat-heading"><div><Typography.Text className="eyebrow">专家标注</Typography.Text><Typography.Title level={4}>{beat.original_label}<span className="muted"> → </span>{beat.aami_label}</Typography.Title></div><Tag color={CLASS_COLORS[beat.aami_label||'Q']}>AAMI：{beat.aami_label}</Tag><Button size="small" disabled={pinnedCount >= 2} onClick={onPin}>加入形态对比</Button></div>
    <div className="beat-facts"><span>记录 <b>{beat.record_id}</b></span>{' '}<span>时间 <b>{beat.time_seconds.toFixed(3)} s</b></span>{' '}<span>样本 <b>{beat.annotation_sample.toLocaleString()}</b></span>{' '}<span>导联 <b>{beat.lead_name}</b></span></div>
    <BeatPlot beat={beat} /></>}
    {variant!=='waveform'&&(prediction ? <div className="prediction-card" data-testid="single-prediction">
      <div className="prediction-top"><span>AI 预测 · 与专家参考{prediction.prediction_matches_expert ? '一致' : '不同'}</span><Tag color={CLASS_COLORS[prediction.predicted_class]}>{prediction.predicted_class}</Tag></div>
      <div className="probability-list">{Object.entries(prediction.class_probabilities).map(([label,value])=><ProbabilityBar key={label} label={label} value={value} color={CLASS_COLORS[label]}/>)}</div>
      <div className="prediction-foot">{prediction.model_id.replaceAll('_', ' ')} · {prediction.inference_time_ms.toFixed(2)} ms · {prediction.dataset_split} split</div>
      <Typography.Text type="secondary" className="small-note">概率未经临床校准，仅供教学演示。</Typography.Text>
    </div> : <div className="prediction-pending">{beat.inference_unavailable_reason || '切换模型可对同一标注位置重新推理'}</div>)}
  </div>;
}

function BeatPlot({beat}:{beat:BeatDetail}){
 const data=(values:number[])=>values.map((value,i)=>[beat.window_time_relative_seconds[i],value]);
 return <div className="beat-plot-wrap"><Chart height={180} label="单拍原始与滤波波形，单位毫伏" option={{legend:{top:0,right:0,itemWidth:13,textStyle:{fontSize:9}},grid:{left:44,right:12,top:30,bottom:35},tooltip:{trigger:'axis',valueFormatter:(v:any)=>`${Number(v).toFixed(3)} mV`},xAxis:{type:'value',min:-.3,max:.4,name:'时间 (s，相对标注)',nameLocation:'middle',nameGap:24,axisLabel:{fontSize:10},splitLine:{lineStyle:{color:'#e7eff8'}}},yAxis:{type:'value',scale:true,name:'mV',nameTextStyle:{fontSize:10},axisLabel:{fontSize:10},splitLine:{lineStyle:{color:'#e7eff8'}}},series:[{name:'原始信号',itemStyle:{color:'#b1c1d5'},type:'line',showSymbol:false,lineStyle:{color:'#b1c1d5',width:1.2},data:data(beat.raw_amplitude_mv)},{name:'训练滤波输入',itemStyle:{color:'#1677ff'},type:'line',showSymbol:false,lineStyle:{color:'#1677ff',width:1.8},data:data(beat.filtered_amplitude_mv),markLine:{silent:true,symbol:'none',lineStyle:{color:'#e64980',type:'dashed'},label:{show:false},data:[{xAxis:0}]}}]}}/></div>;
}
