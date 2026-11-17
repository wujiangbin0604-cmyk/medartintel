from pathlib import Path
P=Path(__file__).resolve().parents[1]
p=P/'draft/ECG_AI_课程论文_修订版V2.md';s=p.read_text(encoding='utf-8')
s=s.replace('本文数据表仅统计通过窗口和信号有效性规则、实际进入模型数据集的心拍。','本文模型结果表统计通过窗口和信号有效性规则、实际进入模型数据集的心拍；数据构建流程表另列原始事件与映射阶段数量。')
s=s.replace('表12与图10仅使用既有CNN训练和验证结果。','表12与图10展示既有CNN训练实验的验证侧结果。')
s=s.replace('本轮直接汇总第三阶段的保存对照CSV','本轮直接汇总已有部署对照CSV（phase3_validation）')
s=s.replace('p的下标(i,yᵢ)为其预测概率，w的下标yᵢ为对应类别权重','p_(i,yᵢ)为对应真实类别的预测概率，w_(yᵢ)为类别权重')
s=s.replace('$$ L = −Σᵢ w的下标yᵢ log p的下标(i,yᵢ) / Σᵢ w的下标yᵢ （3）','$$ L = −Σᵢ w_(yᵢ) log p_(i,yᵢ) / Σᵢ w_(yᵢ) （3）')
old='另一个需要关注的事实是，该CNN最佳检查点在验证集上的Macro-F1仅0.6630，明显低于测试集0.9865。验证与测试患者及类别构成不同，分数高低不必同向；这种差异进一步表明，单个较高测试分数不足以证明对未知患者的稳定表现。'
s=s.replace(old,'验证侧与测试侧的差异进一步在5.1.1节按患者来源分析。')
p.write_text(s,encoding='utf-8')
assert '的下标' not in next(l for l in s.splitlines() if l.startswith('$$ L'))
print('Review findings resolved without changing formal experiment metrics.')
