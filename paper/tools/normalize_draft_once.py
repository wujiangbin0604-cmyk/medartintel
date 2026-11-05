from pathlib import Path
P=Path(__file__).resolve().parents[1]
f=P/'draft/ECG_AI_课程论文初稿.md'
s=f.read_text(encoding='utf-8')
repeats=[
'划分还按V注释数是否达到100分层并约束留出V数量；已用于探索的记录100、200固定留在训练侧，未按模型成绩反复选择分区。',
'平滑方案对逆频率开平方后按权重均值归一化，截断方案先将原始逆频率截到10再按均值归一化；',
'另一个需要关注的事实是，该CNN最佳检查点在验证集上的Macro-F1仅0.6630，明显低于测试集0.9865。验证与测试患者及类别构成不同，分数高低不必同向；这种差异进一步表明，单个较高测试分数不足以证明对未知患者的稳定表现。',
]
for text in repeats:
    while text+text in s: s=s.replace(text+text,text)
f.write_text(s,encoding='utf-8')
b=P/'tools/build_paper.py'; t=b.read_text(encoding='utf-8')
start=t.find('    s=s.replace('); end=t.find('    weight=')
if start!=-1: t=t[:start]+t[end:]; b.write_text(t,encoding='utf-8')
print('Authoring corrections finalized; repeated builds now preserve manuscript text.')
