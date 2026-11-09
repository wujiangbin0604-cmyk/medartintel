import React from 'react';
import { Alert, Progress, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { MODEL_LABELS, type Prediction } from '@/types/ecg';
import { CLASS_COLORS } from '@/design';

export default function PredictionComparison({ result }: { result: { models: Prediction[]; all_models_agree: boolean; agreement_statement: string } | null }) {
  if (!result) return <div className="tab-empty">选中心拍后，点击“同拍三模型对比”查看真实模型输出。</div>;
  const columns: ColumnsType<Prediction> = [
    { title: '模型', dataIndex: 'model_id', render: (id: Prediction['model_id']) => MODEL_LABELS[id] },
    { title: '预测', dataIndex: 'predicted_class', render: (label: string) => <Tag color={CLASS_COLORS[label]}>{label}</Tag> },
    { title: '最大类别概率', key: 'probability', render: (_, row) => `${(Math.max(...Object.values(row.class_probabilities)) * 100).toFixed(2)}%` },
    { title: '专家 AAMI', dataIndex: 'expert_label' },
    { title: '匹配', dataIndex: 'prediction_matches_expert', render: (yes: boolean) => yes ? <Tag color="success">一致</Tag> : <Tag color="warning">不同</Tag> },
    { title: '耗时', dataIndex: 'inference_time_ms', render: (ms: number) => `${ms.toFixed(2)} ms` },
  ];
  return <div className="comparison-panel"><Alert type={result.all_models_agree ? 'success' : 'info'} showIcon title={result.agreement_statement} description="三种模型对相同原始标注位置、相同预处理心拍执行推理。" />
    <Table rowKey="model_id" columns={columns} dataSource={result.models} pagination={false} size="small" scroll={{ x: 650 }} />
    <div className="probability-comparison"><Typography.Title level={5}>类别概率对比</Typography.Title>
      {result.models.map((model) => <div className="model-probability" key={model.model_id}><div className="model-prob-title">{MODEL_LABELS[model.model_id]} <Tag>{model.predicted_class}</Tag></div><div className="model-prob-grid">{Object.entries(model.class_probabilities).map(([label, value]) => <div key={label}><span>{label}</span><Progress percent={value * 100} size="small" showInfo={false} strokeColor={CLASS_COLORS[label]} /><b>{(value * 100).toFixed(1)}%</b></div>)}</div></div>)}
    </div>
  </div>;
}
