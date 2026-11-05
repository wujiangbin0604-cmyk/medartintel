# 已核验参考文献

核验日期：2026年11月5日。以下编号固定为1—10，供正文顺序编码引用；正式文稿仍须检查首次出现顺序。只使用原始研究、作者所属机构存档及官方数据资源。部分出版商全文受到访问限制，已明确区分书目信息核验、摘要核验和全文阅读；未声称完成无法访问的全文审阅。

## 可直接用于文末的GB/T 7714条目

[1] MOODY G B, MARK R G. The impact of the MIT-BIH Arrhythmia Database[J]. IEEE Engineering in Medicine and Biology Magazine, 2001, 20(3): 45-50. DOI: 10.1109/51.932724.

[2] GOLDBERGER A L, AMARAL L A N, GLASS L, et al. PhysioBank, PhysioToolkit, and PhysioNet: components of a new research resource for complex physiologic signals[J]. Circulation, 2000, 101(23): e215-e220. DOI: 10.1161/01.CIR.101.23.e215.

[3] MOODY G, MARK R. MIT-BIH Arrhythmia Database version 1.0.0[DB/OL]. PhysioNet, 2005[2026-11-05]. https://physionet.org/content/mitdb/1.0.0/. DOI: 10.13026/C2F305.

[4] DE CHAZAL P, O'DWYER M, REILLY R B. Automatic classification of heartbeats using ECG morphology and heartbeat interval features[J]. IEEE Transactions on Biomedical Engineering, 2004, 51(7): 1196-1206. DOI: 10.1109/TBME.2004.827359.

[5] BREIMAN L. Random forests[J]. Machine Learning, 2001, 45(1): 5-32. DOI: 10.1023/A:1010933404324.

[6] KIRANYAZ S, INCE T, GABBOUJ M. Real-time patient-specific ECG classification by 1-D convolutional neural networks[J]. IEEE Transactions on Biomedical Engineering, 2016, 63(3): 664-675. DOI: 10.1109/TBME.2015.2468589.

[7] ACHARYA U R, OH S L, HAGIWARA Y, et al. A deep convolutional neural network model to classify heartbeats[J]. Computers in Biology and Medicine, 2017, 89: 389-396. DOI: 10.1016/j.compbiomed.2017.08.022.

[8] MONDÉJAR-GUERRA V, NOVO J, ROUCO J, et al. Heartbeat classification fusing temporal and morphological information of ECGs via ensemble of classifiers[J]. Biomedical Signal Processing and Control, 2019, 47: 41-48. DOI: 10.1016/j.bspc.2018.08.007.

[9] CHAWLA N V, BOWYER K W, HALL L O, et al. SMOTE: synthetic minority over-sampling technique[J]. Journal of Artificial Intelligence Research, 2002, 16: 321-357. DOI: 10.1613/jair.953.

[10] PAN J, TOMPKINS W J. A real-time QRS detection algorithm[J]. IEEE Transactions on Biomedical Engineering, 1985, BME-32(3): 230-236. DOI: 10.1109/TBME.1985.325532.

## 核验记录与可支持的论断

| 编号 | 一手来源及核验程度 | 本文可支持的论断与边界 |
|---|---|---|
| [1] | [PhysioNet官方条目及原论文引文](https://physionet.org/content/mitdb/1.0.0/)，核实作者、题名、刊年、卷期页码、DOI。官方链接的MIT旧站PDF无法访问；[作者原文存档](https://georgebmoody.com/publications/mitdb-embs-2001.pdf)有可检索原文，直接抓取超时。 | MIT-BIH建立共享评估材料，支持算法之间可复核的比较。数据库技术细节优先另引[3]，不以此替代本项目样本审计。 |
| [2] | [NLM书目与作者摘要](https://pubmed.ncbi.nlm.nih.gov/10851218/)、[PhysioNet官方引用说明](https://archive.physionet.org/physiotools/software-index.shtml)，核实书目信息与资源组成。AHA全文页面403。 | PhysioBank数据、PhysioToolkit分析软件及PhysioNet传播交流构成相互关联的开放研究资源。此为2000年原始资源论文，不能据此描述当前所有平台功能。 |
| [3] | [PhysioNet数据发布者页面](https://physionet.org/content/mitdb/1.0.0/)，正文直接可读，核实版本1.0.0及版本DOI。 | 48条约半小时双通道记录、47名受试者、360 Hz；201与202来自同一受试者，应同分区。部分记录经选择纳入罕见心律失常，样本比例不代表临床患病率。 |
| [4] | [作者机构TCD原文存档及摘要](https://www.tara.tcd.ie/items/ddf100f9-52e5-4772-b993-18eb190541a0)、[NLM书目](https://pubmed.ncbi.nlm.nih.gov/15248536/)，核实书目与方法摘要。 | 研究采用44条非起搏记录、五类分组，以及形态与心拍间期特征；分别选择模型配置与独立评估。摘要提及ANSI/AAMI EC57:1998，不能声称已审查标准全文。 |
| [5] | [Springer出版商页面](https://link.springer.com/article/10.1023/A:1010933404324)，作者、出版年、卷页、DOI与摘要直接可读；期号由出版记录核对。 | 随机森林组合含随机性的决策树，随机特征选择是其机制的一部分。不能据此预言本项目一定优于CNN。 |
| [6] | [NLM书目与作者摘要](https://pubmed.ncbi.nlm.nih.gov/26285054/)，核实作者、期刊、卷期页码、DOI和患者特异训练设置。IEEE跳转受到机器人验证。 | 1D-CNN可联合学习特征和分类器。该研究采用患者特异数据，不能与本文严格跨受试者划分的指标直接排名。正式卷期年为2016，2015为在线发表年份。 |
| [7] | [NLM书目与作者摘要](https://pubmed.ncbi.nlm.nih.gov/28869899/)、[Elsevier论文页面](https://www.sciencedirect.com/science/article/pii/S0010482517302810)，核实7名作者、卷页、DOI及五类CNN设计。 | 该研究比较类别平衡处理与原始不平衡数据，说明应报告类别分布及训练策略。不能将其增强后的指标当作本文实验，也不能据摘要推断其与本文划分一致。 |
| [8] | [Elsevier出版商检索内容](https://www.sciencedirect.com/science/article/pii/S1746809418301976)、[作者机构RUC存档](https://hdl.handle.net/2183/34480)，核实作者、2019年、47卷41-48页、DOI及形态/间期SVM集成方法。直接页面访问403，核验依据为可检索的作者原稿与出版元数据。 | ECG形态与相邻心拍时间间隔可以共同建模，为未来引入RR上下文提供方法依据；本文未实现该SVM集成。 |
| [9] | [JAIR官方页面](https://www.jair.org/index.php/jair/article/view/10302)、[期刊原文PDF](https://www.jair.org/index.php/jair/article/download/10302/24590)，核实作者、卷页、年份、DOI，已读摘要与方法相关段落。 | 类别不平衡时单一Accuracy可能掩盖少数类错误；SMOTE是在特征空间生成少数类合成样本的方法。本项目未采用SMOTE，不得列入已完成方法。 |
| [10] | [NLM书目](https://pubmed.ncbi.nlm.nih.gov/3997178/)、[IEEE出版商摘要与元数据](https://ieeexplore.ieee.org/abstract/document/4122029/metrics)，核实作者、1985年、卷期页码、DOI及自动QRS检测任务。 | 自动QRS检测是可独立评估的处理环节；可用于本文未来工作说明。本文当前使用参考标注切拍，不能将自动检测写成已实现。 |

## 引文使用检查

- 本表的“核验”指对应级别的存在性、书目信息或可读方法核验，不表示每篇全文均已阅读。
- 正文仅概括与课程论文有关的方法，不照抄摘要，不摘录外部论文图表。
- [3]的DB/OL条目使用版本发布日期2005和本次访问日期2026-11-05；不能把2005误作最初数据库建成年份。
- 作者人数超过3人的文末条目列前3位并使用et al.，全体作者可在链接的元数据追溯。
- 没有引用未读取原文的AAMI标准条目；标签映射要以项目源码和[4]共同说明。
