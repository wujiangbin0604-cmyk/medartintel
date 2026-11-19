# 节律融合与选择性分类：一手来源核查

核查日期：2026-11-18（Asia/Shanghai）。本文件记录方法依据与主张边界，不报告本项目尚未完成的实验结果。所有外部来源均为数据库官方文档、原始研究论文或软件官方文档；下文“实施建议”是本项目设计判断。

## 1. 数据单位、心拍事件与受试者分组

MIT-BIH Arrhythmia Database 1.0.0 包含 48 条约半小时的双通道记录，来自 47 位受试者，采样率为每通道 360 Hz。数据集适合开发与比较心律失常分析方法，但其数据库内结果不构成临床有效性的独立证明。[PhysioNet 数据集官方页面](https://physionet.org/content/mitdb/1.0.0/)

官方目录明确说明：201 和 202 来自同一男性受试者；102、104、107、217 含起搏心拍。由此，将后四条排除后保留 44 条记录，并合并 201/202，可以形成 43 个受试者组。这里的 43 是依据官方身份说明作出的计数推导；31/6/6 划分是本项目已有锁定协议，并非 PhysioNet 规定的唯一划分。数据库记录还可能存在模拟磁带速度变化，间期分析应承认这一测量限制。[PhysioNet 官方目录 Introduction，Selection criteria / Analog recording and playback / Digitization](https://physionet.org/physiobank/database/html/mitdbdir/intro.htm)

PhysioNet 区分 beat 与 non-beat 标注。beat 符号包括 `N,L,R,B,A,a,J,S,V,r,F,e,j,n,E,/,f,Q,?`；`x`（未下传 P 波）、`!`（心室扑动波）、`+`（节律改变）、`|`（类 QRS 伪迹）等属于 non-beat。RR 的事件集合不能简单等于全部注释位置，也不能先缩减为 N/S/V/F 目标类。[PhysioBank 官方 Annotation Codes](https://archive.physionet.org/physiobank/annotations.shtml)

WFDB 的 `rdann(record_name, 'atr')` 读取注释，`sample` 与 `symbol` 分别提供位置和符号。只读本地原始注释即可构造历史事件流，无须修改注释文件。[WFDB 官方 I/O 文档](https://wfdb.readthedocs.io/en/latest/io.html)

**实施建议：**先以固定 beat 符号集合识别“这是心拍事件”，再仅把有序位置传入 RR 计算器。符号在此只用于区分事件种类，不应将细分类别、AAMI 标签、`aux_note`、患者 ID 或记录 ID 编码为输入。`Q`、`/`、`f` 等非目标心拍仍应保留为计算相邻间期的事件；记录边界应重置全部历史。建议把这一事件定义与模型标签映射分开保存。

## 2. 形态与 RR 融合已有先例

de Chazal、O'Dwyer 和 Reilly（2004）在 44 条非起搏记录上研究 ECG 形态与心拍间期特征，并将配置选择与独立评价分开。这足以证明“联合形态和节律信息”是已有研究思路。其数据划分、特征和分类器不同于本项目，不能把论文指标拿来替代本项目复现结果。[原始论文题录与摘要，DOI: 10.1109/TBME.2004.827359](https://pubmed.ncbi.nlm.nih.gov/15248536/)

Wang 等（2021）的原始研究已把 CWT-CNN 学到的 64 维表示与四个 RR 特征拼接，送入全连接分类器。其 Section 3.4 明确包含 post-RR，即当前拍与下一拍之间的间期。因此，本项目的历史 RR 方案与该方案的信息可用条件不同，不宜将两者指标直接比较，也不能宣称 CNN+RR 拼接为首次提出。[Automatic ECG Classification Using Continuous Wavelet Transform and Convolutional Neural Network，Entropy 23(1):119，DOI: 10.3390/e23010119](https://pmc.ncbi.nlm.nih.gov/articles/PMC7831114/)

Zahid、Kiranyaz 和 Gabbouj（2022）也研究跨患者分类中将 RR 时间特征注入学习到的形态特征，使用的是 Self-ONN，进一步表明该融合方向并非本项目原创。[作者原始预印本：Global ECG Classification by Self-Operational Neural Networks with Feature Injection](https://arxiv.org/abs/2204.03768)

**可成立的项目贡献类型：**沿用现有 CNN 的轻量双分支实现；明确仅使用当前及历史事件的 RR 设计；保持患者独立划分；同预算消融及打乱对照；逐拍追溯、患者级异质性分析；把真实模型与教育平台连接。是否存在额外实证收益，必须由本项目全部完成折和种子的结果决定。仅增加网络容量或仅有单折改善，不足以证明节律信息有效。

**离线边界：**RR 仅用历史事件，并不自动使整套系统成为实时因果系统。现有心拍窗口包含 R 峰之后的波形，若沿用零相位滤波，还涉及双向信号处理。应明确为“专家定位心拍条件下的离线分类”，不声称未标注连续 ECG 的端到端异常发现。

## 3. 分组交叉验证与结果解释

`StratifiedGroupKFold` 的官方定义是在组互斥条件下尽量保持类比例；每个组在一个交叉验证循环中只出现在一个外层评价折。受试者组很少、类分布集中时，无法保证每折拥有相近类别构成或相同患者数。软件的分层策略不消除患者相关性，也不创造独立受试者。[scikit-learn 官方 StratifiedGroupKFold 文档](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html)

**实施建议：**将原训练和验证受试者合为开发池，排除原正式测试患者；预先保存外层 SGKF 的样本 ID 和患者组。每折另外划分组互斥的内部早停患者；只在实际训练患者拟合波形标准化、RR 填充和缩放、类别权重。外层评价患者不能参与 epoch 选择。若阶段 B 需选择阈值，可在外层训练侧保留独立校准患者，或做严格的训练侧交叉拟合。外层预测应最后使用一次，不以结果反复调阈值。

本项目应同时报告逐拍汇总和患者级汇总，并列出 S/F 的样本数与贡献患者数。若计算 bootstrap 区间，应以患者组为抽样单位，同一次抽样中保留该患者全部心拍；多随机种子不是新增独立患者。不把同一患者的多拍用于普通独立样本显著性检验。

## 4. 最大分数、信息熵与拒识

El-Yaniv 和 Wiener（2010）将拒识分类视为覆盖率与错误风险之间的权衡，risk–coverage 是该问题的基本评价对象。[JMLR 原始论文：On the Foundations of Noise-free Selective Classification](https://jmlr.org/papers/v11/el-yaniv10a.html)

Geifman 和 El-Yaniv（2017）研究训练后深度网络的选择性分类，使用最大 softmax 响应等分数构造拒识机制。该论文中的统计保证有特定算法与条件；只实现分数分位数阈值并不能继承其风险保证。[NeurIPS 原始论文：Selective Classification for Deep Neural Networks](https://papers.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html)

Guo 等（2017）在其研究数据上发现现代神经网络的分数可能未校准，讨论了温度缩放等校准方法。这支持本项目把 softmax 和熵称为不确定性代理，而不能直接称为“正确概率”或“临床风险”。论文的校准效果也不能不经验证地推广到本项目 ECG 数据。[ICML/PMLR 原始论文：On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html)

以下为本项目建议固定的定义，均以心拍作为报告中的预测单位，并另行分患者汇总：

设类别分数向量为 \(p_i\)，预测为 \(\hat y_i=\arg\max_k p_{ik}\)，错误指示为 \(e_i=1[\hat y_i\ne y_i]\)。

- 最大分数不确定性：\(u_i^{max}=1-\max_k p_{ik}\)。
- 信息熵：\(u_i^{H}=-\sum_k p_{ik}\log p_{ik}\)，单位 nat。若除以 \(\log K\) 归一化，需要显式标记。
- 接受集合：\(A_\tau=\{i:u_i\le\tau\}\)，包括等号的规则需固定并保存。
- Coverage：\(|A_\tau|/n\)。
- 接受风险：\(\sum_{i\in A_\tau}e_i/|A_\tau|\)。接受数为零时该值未定义，不能填 0。
- 拒识比例：\(1-|A_\tau|/n\)。
- 被拒识心拍真实错误比例：\(\sum_{i\notin A_\tau}e_i/(n-|A_\tau|)\)。无拒识时未定义。
- 类别接受率：\(\#\{y_i=k,i\in A_\tau\}/\#\{y_i=k\}\)。
- 保留预测 Precision：接受样本中的 \(TP_k/(TP_k+FP_k)\)。
- 全类别支持分母 Recall：接受且预测正确的该类样本数，除以全部真实该类样本数；拒识样本计入未覆盖的真实支持。
- 接受子集 Recall：同样的分子，除以被接受的真实该类样本数。若同时给出，必须与上一指标明确区分。

风险曲线可在外层患者的冻结预测上作描述性扫描，但评价后的曲线不能再用于选择部署阈值。采用校准池分位数预设“目标 coverage”时，实际外层 coverage 可能因患者分布变化而偏离目标。阈值来源、校准患者、目标覆盖率、阈值数值及 tie 规则都应随模型保存。

## 5. 报告文字边界

1. 如果 A2 优于 A0，但 A3 与 A2 接近，优先讨论额外容量、优化轨迹或残留分布结构的影响，不立即归因于匹配节律。
2. 如果逐拍 Macro-F1 提升但患者等权结果下降，必须同时报告，不能称为跨患者稳定改善。
3. S 类 Recall 增加需要同时给出 Precision、样本支持与患者数；F 类患者少时，不把少量病例的效果概括为普遍规律。
4. 拒识后的接受样本准确率不能替代全部心拍的表现；必须同步展示覆盖率及各类被拒比例。
5. 本文件未验证外部临床场景，未验证设备外分布、自动 R 峰定位或前瞻性医疗流程。不得把教育平台预测展示称为诊断系统。

## 6. 引用元数据

- Moody G, Mark R. MIT-BIH Arrhythmia Database (version 1.0.0). PhysioNet; 2005. DOI: [10.13026/C2F305](https://doi.org/10.13026/C2F305).
- de Chazal P, O'Dwyer M, Reilly RB. Automatic classification of heartbeats using ECG morphology and heartbeat interval features. IEEE Transactions on Biomedical Engineering. 2004;51(7):1196–1206. DOI: [10.1109/TBME.2004.827359](https://doi.org/10.1109/TBME.2004.827359).
- Wang T, Lu C, Sun Y, Yang M, Liu C, Ou C. Automatic ECG Classification Using Continuous Wavelet Transform and Convolutional Neural Network. Entropy. 2021;23(1):119. DOI: [10.3390/e23010119](https://doi.org/10.3390/e23010119).
- Zahid MU, Kiranyaz S, Gabbouj M. Global ECG Classification by Self-Operational Neural Networks with Feature Injection. Author preprint; 2022. [arXiv:2204.03768](https://arxiv.org/abs/2204.03768).
- El-Yaniv R, Wiener Y. On the Foundations of Noise-free Selective Classification. Journal of Machine Learning Research. 2010;11(53):1605–1641. [Original paper](https://jmlr.org/papers/v11/el-yaniv10a.html).
- Geifman Y, El-Yaniv R. Selective Classification for Deep Neural Networks. Advances in Neural Information Processing Systems 30; 2017. [Original proceedings](https://papers.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html).
- Guo C, Pleiss G, Sun Y, Weinberger KQ. On Calibration of Modern Neural Networks. Proceedings of ICML. PMLR. 2017;70:1321–1330. [Original proceedings](https://proceedings.mlr.press/v70/guo17a.html).
