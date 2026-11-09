# MIT-BIH 心拍分类课程项目：完整实验报告

> 本报告依据已保存的数据、配置、预测 CSV、指标 JSON、训练日志及五折分组交叉验证产物，展示模型评估、结果核验和误分类分析。

## 摘要

本项目基于 PhysioNet MIT-BIH Arrhythmia Database，检查 44 条非起搏记录，使用按受试者隔离的固定 train/validation/test 划分，完成 N/V 二分类及 N/S/V/F 四分类。三种已有模型为 Logistic Regression、Random Forest 和浅层 1D-CNN。保存的预测 CSV 重新计算后，全部 Accuracy、宏 Precision/Recall/F1 与原指标 JSON 一致（容差 `1e-10`），六个模型的混淆矩阵逐格一致。N/V CNN 的测试 Accuracy、Macro-F1、V Recall 分别为 0.9957、0.9865、0.9905。四分类 CNN Accuracy 为 0.7690，Macro-F1 为 0.4460；CNN 测试 S Recall 为 0.000，F Recall 为 0.0027。探索性患者分组 CV 中，RF Macro-F1 折均值约 0.417，CNN 约 0.356；同时分析少数类覆盖和受试者集中度。

**关键词：** MIT-BIH；心电图；AAMI；受试者独立划分；类别不平衡；心拍分类

## 第一章 绪论

心电图（ECG）包含反映心脏电活动的时序信号，自动化信号分析可用于研究心拍分类任务。公开、有专家复核标注的数据集允许开发者进行可复现的算法实验；MIT-BIH Arrhythmia Database 是常用公开资源，包含约半小时、双导联记录和逐拍参考标注。[1–2] 本项目的目标是学习医学信号读取、标签构造、患者独立划分、基础机器学习/深度学习训练和可靠评估流程。

项目工作包括原始数据探索、波形与标签可视化、44 条非起搏记录处理、N/V 二分类、N/S/V/F 四分类、三种基线模型比较、类别权重分析、受试者级错误回顾及患者分组交叉验证。当前报告对既有实验做独立指标核验与诊断整合，不重训模型。

## 第二章 数据集与数据探索

### 2.1 数据集及记录范围

PhysioNet 页面记载 MIT-BIH 数据集由 48 条双通道、约半小时记录组成，来源于 47 位受试者，采样率为 360 Hz；记录 201 与 202 来自同一人。[1] 项目保留原始数据文件，只用记录 100、200、103、105、…等预先锁定的 44 条非起搏记录开展分类，排除 102、104、107、217。排除记录仍保留在原始数据目录，没有删除或改写。项目划分方案、原始文件校验和及排除理由可查 `data/processed/mitdb44_nsvf_v1/split_manifest.csv` 和 `results/download_manifest.csv`。

数据库注释包括逐拍符号，也包括节律或信号质量等非心拍符号；PhysioNet 对这些代码分别说明。[3] 本项目不把非心拍符号推断成心拍类别。

### 2.2 原始符号与 AAMI 映射

映射参考 ANSI/AAMI EC57 的五类心拍评估框架，以及 de Chazal 等人基于 MIT-BIH 44 条非起搏记录开展五类分类的公开研究；项目采用的逐符号映射在代码中显式列出并可逐项复核。[4–5] 原始符号与分组保持可追溯：N 组为 `N/L/R/e/j`；S 组为 `A/a/J/S`；V 组为 `V/E`；F 组为 `F`；Q 组为 `/、f、Q`。四分类只使用 N/S/V/F。非心拍注释、Q 组、未知或未映射注释均不进入四分类；原始 `.atr` 和 `original_label` 保留。这里的 N 是 AAMI 标签分组，包含束支传导阻滞及部分逸搏符号。

### 2.3 四分类有效数据分布

以下数量是通过窗口边界、信号质量守卫和类别筛选后，实际进入四分类 NPZ 的样本数，不是数据库中全部原始 annotation 数。

| 类别 | 有效心拍数 | 占比% |
| --- | --- | --- |
| N | 89577 | 89.4741 |
| S | 2761 | 2.7578 |
| V | 6977 | 6.9690 |
| F | 800 | 0.7991 |

![类别心拍数与受试者覆盖](../../figures/12_final_report/02_class_support_and_subject_coverage.png)

![跨患者类别集中度](../../figures/11_four_class_diagnosis/top_subject_class_concentration.png)

跨受试者覆盖如下。有效受试者数为心拍份额 Shannon 熵转换得到的 `2^H` 描述量，只用于表现集中程度，不等于独立患者样本数或统计功效。

| split | class | subjects_with_class | subjects_total | coverage_pct | sample_count | top_subject_id | top_subject_share_pct | top3_subject_share_pct | effective_subject_count_2pow_entropy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 训练集 | N | 31 | 31 | 100.0000 | 65436 | subject_201_202 | 5.6146 | 13.7233 | 30.2614 |
| 训练集 | S | 23 | 31 | 74.1935 | 1347 | subject_209 | 28.4336 | 57.4610 | 9.6749 |
| 训练集 | V | 23 | 31 | 74.1935 | 4747 | subject_200 | 17.3162 | 38.1925 | 12.5718 |
| 训练集 | F | 10 | 31 | 32.2581 | 411 | subject_213 | 88.0779 | 94.1606 | 1.7948 |
| 验证集 | N | 6 | 6 | 100.0000 | 11854 | subject_215 | 26.7926 | 66.4080 | 5.3573 |
| 验证集 | S | 5 | 6 | 83.3333 | 1404 | subject_232 | 98.0057 | 99.3590 | 1.1313 |
| 验证集 | V | 4 | 6 | 66.6667 | 1069 | subject_233 | 77.1749 | 96.5388 | 2.0818 |
| 验证集 | F | 4 | 6 | 66.6667 | 18 | subject_233 | 61.1111 | 94.4444 | 2.8290 |
| 测试集 | N | 6 | 6 | 100.0000 | 12287 | subject_212 | 22.2430 | 58.0451 | 5.8765 |
| 测试集 | S | 3 | 6 | 50.0000 | 10 | subject_219 | 70.0000 | 100.0000 | 2.2296 |
| 测试集 | V | 5 | 6 | 83.3333 | 1161 | subject_208 | 84.8407 | 99.6555 | 1.7180 |
| 测试集 | F | 2 | 6 | 33.3333 | 371 | subject_208 | 99.7305 | 100.0000 | 1.0188 |

测试集中 S 只有 10 拍、覆盖 3 个患者组；F 有 371 拍但 99.73% 来自 subject_208。训练集 F 有 411 拍，其中 88.08% 来自 subject_213。验证集 S 有 1,404 拍，其中 98.01% 来自 subject_232。即使某类总拍数看似可用，若主要来自极少患者，模型仍可能学习到患者/记录特征，而不是可泛化的类别形态。

### 2.4 信号与形态观察

所有有效心拍均使用 MLII 导联、360 Hz 采样；观察图保留记录编号、专家标注位置和记录内时间。N/V 单心拍任务表现较好，但四分类中 S/F 数量少、跨患者异质性更明显。N/S/F 的标签差异不能仅靠一段短单拍波形完整表达；相邻 RR 间期、相邻心拍序列和受试者间差异可能提供上下文。四类错误样例见第五、六章及图 11。

![项目实验流程](../../figures/12_final_report/10_project_workflow.png)

## 第三章 数据预处理与数据集构建

### 3.1 数据读取与滤波

WFDB 读取 `.dat` 信号、`.hea` 头信息与 `.atr` 专家注释；采样率、导联名、注释样点、原始符号和记录内时间保存在元数据中。导联通过头文件导联名称选择 MLII，而不是默认通道 0；项目所含的 44 条记录全部找到 MLII。实际滤波为 4 阶 Butterworth 带通，0.5–40.0 Hz，SOS 零相位双向 `sosfiltfilt`（`sosfiltfilt`），两端各使用 5.0 s 保护区并按配置排除窗口。 配置细节见 `data/processed/mitdb44_nsvf_v1/processing_config.json` 与 `src/preprocessing/filters.py`。信号经过滤波后，以专家标注样点为中心截取前 0.3 秒和后 0.4 秒，360 Hz 下为 253 个采样点，中心索引为 108。超出边界、滤波边缘/信号间隙守卫内的窗口不纳入样本。

### 3.2 标准化与标签

归一化参数只由训练划分拟合，再用于验证和测试；传统模型的 StandardScaler 同样只在各自训练数据拟合。AAMI 标签映射在 `src/labels.py` 中显式维护。N/V 任务将 N 与 V 映射为二类；四分类使用 N/S/V/F。对 201 与 202 使用共同受试者组标识 `subject_201_202`。

### 3.3 患者独立划分与防泄漏

N/V 与 N/S/V/F 复用相同 44 条记录的受试者分区；本轮从两份 `split_manifest.csv` 逐记录重新比对，映射一致。训练、验证、测试受试者集合两两不交；201/202 被合并且属于同一集合。每个有效样本的 `subject_id`、`record_id` 和 `sample_id` 可从元数据追溯。当前实验不做随机心拍拆分。

四分类样本数按 split 与类别的核验表如下；`subject_count`、`record_count` 为该类别真正出现的受试者数和记录数，而不是 split 总数。

| split | class | sample_count | share_of_split_pct | subject_count | record_count | split_subject_total | split_record_total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 训练集 | N | 65436 | 90.9579 | 31 | 32 | 31 | 32 |
| 训练集 | S | 1347 | 1.8724 | 23 | 24 | 31 | 32 |
| 训练集 | V | 4747 | 6.5985 | 23 | 24 | 31 | 32 |
| 训练集 | F | 411 | 0.5713 | 10 | 11 | 31 | 32 |
| 验证集 | N | 11854 | 82.6351 | 6 | 6 | 6 | 6 |
| 验证集 | S | 1404 | 9.7874 | 5 | 5 | 6 | 6 |
| 验证集 | V | 1069 | 7.4521 | 4 | 4 | 6 | 6 |
| 验证集 | F | 18 | 0.1255 | 4 | 4 | 6 | 6 |
| 测试集 | N | 12287 | 88.8495 | 6 | 6 | 6 | 6 |
| 测试集 | S | 10 | 0.0723 | 3 | 3 | 6 | 6 |
| 测试集 | V | 1161 | 8.3954 | 5 | 5 | 6 | 6 |
| 测试集 | F | 371 | 2.6828 | 2 | 2 | 6 | 6 |

各患者的类别样本数完整表：`results/classification/final_verified_subject_class_counts.csv`。完整分布表：`results/classification/final_verified_split_class_counts.csv`。

### split_class_counts.csv 错误修复记录

虽然 `src/datasets/build.py` 当前统计代码已按类别内 `subject_id`/`record_id` 去重，二分类旧派生 CSV 仍未更新：原表把 V 类患者/记录数写成 split 总数（训练为 31/32，实际 23/24；验证为 6/6，实际 4/4；测试为 6/6，实际 5/5）。本轮已把旧表原样存档至 `reports/final/nv44_v1_split_class_counts_before_repair.csv`，再由 metadata 重生成 `data/processed/mitdb44_nv_v1/split_class_counts.csv`；四分类表核验时已与 metadata 一致。未修改 NPZ、样本、标签、划分或模型权重。

| 任务 | 当前 CSV 与 metadata 一致 | 存档旧 CSV 与 metadata 一致 | 本轮发现并修正旧 CSV | 修正后核验通过 | 旧值存档路径 |
| --- | --- | --- | --- | --- | --- |
| N/V | True | False | True | True | reports/final/nv44_v1_split_class_counts_before_repair.csv |
| N/S/V/F | True | True | False | True |  |

## 第四章 模型设计

本项目对比 Logistic Regression、Random Forest 与 1D-CNN。超参数从各任务正式配置 JSON 读取，不凭记忆补写。Smoke Test 文件保留在结果目录；正式模型使用已有正式训练结果。

### N/V 配置

随机种子为 `20261027`。LR 参数：`C=1.0`、`class_weight=balanced`、`solver=lbfgs`、`max_iter=1000`；StandardScaler 仅在训练样本拟合。

RF 参数：`n_estimators=100`、`max_depth=18`、`min_samples_leaf=2`、`max_features=sqrt`、`class_weight=balanced_subsample`、`max_samples=0.8`。

1D-CNN 结构：`Conv1d(1,16,7)-ReLU-MaxPool2-Conv1d(16,32,5)-ReLU-MaxPool2-Conv1d(32,64,3)-ReLU-AdaptiveAvgPool1-Linear`。损失为 `CrossEntropyLoss`，优化器 `Adam`，学习率 `0.001`，权重衰减 `1e-05`，batch size `256`，最多 `25` 个 epoch，patience `5`，按验证集 `validation macro-F1` 早停。配置来源：`results/classification/nv44_v1/config.json`。

正式日志显示三种模型均完成；CNN 在 17 个 epoch 停止，验证 Macro-F1 最佳 epoch 为 12（0.6630），运行设备 `cpu`。检查点与完整 epoch 日志分别保存在 `checkpoints/nv44_v1/formal/cnn/` 和 `checkpoints/nv44_v1/formal/cnn/cnn_training_history.csv`。
### N/S/V/F 配置

随机种子为 `20261027`。LR 参数：`C=1.0`、`class_weight=balanced`、`solver=lbfgs`、`max_iter=1000`；StandardScaler 仅在训练样本拟合。

RF 参数：`n_estimators=100`、`max_depth=18`、`min_samples_leaf=2`、`max_features=sqrt`、`class_weight=balanced_subsample`、`max_samples=0.8`。

1D-CNN 结构：`Conv1d(1,16,7)-ReLU-MaxPool2-Conv1d(16,32,5)-ReLU-MaxPool2-Conv1d(32,64,3)-ReLU-AdaptiveAvgPool1-Linear`。损失为 `CrossEntropyLoss`，优化器 `Adam`，学习率 `0.001`，权重衰减 `1e-05`，batch size `256`，最多 `25` 个 epoch，patience `5`，按验证集 `validation macro-F1` 早停。配置来源：`results/classification/nsvf44_v1/config.json`。

正式日志显示三种模型均完成；CNN 在 16 个 epoch 停止，验证 Macro-F1 最佳 epoch 为 11（0.4735），运行设备 `cpu`。检查点与完整 epoch 日志分别保存在 `checkpoints/nsvf44_v1/formal/cnn/` 和 `checkpoints/nsvf44_v1/formal/cnn/cnn_training_history.csv`。

### 已保存模型权重只读核验

本轮使用 `joblib.load` 和 PyTorch `weights_only=True` 只读载入六个正式模型工件，检查类别索引、253 点输入长度、LR 标准化器、CNN checkpoint 中类别名/随机种子/最佳 epoch/验证 Macro-F1，并逐张量比较 CNN `cnn_best.pt` 与 `cnn_final_best.pt`。表中 LR 规模计数为系数数、RF 为树节点数、CNN 为 state_dict 张量值数量。核验不执行推理或训练；逐文件结果见 `results/classification/final_formal_model_artifact_audit.csv`。

| 任务 | 模型 | 类别 | 输入长度 | 规模计数 | 缩放器 | 最佳 epoch | 与配置及日志一致 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| N/V | Logistic Regression | N,V | 253 | 254 | StandardScaler | — | True |
| N/V | Random Forest | N,V | 253 | 56016 | none | — | True |
| N/V | 1D-CNN | N,V | 253 | 9058 | 训练折拟合参数（见处理配置） | 12 | True |
| N/S/V/F | Logistic Regression | N,S,V,F | 253 | 1016 | StandardScaler | — | True |
| N/S/V/F | Random Forest | N,S,V,F | 253 | 134326 | none | — | True |
| N/S/V/F | 1D-CNN | N,S,V,F | 253 | 9188 | 训练折拟合参数（见处理配置） | 11 | True |

评估报告包括 Accuracy、逐类 Precision/Recall/F1/Support、Macro-F1、Weighted-F1、Balanced Accuracy 和混淆矩阵。Macro-F1 让每类等权参与平均；Balanced Accuracy 为各真实类别 Recall 的均值；Weighted-F1 按真实支持数加权。少数类 Support 很小时，这些估计仍有较大不确定性。

## 第五章 N/V 二分类实验

N/V 是本项目主要分类实验。以下测试指标直接从三模型既有 `test_predictions_all_models.csv` 重新计算，并与原始指标 JSON 对照。

| 任务 | 模型 | 测试样本数 | Accuracy | Macro-F1 | Weighted-F1 | Balanced Accuracy |
| --- | --- | --- | --- | --- | --- | --- |
| N/V | Logistic Regression | 13448 | 0.8369 | 0.6961 | 0.8673 | 0.8675 |
| N/V | Random Forest | 13448 | 0.9835 | 0.9494 | 0.9838 | 0.9648 |
| N/V | 1D-CNN | 13448 | 0.9957 | 0.9865 | 0.9957 | 0.9934 |
| N/S/V/F | Logistic Regression | 13829 | 0.7423 | 0.3599 | 0.8015 | 0.5624 |
| N/S/V/F | Random Forest | 13829 | 0.9536 | 0.4656 | 0.9448 | 0.4748 |
| N/S/V/F | 1D-CNN | 13829 | 0.7690 | 0.4460 | 0.8431 | 0.4415 |

逐类指标（包括 Support）见下一表；完整混淆矩阵按真实类别为行、预测类别为列。

| 任务 | 模型 | 类别 | Support | Precision | Recall | F1 | 预测数 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| N/V | Logistic Regression | N | 12287 | 0.9892 | 0.8306 | 0.9030 | 10316 |
| N/V | Logistic Regression | V | 1161 | 0.3352 | 0.9044 | 0.4892 | 3132 |
| N/V | Random Forest | N | 12287 | 0.9945 | 0.9874 | 0.9909 | 12199 |
| N/V | Random Forest | V | 1161 | 0.8759 | 0.9423 | 0.9079 | 1249 |
| N/V | 1D-CNN | N | 12287 | 0.9991 | 0.9962 | 0.9976 | 12251 |
| N/V | 1D-CNN | V | 1161 | 0.9607 | 0.9905 | 0.9754 | 1197 |
| N/S/V/F | Logistic Regression | N | 12287 | 0.9804 | 0.7545 | 0.8528 | 9456 |
| N/S/V/F | Logistic Regression | S | 10 | 0.0042 | 0.6000 | 0.0083 | 1436 |
| N/S/V/F | Logistic Regression | V | 1161 | 0.3529 | 0.8303 | 0.4952 | 2732 |
| N/S/V/F | Logistic Regression | F | 371 | 0.1171 | 0.0647 | 0.0833 | 205 |
| N/S/V/F | Random Forest | N | 12287 | 0.9729 | 0.9871 | 0.9800 | 12467 |
| N/S/V/F | Random Forest | S | 10 | 0.0000 | 0.0000 | 0.0000 | 123 |
| N/S/V/F | Random Forest | V | 1161 | 0.8547 | 0.9121 | 0.8825 | 1239 |
| N/S/V/F | Random Forest | F | 371 | 0.0000 | 0.0000 | 0.0000 | 0 |
| N/S/V/F | 1D-CNN | N | 12287 | 0.9763 | 0.7718 | 0.8621 | 9713 |
| N/S/V/F | 1D-CNN | S | 10 | 0.0000 | 0.0000 | 0.0000 | 2630 |
| N/S/V/F | 1D-CNN | V | 1161 | 0.8545 | 0.9914 | 0.9179 | 1347 |
| N/S/V/F | 1D-CNN | F | 371 | 0.0072 | 0.0027 | 0.0039 | 139 |

### N/V 混淆矩阵

**N/V · Logistic Regression**

**N/V · Random Forest**

**N/V · 1D-CNN**

N/V CNN 的 Accuracy 为 0.9957、Macro-F1 为 0.9865、V Recall 为 0.9905。该结果是当前锁定患者测试集上的既有结果，不自动推广到其他医院、设备或人群。图 1 将其与四分类结果并列展示；图 9 比较 CNN 在 N、V 类上的逐类 Precision/Recall/F1。

![任务间模型 Accuracy 与 Macro-F1](../../figures/12_final_report/01_task_model_performance.png)

![CNN 二分类与四分类逐类指标](../../figures/12_final_report/09_cnn_binary_vs_multiclass_per_class.png)

## 第六章 N/S/V/F 四分类拓展实验

### 6.1 测试指标与混淆矩阵

四分类测试结果来自已查看的固定测试集，单独呈现以核验既有报告。测试 S 支持数为 10，F 为 371；N 有 12,287，V 有 1,161。RF Accuracy 高，但在此测试集上没有正确识别 S 与 F，故不能以 Accuracy 代表四类均衡识别能力。

| 任务 | 模型 | 测试样本数 | Accuracy | Macro-F1 | Weighted-F1 | Balanced Accuracy |
| --- | --- | --- | --- | --- | --- | --- |
| N/V | Logistic Regression | 13448 | 0.8369 | 0.6961 | 0.8673 | 0.8675 |
| N/V | Random Forest | 13448 | 0.9835 | 0.9494 | 0.9838 | 0.9648 |
| N/V | 1D-CNN | 13448 | 0.9957 | 0.9865 | 0.9957 | 0.9934 |
| N/S/V/F | Logistic Regression | 13829 | 0.7423 | 0.3599 | 0.8015 | 0.5624 |
| N/S/V/F | Random Forest | 13829 | 0.9536 | 0.4656 | 0.9448 | 0.4748 |
| N/S/V/F | 1D-CNN | 13829 | 0.7690 | 0.4460 | 0.8431 | 0.4415 |

### 四分类逐类指标

| 任务 | 模型 | 类别 | Support | Precision | Recall | F1 | 预测数 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| N/V | Logistic Regression | N | 12287 | 0.9892 | 0.8306 | 0.9030 | 10316 |
| N/V | Logistic Regression | V | 1161 | 0.3352 | 0.9044 | 0.4892 | 3132 |
| N/V | Random Forest | N | 12287 | 0.9945 | 0.9874 | 0.9909 | 12199 |
| N/V | Random Forest | V | 1161 | 0.8759 | 0.9423 | 0.9079 | 1249 |
| N/V | 1D-CNN | N | 12287 | 0.9991 | 0.9962 | 0.9976 | 12251 |
| N/V | 1D-CNN | V | 1161 | 0.9607 | 0.9905 | 0.9754 | 1197 |
| N/S/V/F | Logistic Regression | N | 12287 | 0.9804 | 0.7545 | 0.8528 | 9456 |
| N/S/V/F | Logistic Regression | S | 10 | 0.0042 | 0.6000 | 0.0083 | 1436 |
| N/S/V/F | Logistic Regression | V | 1161 | 0.3529 | 0.8303 | 0.4952 | 2732 |
| N/S/V/F | Logistic Regression | F | 371 | 0.1171 | 0.0647 | 0.0833 | 205 |
| N/S/V/F | Random Forest | N | 12287 | 0.9729 | 0.9871 | 0.9800 | 12467 |
| N/S/V/F | Random Forest | S | 10 | 0.0000 | 0.0000 | 0.0000 | 123 |
| N/S/V/F | Random Forest | V | 1161 | 0.8547 | 0.9121 | 0.8825 | 1239 |
| N/S/V/F | Random Forest | F | 371 | 0.0000 | 0.0000 | 0.0000 | 0 |
| N/S/V/F | 1D-CNN | N | 12287 | 0.9763 | 0.7718 | 0.8621 | 9713 |
| N/S/V/F | 1D-CNN | S | 10 | 0.0000 | 0.0000 | 0.0000 | 2630 |
| N/S/V/F | 1D-CNN | V | 1161 | 0.8545 | 0.9914 | 0.9179 | 1347 |
| N/S/V/F | 1D-CNN | F | 371 | 0.0072 | 0.0027 | 0.0039 | 139 |

### 四分类混淆矩阵

**N/S/V/F · Logistic Regression**

**N/S/V/F · Random Forest**

**N/S/V/F · 1D-CNN**

![四分类 CNN 主要误分类方向](../../figures/12_final_report/08_cnn_error_directions_descriptive.png)

主要错误方向及真实类内比例：

| 方向 | 错误数 | 真实类支持 | 该类错误比例 |
| --- | --- | --- | --- |
| N→S | 2626 | 12287 | 0.2137 |
| F→N | 216 | 371 | 0.5822 |
| F→V | 154 | 371 | 0.4151 |
| V→N | 4 | 1161 | 0.0034 |

常见测试错误包括 CNN 的 N→S 2,626 拍、F→N 216 拍、F→V 154 拍以及 V→N 4 拍。F 的 371 拍中，370 拍误判为 N 或 V；S 的 10 拍均未被 CNN 识别。波形图 11 为每个错误方向中，按该方向被预测类别概率的中位数选取的一个示例，避免挑选概率极端样本；图上同时列出四类概率、record、subject、原始符号及注释时间。

![带概率的四类典型错误心拍](../../figures/12_final_report/11_error_case_ecg_with_probabilities_descriptive.png)

样本编号、记录和导联、专家原始符号、时间及预测概率：

| sample_id | record_id | subject_id | lead_name | time_s | original_label | true_class | predicted_class | P(predicted_class) | all_class_probabilities |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 212:1427 | 212 | subject_212 | MLII | 914.292 | R | N | S | 0.571 | P(N)=0.38, P(S)=0.57, P(V)=0.02, P(F)=0.03 |
| 208:1482 | 208 | subject_208 | MLII | 871.544 | F | F | N | 0.668 | P(N)=0.67, P(S)=0.32, P(V)=0.00, P(F)=0.01 |
| 208:1293 | 208 | subject_208 | MLII | 754.314 | F | F | V | 0.906 | P(N)=0.05, P(S)=0.01, P(V)=0.91, P(F)=0.04 |
| 116:1799 | 116 | subject_116 | MLII | 1357.183 | V | V | N | 0.509 | P(N)=0.51, P(S)=0.41, P(V)=0.06, P(F)=0.02 |

示例样本可核对 [CSV](../../results/classification/nsvf44_v1/diagnosis/final_error_case_samples_descriptive_only.csv)。

### 6.2 类别权重消融

复用已有同一 CNN 权重策略实验：无权重、平方根逆频率、逆频率在原始 mean-one 向量截断为 10 后再归一、全逆频率。权重只由训练集标签计算；各版本按验证 Macro-F1 早停，所以验证集并非独立调参集。下表同时给出训练和验证 Macro-F1 与预测类别份额：

| strategy | split | sample_count | accuracy | macro_f1_present_classes | predicted_share_N | predicted_share_S | predicted_share_V | predicted_share_F |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 无权重 | 训练集 | 71941 | 0.9500 | 0.4368 | 95.0181 | 0.0000 | 4.9693 | 0.0125 |
| 无权重 | 验证集 | 14345 | 0.8519 | 0.3914 | 93.4611 | 0.0000 | 6.5389 | 0.0000 |
| 平方根逆频率 | 训练集 | 71941 | 0.9325 | 0.5082 | 91.1427 | 0.0000 | 6.9752 | 1.8821 |
| 平方根逆频率 | 验证集 | 14345 | 0.8335 | 0.3962 | 90.4845 | 0.0000 | 7.2848 | 2.2307 |
| 逆频率截断 10 | 训练集 | 71941 | 0.7387 | 0.5731 | 66.9618 | 23.6152 | 8.3541 | 1.0689 |
| 逆频率截断 10 | 验证集 | 14345 | 0.6590 | 0.4138 | 55.4827 | 18.3479 | 25.8836 | 0.2858 |
| 全逆频率 | 训练集 | 71941 | 0.7338 | 0.5255 | 67.0271 | 23.4970 | 7.0891 | 2.3867 |
| 全逆频率 | 验证集 | 14345 | 0.7185 | 0.4735 | 59.1774 | 19.4144 | 17.5113 | 3.8968 |

验证集逐类 Precision、Recall 与预测数量：

| strategy | class | support | predicted_count | precision | recall | f1 | predicted_share_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 无权重 | N | 11854 | 13407 | 0.8629 | 0.9760 | 0.9160 | 93.4611 |
| 无权重 | S | 1404 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 无权重 | V | 1069 | 938 | 0.6951 | 0.6099 | 0.6497 | 6.5389 |
| 无权重 | F | 18 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 平方根逆频率 | N | 11854 | 12980 | 0.8666 | 0.9490 | 0.9059 | 90.4845 |
| 平方根逆频率 | S | 1404 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 平方根逆频率 | V | 1069 | 1045 | 0.6746 | 0.6595 | 0.6670 | 7.2848 |
| 平方根逆频率 | F | 18 | 320 | 0.0063 | 0.1111 | 0.0118 | 2.2307 |
| 逆频率截断 10 | N | 11854 | 7959 | 0.9402 | 0.6313 | 0.7554 | 55.4827 |
| 逆频率截断 10 | S | 1404 | 2632 | 0.3723 | 0.6980 | 0.4856 | 18.3479 |
| 逆频率截断 10 | V | 1069 | 3713 | 0.2666 | 0.9261 | 0.4141 | 25.8836 |
| 逆频率截断 10 | F | 18 | 41 | 0.0000 | 0.0000 | 0.0000 | 0.2858 |
| 全逆频率 | N | 11854 | 8489 | 0.9631 | 0.6897 | 0.8038 | 59.1774 |
| 全逆频率 | S | 1404 | 2785 | 0.4693 | 0.9309 | 0.6240 | 19.4144 |
| 全逆频率 | V | 1069 | 2512 | 0.3272 | 0.7689 | 0.4591 | 17.5113 |
| 全逆频率 | F | 18 | 559 | 0.0036 | 0.1111 | 0.0069 | 3.8968 |

![权重策略验证 Precision–Recall](../../figures/12_final_report/04_weight_strategy_precision_recall.png)

![真实与预测类别份额](../../figures/12_final_report/05_weight_strategy_prediction_shares.png)

全逆频率权重让模型在验证集上更常预测 S/F，部分少数类 Recall 上升，但相应误报增加、Precision 下降；例如全逆频率 F Recall 只有约 0.111，F Precision 约 0.0036，而 F 预测数量远大于真实支持数。截断权重改善 S 识别，但该验证折仍未正确识别 F。无权重/平滑权重在 S/F 上又容易完全不预测。证据支持“权重改变了决策偏好且存在 Precision–Recall 权衡”；不支持“权重越大越好”或“权重完全无效”。权重比较的训练/验证结果详表见 `results/classification/nsvf44_v1/diagnosis/weight_strategy_train_val_metrics.csv`。

### 6.3 受试者分布及患者级表现

![按患者分层的测试表现](../../figures/12_final_report/07_subject_level_model_heatmap_descriptive.png)

四分类 CNN 的患者级指标如下；完整 2 个任务 × 3 模型的逐患者结果保存在 [CSV](../../results/classification/final_subject_test_metrics_descriptive_only.csv)。

| 受试者 | 记录编号 | 记录数 | 样本数 | Accuracy | Macro-F1(出现类别) | Support-N | Recall-N | Support-S | Recall-S | Support-V | Recall-V | Support-F | Recall-F |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| subject_111 | 111 | 1 | 2112 | 0.8859 | 0.5253 | 2111 | 0.8858 | 0.0000 | — | 1 | 1.0000 | 0.0000 | — |
| subject_116 | 116 | 1 | 2398 | 0.8636 | 0.6207 | 2288 | 0.8580 | 1.0000 | 0.0000 | 109 | 0.9908 | 0.0000 | — |
| subject_123 | 123 | 1 | 1509 | 0.9967 | 0.9992 | 1506 | 0.9967 | 0.0000 | — | 3 | 1.0000 | 0.0000 | — |
| subject_208 | 208 | 1 | 2936 | 0.8014 | 0.4486 | 1579 | 0.8670 | 2.0000 | 0.0000 | 985 | 0.9980 | 370.0000 | 0.0027 |
| subject_212 | 212 | 1 | 2733 | 0.3117 | 0.4753 | 2733 | 0.3117 | 0.0000 | — | 0 | — | 0.0000 | — |
| subject_219 | 219 | 1 | 2141 | 0.9267 | 0.4719 | 2070 | 0.9314 | 7.0000 | 0.0000 | 63 | 0.8889 | 1.0000 | 0.0000 |

缺少某类别真实样本时，该类 Recall 留空；患者 Macro-F1 只对该患者实际出现的类别取平均。因此不能把患者仅含 N 的分数与同时含 N/S/V/F 的患者当作同一支持结构解释。该汇总使用清晰区分的记录编号、记录数和样本数；患者级结果用于比较受试者之间的表现。

### 6.4 五折受试者分组交叉验证

已有 StratifiedGroupKFold 五折结果已读取复用，没有重跑训练。输入仅为原 train+validation 中的 37 个患者组、86,286 拍；正式测试集不读取。外层验证患者互斥，每个患者只在一个外层验证折；各折内标准化与类别权重由该折训练患者估计。CNN 早停进一步用外层训练患者中的内层患者独立划分，随后按内层最佳 epoch 在外层训练数据上重拟合。

| 模型 | folds | accuracy_mean | accuracy_std | macro_f1_mean | macro_f1_std | pooled_oof_accuracy | pooled_oof_macro_f1_present_classes | recall_N_mean | recall_S_mean | recall_V_mean | recall_F_mean | support_N_total | support_S_total | support_V_total | support_F_total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Logistic Regression | 5 | 0.6038 | 0.0908 | 0.3047 | 0.0377 | 0.6020 | 0.2931 | 0.6209 | 0.2497 | 0.5963 | 0.1481 | 77290 | 2751 | 5816 | 429 |
| Random Forest | 5 | 0.9011 | 0.0332 | 0.4173 | 0.0424 | 0.8999 | 0.4054 | 0.9446 | 0.0347 | 0.8046 | 0.0000 | 77290 | 2751 | 5816 | 429 |
| 1D-CNN | 5 | 0.6418 | 0.1870 | 0.3564 | 0.0624 | 0.6433 | 0.3535 | 0.6418 | 0.2447 | 0.8801 | 0.0632 | 77290 | 2751 | 5816 | 429 |

逐折支持数、Accuracy、Macro-F1 与 Recall：

| fold | 模型 | validation_subject_count | validation_sample_count | support_N | support_S | support_V | support_F | accuracy | macro_f1_present_classes | recall_N | recall_S | recall_V | recall_F |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Logistic Regression | 8 | 18457 | 16702 | 380 | 1370 | 5 | 0.6160 | 0.2489 | 0.6425 | 0.0737 | 0.4445 | 0.4000 |
| 1 | Random Forest | 8 | 18457 | 16702 | 380 | 1370 | 5 | 0.8488 | 0.3581 | 0.8722 | 0.0289 | 0.7934 | 0.0000 |
| 1 | 1D-CNN | 8 | 18457 | 16702 | 380 | 1370 | 5 | 0.7243 | 0.3453 | 0.7212 | 0.1711 | 0.9175 | 0.0000 |
| 2 | Logistic Regression | 8 | 17914 | 15405 | 1452 | 1040 | 17 | 0.4719 | 0.3186 | 0.4930 | 0.0971 | 0.6894 | 0.0588 |
| 2 | Random Forest | 8 | 17914 | 15405 | 1452 | 1040 | 17 | 0.8976 | 0.4360 | 0.9990 | 0.0096 | 0.6510 | 0.0000 |
| 2 | 1D-CNN | 8 | 17914 | 15405 | 1452 | 1040 | 17 | 0.7600 | 0.4473 | 0.8229 | 0.0034 | 0.8942 | 0.1765 |
| 3 | Logistic Regression | 7 | 16267 | 15207 | 163 | 892 | 5 | 0.6066 | 0.2900 | 0.6012 | 0.4356 | 0.7321 | 0.0000 |
| 3 | Random Forest | 7 | 16267 | 15207 | 163 | 892 | 5 | 0.9364 | 0.4136 | 0.9475 | 0.0184 | 0.9204 | 0.0000 |
| 3 | 1D-CNN | 7 | 16267 | 15207 | 163 | 892 | 5 | 0.8223 | 0.3864 | 0.8300 | 0.0675 | 0.8330 | 0.0000 |
| 4 | Logistic Regression | 7 | 16609 | 15043 | 313 | 1216 | 37 | 0.7278 | 0.3161 | 0.7600 | 0.2428 | 0.4753 | 0.0541 |
| 4 | Random Forest | 7 | 16609 | 15043 | 313 | 1216 | 37 | 0.9013 | 0.4050 | 0.9267 | 0.0351 | 0.8363 | 0.0000 |
| 4 | 1D-CNN | 7 | 16609 | 15043 | 313 | 1216 | 37 | 0.5346 | 0.2904 | 0.5121 | 0.5367 | 0.8289 | 0.0000 |
| 5 | Logistic Regression | 7 | 17039 | 14933 | 443 | 1298 | 365 | 0.5966 | 0.3499 | 0.6077 | 0.3995 | 0.6402 | 0.2274 |
| 5 | Random Forest | 7 | 17039 | 14933 | 443 | 1298 | 365 | 0.9214 | 0.4736 | 0.9775 | 0.0813 | 0.8220 | 0.0000 |
| 5 | 1D-CNN | 7 | 17039 | 14933 | 443 | 1298 | 365 | 0.3679 | 0.3127 | 0.3226 | 0.4447 | 0.9268 | 0.1397 |

![已有五折患者分组交叉验证结果](../../figures/11_four_class_diagnosis/group_cv_fold_metrics.png)

F 类跨折支持数差别显著；存在 F 支持只有个位数的折，也有 F 样本集中在少数患者的折。Macro-F1 和逐类 Recall 的折间变化反映患者组成的重要影响。OOF 综合值与折均值略有差别，因为一个是合并全部 OOF 预测再计分，一个是逐折计算后求均值。

## 第七章 综合讨论

### 7.1 二分类与四分类差异

二分类中 CNN 对 N 与 V 的区分在当前锁定划分上表现良好；加入 S 与 F 后，它们成为竞争类别且类别覆盖更偏向特定患者。四分类模型的 Accuracy 会被 N 类支持数主导；RF 的四分类测试 Accuracy 为 0.9536，但 S/F Recall 均为 0。CNN 的 V Recall 高而 S/F 几乎不识别。

### 7.2 数据不平衡与患者分布

除了 N/S/V/F 心拍数量比例不均，患者覆盖也不均：S 有效患者约 31/43，F 约 16/43。F 心拍的熵有效患者数约 3.05，且训练、验证、测试分别受到不同患者主导。用患者隔离划分能防止同一患者记录泄漏，却不能保证每个少数类在各 split 中具备广泛患者覆盖。对于本数据规模，这种患者集中是比单纯类别权重更基础的限制。

### 7.3 可支持的发现与待验证假设

由实验直接支持：指标 JSON 与预测 CSV 一致；四分类 S/F 测试召回差；患者组别及类别集中明显；类别权重会改变预测类别份额并产生 Precision/Recall 权衡；五折患者分组结果存在折间波动。

仍待验证：N→S、F→N 或 F→V 可能受单拍窗口缺少 RR 上下文、患者特异形态、类别内异质性、训练样本覆盖不足等因素影响。

### 7.4 数据与评估设置

项目使用 MIT-BIH 的 44 条非起搏双导联动态 ECG 记录。标签采用心拍级 AAMI 分组，N 类合并多种原始标注符号。测试结果由已保存预测复算，患者分组 CV 使用 train/validation 数据。

## 第八章 总结与展望

项目已完成数据探索、标签映射、患者独立数据集构建、N/V 与 N/S/V/F 基线实验、类别权重分析和患者分组 CV。重新计算的已保存测试预测指标与原 JSON 一致。二分类结果较好，四分类主要受到 S/F 患者覆盖及类内数据不足影响；更换复杂网络不是当前最优先改进。

后续可在不触碰锁定测试结果的前提下：在训练折内加入相邻心拍/RR 上下文比较；改善稀有类别的患者覆盖并采用患者分组评估；在预先锁定的新患者或外部数据库上作独立确认；最后再建立交互式波形展示工具。以上均为计划，未在本项目中完成。

## 参考文献与数据来源

1. Moody G, Mark R. MIT-BIH Arrhythmia Database (version 1.0.0). PhysioNet; 2005. doi:10.13026/C2F305. [官方数据集页面](https://physionet.org/content/mitdb/1.0.0/)。
2. Moody GB, Mark RG. The impact of the MIT-BIH Arrhythmia Database. *IEEE Engineering in Medicine and Biology Magazine*. 2001;20(3):45–50. doi:10.1109/51.932724.
3. PhysioNet. Standard annotations. [注释符号与非心拍代码说明](https://physionet.org/static/lightwave/doc/annotations.html)。
4. Association for the Advancement of Medical Instrumentation. ANSI/AAMI EC57:2012 (R2020), *Testing and reporting performance results of cardiac rhythm and ST segment measurement algorithms*. [ANSI/AAMI 官方产品页](https://webstore.ansi.org/standards/aami/ansiaamiec572012r2020)。本项目使用的逐符号映射可直接复核于 `src/labels.py`。
5. de Chazal P, O'Dwyer M, Reilly RB. Automatic classification of heartbeats using ECG morphology and heartbeat interval features. *IEEE Transactions on Biomedical Engineering*. 2004;51(7):1196–1206. doi:10.1109/TBME.2004.827359. [PubMed 记录](https://pubmed.ncbi.nlm.nih.gov/15248536/)。

## 附录：复现与核验产物

- 数据加载/预处理和训练入口见 `README.md`；不得把测试集重新用于调参。
- 本轮只生成报告、统计表与图，没有训练新模型：`python -m src.evaluation.final_report`。
- 原始预测仍在 `results/classification/nv44_v1/` 和 `results/classification/nsvf44_v1/`；新独立复算保存为 `results/classification/final_recomputed_*.csv/json`，旧记录不覆盖。
- 诊断来源：`reports/classification/four_class_failure_diagnosis.md`；五折输出：`results/classification/nsvf44_v1/diagnosis/group_cv_5fold/`。
- 逐文件清单：`project_file_inventory.csv`；核验摘要：`实验结果核验报告.md`；图表路径与说明：`图表索引.md`。
