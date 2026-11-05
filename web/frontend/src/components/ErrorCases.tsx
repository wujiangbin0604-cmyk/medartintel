import React from 'react';
import {Link} from '@umijs/max';
import {Card,Empty,Table,Tag} from 'antd';
import {ResourceState,Source,useResource,type Row} from './Research';
import type {ModelId,TaskName} from '@/types/ecg';
export default function ErrorCases({task,model,trueLabel,predictedLabel,subject}:{task:TaskName;model:ModelId;trueLabel:string;predictedLabel:string;subject?:string}){
 const query=new URLSearchParams({task,model,true_label:trueLabel,predicted_label:predictedLabel,...(subject?{subject}: {})});
 const resource=useResource<{count:number;rows:Row[];source:string}>(`/api/research/errors?${query}`);
 return <Card className="error-cases" title={`真实样本 · ${trueLabel} → ${predictedLabel}`} extra={<Tag>历史 test · 最多展示 20 条</Tag>}>{!resource.data?<ResourceState {...resource}/>:<>{resource.data.rows.length?<Table rowKey="sample_id" size="small" pagination={false} scroll={{x:550}} dataSource={resource.data.rows} columns={[{title:'记录',dataIndex:'record_id'},{title:'时间 (s)',dataIndex:'time_s',render:v=>Number(v).toFixed(3)},{title:'受试者',dataIndex:'subject_id'},{title:'专家 / 预测',render:()=>`${trueLabel} / ${predictedLabel}`},{title:'查看',render:(_,row)=><Link to={`/ai-detection?record=${row.record_id}&time=${row.time_s}&sample=${row.annotation_sample}&task=${task}`}>查看 ECG 波形</Link>}]}/>:<Empty description="该方向没有已保存样本"/>}<p className="chart-insight">共 {resource.data.count} 条既有预测；点击记录将定位真实 WFDB 时间与样本，重新推理的结果单独显示。</p><Source>{resource.data.source}</Source></>}</Card>;
}
