import React, { useMemo, useState } from 'react';
import { Alert, Button, Card, Empty, InputNumber, Select, Space, Table, Tabs, Tag } from 'antd';
import { Chart, PageHeading, ResourceState, Source, useResource } from '@/components/Research';
import './index.less';

const names: Record<string, string> = { A0: 'A0 · 原始结构 CNN', A1: 'A1 · RR-only MLP', A2: 'A2 · 节律形态融合', A3: 'A3 · 打乱 RR 对照' };
const colors = ['#1677ff', '#13a2a2', '#4059a9', '#8295ab'];
const percent = (v: number | null | undefined) => v == null ? '—' : `${(v * 100).toFixed(2)}%`;
interface LabData { status: string; config?: any; models: any[]; folds: any[]; per_class: any[]; patients: any[]; subject_count?: number; sample_count?: number; source?: string; uncertainty: any; completed_jobs?: number; expected_jobs?: number; }

function Architecture() {
  const [step, setStep] = useState(2);
  return <Card title="双分支结构" extra={<Tag>结构与张量示意</Tag>}>
    <Space wrap className="rhythm-stage-controls">{['查看形态分支', '查看节律分支', '查看融合输出'].map((text, i) => <Button key={text} type={step === i ? 'primary' : 'default'} onClick={() => setStep(i)}>{text}</Button>)}</Space>
    <div className={`rhythm-architecture stage-${step}`}>
      <div className="rhythm-branches"><div className="rhythm-branch morphology"><b>ECG 单拍</b><span>[B, 1, 253]</span><i>Conv 1→16, k7 → Pool 126<br />Conv 16→32, k5 → Pool 63<br />Conv 32→64, k3 → AvgPool 1</i><strong>64 维形态表示</strong></div>
        <div className="rhythm-branch timing"><b>历史 RR 与可用性</b><span>[B, 7] 特征 ＋ [B, 7] 掩码</span><i>Linear 14→32 → ReLU<br />Linear 32→16 → ReLU</i><strong>16 维节律表示</strong></div></div>
      <span className="rhythm-join" aria-hidden="true">→</span><div className="rhythm-fusion"><b>拼接 64 ＋ 16</b><span>[B, 80]</span><i>Linear 80→4</i><strong>N / S / V / F</strong></div>
    </div><p className="chart-insight" aria-live="polite">{['波形编码器复用 HeartbeatCNN 的三层卷积结构。', '仅使用当前与过去的专家心拍位置，缺失值采用训练侧统计量和掩码。', '拼接后输出类别分数；此图不展示实际神经元激活。'][step]}</p>
  </Card>;
}

function BeatAnalysis({ record, sample }: { record: string; sample: number }) {
  const resource = useResource<any>(`/api/rhythm/beat?record_id=${encodeURIComponent(record)}&annotation_sample=${sample}`);
  const [method, setMethod] = useState('max_score');
  if (!resource.data) return <ResourceState {...resource} />;
  const d = resource.data, beat = d.beat;
  return <div data-testid="rhythm-beat-results"><p><Tag color="blue">记录 {beat.record_id}</Tag>样本 {beat.annotation_sample} · 专家 {beat.original_label} / AAMI {beat.aami_label} · 原 {beat.dataset_split} · {beat.subject_id}</p>
    <div className="rhythm-two-column"><Chart label="真实单拍滤波波形" height={240} option={{ xAxis: { type: 'category', data: beat.window_time_relative_seconds.map((x: number) => x.toFixed(3)), name: 's' }, yAxis: { type: 'value', name: 'mV', scale: true }, series: [{ type: 'line', data: beat.filtered_amplitude_mv, showSymbol: false, lineStyle: { color: '#1677ff', width: 2 } }] }} />
      <Chart label="历史 RR 与当前 RR" height={240} option={{ xAxis: { type: 'category', data: [...d.history_rr_s.map((_: number, i: number) => `历史 ${i + 1}`), '当前'] }, yAxis: { type: 'value', name: 'RR (s)' }, series: [{ type: 'bar', data: [...d.history_rr_s, d.current_rr_s], itemStyle: { color: '#13a2a2' } }] }} /></div>
    {d.rhythm_missing_reason ? <Alert type="warning" title={d.rhythm_missing_reason} /> : null}
    <div className="rhythm-feature-strip">{d.feature_names.map((name: string, i: number) => <div key={name}><small>{name}</small><b>{d.rhythm_features[i] == null ? '缺失' : d.rhythm_features[i].toFixed(4)}</b></div>)}</div>
    {d.original_cnn ? <p>原正式 CNN：<Tag>{d.original_cnn.predicted_class}</Tag><small>版本 {d.original_cnn.model_version} · SHA {d.original_cnn.model_sha256.slice(0, 12)}</small></p> : null}
    {d.research_available ? <><Space wrap><span>人工复核策略</span><Select aria-label="拒识指标" value={method} onChange={setMethod} options={[{ value: 'max_score', label: '1 − 最大类别分数' }, { value: 'entropy', label: '信息熵' }]} /></Space>
      <Table rowKey="model" pagination={false} scroll={{ x: 720 }} dataSource={d.models} columns={[{ title: '外层留出模型', dataIndex: 'model', render: v => names[v] }, { title: '预测', dataIndex: 'prediction' }, { title: '最大类别分数', dataIndex: 'max_score', render: percent }, { title: '熵 (nats)', dataIndex: 'entropy', render: v => v.toFixed(4) }, { title: '复核提示', render: (_, row: any) => { const p = row.policies.find((p: any) => p.method === method); return p ? <Tag color={p.needs_review ? 'orange' : 'green'}>{p.needs_review ? '需要人工复核' : '符合接受条件'}</Tag> : '阈值未就绪'; } }]} />
      {d.models.map((m: any) => { const p = m.policies.find((p: any) => p.method === method); return <details key={m.model}><summary>{names[m.model]} · 版本及阈值来源</summary><p>{m.version} · SHA-256 {m.sha256}</p>{p ? <p>接受条件 U ≤ {p.threshold.toFixed(5)}；由 {p.calibration_subjects.length} 个独立内部校准患者的 90% 分位数确定。当前患者属于外层 fold {m.fold + 1}，未参与训练、早停或阈值选择。</p> : <p>拒识分析尚未就绪。</p>}</details>; })}
      <p className="chart-insight">{d.models[0].prediction === d.models[1].prediction ? '两种外层留出模型对本拍预测一致。' : '两种外层留出模型对本拍预测不同。'} 单个教学案例不能证明泛化改善。</p></> : <Alert type="info" title="研究模型暂不可用" description={d.unavailable_reason} />}
    <p className="data-source">{d.note} 类别分数和熵均未经临床校准。</p>
  </div>;
}

function SamplePicker() {
  const query = new URLSearchParams(window.location.search);
  const [label, setLabel] = useState('S');
  const samples = useResource<{ samples: any[] }>(`/api/rhythm/samples?label=${label}`);
  const [record, setRecord] = useState(query.get('record_id') || '200');
  const [sample, setSample] = useState<number | null>(query.has('annotation_sample') ? Number(query.get('annotation_sample')) : null);
  const [selected, setSelected] = useState<{ record: string; sample: number } | null>(() => sample != null ? { record, sample } : null);
  const analyze = (rid = record, pos = sample) => { if (pos != null) { setSelected({ record: rid, sample: pos }); window.history.replaceState(null, '', `/rhythm-lab?record_id=${rid}&annotation_sample=${pos}`); } };
  return <Card title="单心拍节律分析" className="spaced-card"><Space wrap className="rhythm-picker"><Select aria-label="示例心拍类别" value={label} onChange={setLabel} options={['N', 'S', 'V', 'F'].map(value => ({ value, label: `${value} 类教学样本` }))} />
    <Select aria-label="真实心拍示例" placeholder="从实际患者选择心拍" style={{ width: 300, maxWidth: '100%' }} value={selected ? `${selected.record}:${selected.sample}` : undefined} onChange={value => { const [r, s] = value.split(':'); setRecord(r); setSample(Number(s)); analyze(r, Number(s)); }} options={(samples.data?.samples || []).map(v => ({ value: `${v.record_id}:${v.annotation_sample}`, label: `${v.record_id} / 样本 ${v.annotation_sample} / ${v.original_label}` }))} />
    <InputNumber aria-label="记录编号" controls={false} min={100} max={234} value={Number(record)} onChange={v => setRecord(String(v || ''))} /><InputNumber aria-label="标注样本位置" min={0} value={sample} onChange={setSample} /><Button type="primary" disabled={!record || sample == null} onClick={() => analyze()}>分析此心拍</Button></Space>
    {selected ? <BeatAnalysis key={`${selected.record}:${selected.sample}`} {...selected} /> : <Empty description="选择真实心拍后，查看历史 RR、专家标签与实际模型预测。" />}
  </Card>;
}

export default function RhythmLab() {
  const resource = useResource<LabData>('/api/rhythm/summary');
  const [task, setTask] = useState('nsvf'), [fold, setFold] = useState('all'), [seed, setSeed] = useState<number>(), [metric, setMetric] = useState('macro_f1');
  const [category, setCategory] = useState('S'), [classMetric, setClassMetric] = useState('f1'), [method, setMethod] = useState('max_score');
  const d = resource.data, selectedSeed = seed || d?.config?.seeds[0];
  const rows = useMemo(() => !d ? [] : fold === 'all' ? d.models.filter(m => m.seed === selectedSeed).map(m => ({ model: m.model, ...m.pooled, parameters: m.parameters, latency_ms: m.latency_ms, fold_sd: m.fold_sd_macro_f1 })) : d.folds.filter(m => m.seed === selectedSeed && String(m.fold) === fold), [d, selectedSeed, fold]);
  if (!d) return <div className="research-page"><ResourceState {...resource} /></div>;
  const ready = d.status === 'completed' && task === 'nsvf';
  const classRows = rows.map(row => ({ model: row.model, ...row.per_class?.[category] }));
  const policies = d.uncertainty?.status === 'completed' ? d.uncertainty.results.filter((r: any) => r.method === method && r.seed === selectedSeed) : [];
  const curves = (d.uncertainty?.risk_coverage || []).filter((r: any) => r.method === method && r.seed === selectedSeed && (fold === 'all' || String(r.fold) === fold));
  return <div className="research-page rhythm-lab"><PageHeading title="节律融合与可靠性实验室" description="同一心拍，形态与历史节律能否提供互补证据？在患者分组评价中检验，而非预设融合一定有效。" />
    <section className="rhythm-overview"><div><h2>从波形走向上下文</h2><p>比较单拍 CNN、RR-only、融合与打乱对照。沿用 44 记录协议与 201/202 合并规则；原正式测试患者隔离。</p><Tag color={d.status === 'completed' ? 'green' : 'blue'}>{d.status === 'completed' ? `阶段 A 已完成 ${d.folds.length} 组真实训练` : `已完成 ${d.completed_jobs || 0}/${d.expected_jobs || 20} 组`}</Tag><Tag>{d.uncertainty.status === 'completed' ? '阶段 B 已生成独立校准分析' : '阶段 B 尚未就绪'}</Tag></div>
      <dl><div><dt>评价患者</dt><dd>{d.subject_count || '—'}</dd></div><div><dt>开发心拍</dt><dd>{d.sample_count?.toLocaleString() || '—'}</dd></div><div><dt>实际种子 / 计划</dt><dd>{d.config?.seeds.length || 0} / 3</dd></div><div><dt>波形 ＋ RR/掩码</dt><dd>253 ＋ 14</dd></div></dl></section>
    <Alert type="info" showIcon title="原 train＋val 上的回顾性分组实验" description="外层患者不参与拟合、早停和阈值选择。开发患者此前已被分析，本实验不构成新的盲测或外部验证。波形仍使用原离线双向滤波，依赖专家心拍定位。" />
    <Architecture />
    <Card title="模型消融对比" className="spaced-card"><Tabs activeKey={task} onChange={setTask} items={[{ key: 'nsvf', label: 'N / S / V / F' }, { key: 'nv', label: 'N / V' }]} />
      {ready ? <><Space wrap><Select aria-label="分组评价折" value={fold} onChange={setFold} options={[{ value: 'all', label: '全部折 · 合并 OOF' }, ...Array.from({ length: d.config.outer_folds }, (_, i) => ({ value: String(i), label: `外层 Fold ${i + 1}` }))]} /><Select aria-label="实验随机种子" value={selectedSeed} onChange={setSeed} options={d.config.seeds.map((value: number) => ({ value, label: `seed ${value}` }))} /><Select aria-label="总体评价指标" value={metric} onChange={setMetric} options={['macro_f1', 'accuracy', 'balanced_accuracy'].map(value => ({ value, label: value }))} /></Space>
        <Chart label="四模型真实消融指标" option={{ xAxis: { type: 'category', data: rows.map(r => r.model) }, yAxis: { type: 'value', min: 0, max: 1, name: metric }, series: [{ type: 'bar', data: rows.map((r, i) => ({ value: r[metric], itemStyle: { color: colors[i] } })), label: { show: true, position: 'top', formatter: (p: any) => Number(p.value).toFixed(3) } }] }} />
        <Table rowKey="model" pagination={false} scroll={{ x: 850 }} dataSource={rows} columns={[{ title: '模型', dataIndex: 'model', render: v => names[v] }, ...['macro_f1', 'accuracy', 'balanced_accuracy'].map(k => ({ title: k, dataIndex: k, render: percent })), { title: '患者', dataIndex: 'subject_count' }, { title: '心拍', dataIndex: 'sample_count' }, { title: '参数量', dataIndex: 'parameters' }, { title: '推理 ms', dataIndex: 'latency_ms', render: v => v.toFixed(3) }]} />
        <p className="chart-insight">A0 是在相同内部划分重新训练的原 CNN 结构。A3 与 A2 参数量相同，RR 在各子分区内按固定无标签方案错配。合并 OOF 指标与折均值不同，患者缺失类别按固定标签集合计入 Macro-F1。</p>
        <Space wrap><Select aria-label="分析类别" value={category} onChange={setCategory} options={['N', 'S', 'V', 'F'].map(value => ({ value, label: `${value} 类` }))} /><Select aria-label="类别评价指标" value={classMetric} onChange={setClassMetric} options={['precision', 'recall', 'f1'].map(value => ({ value, label: value }))} /></Space>
        <Chart label="各模型少数类别指标" height={230} option={{ xAxis: { type: 'category', data: classRows.map(r => r.model) }, yAxis: { type: 'value', min: 0, max: 1, name: `${category} ${classMetric}` }, series: [{ type: 'bar', data: classRows.map((r, i) => ({ value: r[classMetric], itemStyle: { color: colors[i] } })) }] }} />
        <Table rowKey="model" pagination={false} size="small" scroll={{ x: 620 }} dataSource={classRows} columns={[{ title: '模型', dataIndex: 'model' }, { title: '支持拍数', dataIndex: 'support' }, { title: '独立患者', dataIndex: 'subject_count' }, ...['precision', 'recall', 'f1'].map(k => ({ title: k, dataIndex: k, render: percent }))]} /><Source>{d.source}/summary.json；外层留出心拍，非原 test。</Source></> : <Empty description={task === 'nv' ? 'N/V 新消融尚未执行；不复用四分类或历史测试指标填充。' : '完整分组实验尚未就绪，完成后重新加载可查看实际结果。'} />}
    </Card><SamplePicker />
    <Card title="模型可靠性与人工复核" className="spaced-card"><p>阈值来自每折单独的内部校准患者，固定目标覆盖率 90%。新患者的实际覆盖率可能不同。以下曲线是外层分数的描述性扫描，不用于重新选阈值。</p><Select aria-label="可靠性分析指标" value={method} onChange={setMethod} options={[{ value: 'max_score', label: '1 − 最大类别分数' }, { value: 'entropy', label: '信息熵' }]} />
      {policies.length ? <><Chart label="外层 Risk Coverage 曲线" option={{ legend: { data: Object.values(names) }, xAxis: { type: 'value', name: 'Coverage', min: 0, max: 1 }, yAxis: { type: 'value', name: '错误率', min: 0 }, series: Object.keys(names).map((model, i) => ({ name: names[model], type: 'line', itemStyle: { color: colors[i] }, data: [.1, .2, .3, .4, .5, .6, .7, .8, .9, 1].map(c => { const items = curves.filter((r: any) => r.model === model && r.nominal_coverage === c); return [items.reduce((s: number, r: any) => s + r.coverage, 0) / Math.max(1, items.length), items.reduce((s: number, r: any) => s + r.risk, 0) / Math.max(1, items.length)]; }) })) }} />
        <p className="data-source">{fold === 'all' ? '各折描述曲线的等权平均；固定阈值的全体 OOF 指标见下表。' : `外层 Fold ${Number(fold) + 1} 描述曲线；下表为所有外层患者合并的固定阈值结果。`}</p>
        <Table rowKey="model" pagination={false} scroll={{ x: 800 }} dataSource={policies} columns={[{ title: '模型', dataIndex: 'model', render: v => names[v] }, { title: 'Coverage', dataIndex: 'coverage', render: percent }, { title: '拒识比例', dataIndex: 'rejection_rate', render: percent }, { title: '全部错误率', dataIndex: 'all_error_rate', render: percent }, { title: '接受拍错误率', dataIndex: 'accepted_error_rate', render: percent }, { title: '拒识拍真实错误率', dataIndex: 'rejected_error_rate', render: percent }, { title: '接受 / 全部拍数', render: (_, r: any) => `${r.accepted} / ${r.total}` }]} /><Source>research_extensions/uncertainty/results/cv_cpu_v1/summary.json</Source></> : <Empty description="阶段 B 尚未完成；阈值和风险结果不作预填。" />}
      <Alert type="warning" showIcon title="分数与熵只是未校准的不确定性代理" description="接受样本错误率降低不意味着全部心拍更准确。教学中的人工复核提示不代表已验证的医疗风险识别能力。" />
    </Card>
  </div>;
}
