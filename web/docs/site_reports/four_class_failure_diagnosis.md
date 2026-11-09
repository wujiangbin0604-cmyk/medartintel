# MIT-BIH N/S/V/F 四分类失败诊断

> 展示正式测试预测、混淆矩阵和波形，以及 train/validation 权重策略与 train+validation 的 37 个受试者组分组交叉验证。

## 结论摘要

- N/S/V/F 样本量为 89,577/2,761/6,977/800；最少 F 占 0.80%。
- F 类仅由 16 个受试者提供；最大单患者占该类 46.2%。
- 测试集中 F 的 371 拍中，99.7% 来自 subject_208；
- 验证集 S 有 1,404 拍，但 98.0% 来自 subject_232；训练与验证患者的类别构成不同。
- 预处理审计结果：标签/标注/窗口/导联/NPZ 对齐检查均通过。但发现并修正了派生统计 CSV 中 `subject_count`/`record_count` 对每个类别重复写入整个 split 记录数的代码错误；仅更新该汇总字段，没有改动样本、标签、划分、模型或原始文件。
- 类别权重影响具有模型依赖性：CNN 验证集全逆频率方案的 S/F 预测占比分别为 19.41%/3.90%，无权重为 0.00%/0.00%；同时少数类 Recall 的提高伴随 N 识别和少数类 Precision 的变化。随机森林原有验证结果没有出现相同方向的 S/F 过度预测。
- 所有新权重实验和 CV 不读取正式测试集。测试受试者指标及 ECG 错误图均在标题和文件名中标记为回顾性描述。

## 数据与患者间分布

四类有效窗口总计 100,115 拍。这里的样本数指通过窗口与信号有效性规则、实际进入模型 NPZ 的心拍，而不是全部原始 annotation 数。

| Class | Included beats | Share % |
| --- | --- | --- |
| N | 89577 | 89.474 |
| S | 2761 | 2.758 |
| V | 6977 | 6.969 |
| F | 800 | 0.799 |

### 按划分统计的类别覆盖

`subjects_with_class / subjects_total` 是该划分中至少有一拍该类的患者覆盖率；患者 ID `subject_201_202` 合并了记录 201 与 202。

| split | class | subjects_with_class | subjects_total | subject_coverage_pct | sample_count | top_subject_id | top_subject_share_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| train | N | 31 | 31 | 100.000 | 65436 | subject_201_202 | 5.615 |
| train | S | 23 | 31 | 74.194 | 1347 | subject_209 | 28.434 |
| train | V | 23 | 31 | 74.194 | 4747 | subject_200 | 17.316 |
| train | F | 10 | 31 | 32.258 | 411 | subject_213 | 88.078 |
| val | N | 6 | 6 | 100.000 | 11854 | subject_215 | 26.793 |
| val | S | 5 | 6 | 83.333 | 1404 | subject_232 | 98.006 |
| val | V | 4 | 6 | 66.667 | 1069 | subject_233 | 77.175 |
| val | F | 4 | 6 | 66.667 | 18 | subject_233 | 61.111 |
| test | N | 6 | 6 | 100.000 | 12287 | subject_212 | 22.243 |
| test | S | 3 | 6 | 50.000 | 10 | subject_219 | 70.000 |
| test | V | 5 | 6 | 83.333 | 1161 | subject_208 | 84.841 |
| test | F | 2 | 6 | 33.333 | 371 | subject_208 | 99.730 |

### 患者集中度

“有效受试者数”按心拍份额熵计算，用于描述分布集中度，不是独立样本数。

| class | subjects_with_class | top_subject_id | top_subject_samples | top_subject_share_pct | top3_subject_share_pct | effective_subject_count_2pow_entropy |
| --- | --- | --- | --- | --- | --- | --- |
| N | 43 | subject_201_202 | 3674 | 4.101 | 10.698 | 41.491 |
| S | 31 | subject_232 | 1376 | 49.837 | 71.279 | 6.601 |
| V | 32 | subject_208 | 985 | 14.118 | 37.724 | 16.000 |
| F | 16 | subject_208 | 370 | 46.250 | 93.250 | 3.054 |

![受试者×类别支持数热力图](../../figures/11_four_class_diagnosis/subject_class_counts_heatmap.png)

![各类心拍的患者集中度](../../figures/11_four_class_diagnosis/top_subject_class_concentration.png)

患者间差异的主要事实：训练集 F 有 10/31 个受试者提供，且单个患者贡献 88.1%；验证集 S 由患者 232 主导；正式测试 F 几乎全部来自患者 208。这样的 split 使少数类性能很容易被一个患者的形态与信号特征主导。

## 逐受试者模型表现：锁定测试集回顾

本节展示正式测试预测。每位患者的 Macro-F1 仅对该患者真实标签中出现的类别求平均；若该患者没有某类真实样本，该类 Recall 留空而不计算。

| model | subject_id | records | sample_count | accuracy | macro_f1_present_classes | supported_classes | recall_N | recall_S | recall_V | recall_F |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cnn_1d | subject_111 | 111 | 2112 | 0.886 | 0.525 | N,V | 0.886 | — | 1.000 | — |
| logistic_regression | subject_111 | 111 | 2112 | 0.009 | 0.010 | N,V | 0.009 | — | 1.000 | — |
| random_forest | subject_111 | 111 | 2112 | 0.971 | 0.520 | N,V | 0.971 | — | 1.000 | — |
| cnn_1d | subject_116 | 116 | 2398 | 0.864 | 0.621 | N,S,V | 0.858 | 0.000 | 0.991 | — |
| logistic_regression | subject_116 | 116 | 2398 | 0.985 | 0.640 | N,S,V | 0.984 | 0.000 | 1.000 | — |
| random_forest | subject_116 | 116 | 2398 | 0.999 | 0.665 | N,S,V | 1.000 | 0.000 | 0.991 | — |
| cnn_1d | subject_123 | 123 | 1509 | 0.997 | 0.999 | N,V | 0.997 | — | 1.000 | — |
| logistic_regression | subject_123 | 123 | 1509 | 0.993 | 0.998 | N,V | 0.993 | — | 1.000 | — |
| random_forest | subject_123 | 123 | 1509 | 0.949 | 0.987 | N,V | 0.949 | — | 1.000 | — |
| cnn_1d | subject_208 | 208 | 2936 | 0.801 | 0.449 | N,S,V,F | 0.867 | 0.000 | 0.998 | 0.003 |
| logistic_regression | subject_208 | 208 | 2936 | 0.770 | 0.454 | N,S,V,F | 0.911 | 1.000 | 0.809 | 0.062 |
| random_forest | subject_208 | 208 | 2936 | 0.839 | 0.447 | N,S,V,F | 0.994 | 0.000 | 0.907 | 0.000 |
| cnn_1d | subject_212 | 212 | 2733 | 0.312 | 0.475 | N | 0.312 | — | — | — |
| logistic_regression | subject_212 | 212 | 2733 | 0.952 | 0.975 | N | 0.952 | — | — | — |
| random_forest | subject_212 | 212 | 2733 | 0.996 | 0.998 | N | 0.996 | — | — | — |
| cnn_1d | subject_219 | 219 | 2141 | 0.927 | 0.472 | N,S,V,F | 0.931 | 0.000 | 0.889 | 0.000 |
| logistic_regression | subject_219 | 219 | 2141 | 0.711 | 0.551 | N,S,V,F | 0.707 | 0.571 | 0.857 | 1.000 |
| random_forest | subject_219 | 219 | 2141 | 0.992 | 0.480 | N,S,V,F | 1.000 | 0.000 | 0.857 | 0.000 |

![受试者级测试指标热力图](../../figures/11_four_class_diagnosis/per_subject_test_metrics_descriptive_only.png)

### 测试集误分类方向

| model | true_class | predicted_class | error_count |
| --- | --- | --- | --- |
| cnn_1d | N | S | 2626 |
| cnn_1d | F | N | 216 |
| cnn_1d | F | V | 154 |
| cnn_1d | N | F | 136 |
| cnn_1d | N | V | 42 |
| cnn_1d | S | N | 10 |
| cnn_1d | V | N | 4 |
| cnn_1d | V | S | 4 |
| cnn_1d | V | F | 2 |
| logistic_regression | N | V | 1577 |
| logistic_regression | N | S | 1405 |
| logistic_regression | F | V | 191 |
| logistic_regression | V | F | 147 |
| logistic_regression | F | N | 140 |
| logistic_regression | V | N | 41 |
| logistic_regression | N | F | 34 |
| logistic_regression | F | S | 16 |
| logistic_regression | V | S | 9 |
| logistic_regression | S | N | 4 |
| random_forest | F | N | 226 |
| random_forest | F | V | 144 |
| random_forest | N | S | 122 |
| random_forest | V | N | 102 |
| random_forest | N | V | 36 |

CNN 测试标签支持与预测份额已保存于 `test_prediction_class_shares_descriptive_only.csv`。CNN 的主要误分方向包括 N→S、F→N、F→V；其中 F 来源受试者高度集中，因此波形对比用于查看实际例子。

![CNN 典型错误心拍波形](../../figures/11_four_class_diagnosis/cnn_test_error_waveforms_descriptive_only.png)

图中每个面板注明 record、subject、标注样本、时间、原始专家符号与 AAMI 真实/预测类别。曲线使用滤波后物理单位 mV，标注点为 t=0；测试波形只作已暴露数据的定性说明。

## 类别权重策略：train 拟合、validation 比较

比较同一固定 1D-CNN 架构与 seed 的四种训练损失权重：无权重；平滑逆频率 `sqrt(N/(K*n_c))`；将 mean-one inverse-balanced 向量截断至 10 后重新 mean-one；现有全逆频率 `N/(K*n_c)`。各权重只由 train 标签计算。检查点按 validation Macro-F1 早停，所以该验证比较属于探索性结果，validation 并非独立调参集。

| strategy | split | accuracy | macro_f1_present_classes | predicted_share_N | predicted_share_S | predicted_share_V | predicted_share_F |
| --- | --- | --- | --- | --- | --- | --- | --- |
| unweighted | train | 0.950 | 0.437 | 95.018 | 0.000 | 4.969 | 0.013 |
| unweighted | val | 0.852 | 0.391 | 93.461 | 0.000 | 6.539 | 0.000 |
| sqrt_inverse | train | 0.932 | 0.508 | 91.143 | 0.000 | 6.975 | 1.882 |
| sqrt_inverse | val | 0.833 | 0.396 | 90.484 | 0.000 | 7.285 | 2.231 |
| capped_inverse_10 | train | 0.739 | 0.573 | 66.962 | 23.615 | 8.354 | 1.069 |
| capped_inverse_10 | val | 0.659 | 0.414 | 55.483 | 18.348 | 25.884 | 0.286 |
| full_inverse | train | 0.734 | 0.525 | 67.027 | 23.497 | 7.089 | 2.387 |
| full_inverse | val | 0.719 | 0.473 | 59.177 | 19.414 | 17.511 | 3.897 |

### Train/validation 每类 Precision / Recall / F1 与预测占比

| strategy | split | class | class_weight | support | predicted_count | predicted_share_pct | precision | recall | f1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unweighted | train | N | 1.000 | 65436 | 68357 | 95.018 | 0.953 | 0.995 | 0.973 |
| unweighted | train | S | 1.000 | 1347 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| unweighted | train | V | 1.000 | 4747 | 3575 | 4.969 | 0.901 | 0.678 | 0.774 |
| unweighted | train | F | 1.000 | 411 | 9 | 0.013 | 0.000 | 0.000 | 0.000 |
| unweighted | val | N | 1.000 | 11854 | 13407 | 93.461 | 0.863 | 0.976 | 0.916 |
| unweighted | val | S | 1.000 | 1404 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| unweighted | val | V | 1.000 | 1069 | 938 | 6.539 | 0.695 | 0.610 | 0.650 |
| unweighted | val | F | 1.000 | 18 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| sqrt_inverse | train | N | 0.165 | 65436 | 65569 | 91.143 | 0.964 | 0.966 | 0.965 |
| sqrt_inverse | train | S | 1.147 | 1347 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| sqrt_inverse | train | V | 0.611 | 4747 | 5018 | 6.975 | 0.712 | 0.752 | 0.731 |
| sqrt_inverse | train | F | 2.077 | 411 | 1354 | 1.882 | 0.219 | 0.723 | 0.337 |
| sqrt_inverse | val | N | 0.165 | 11854 | 12980 | 90.484 | 0.867 | 0.949 | 0.906 |
| sqrt_inverse | val | S | 1.147 | 1404 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| sqrt_inverse | val | V | 0.611 | 1069 | 1045 | 7.285 | 0.675 | 0.659 | 0.667 |
| sqrt_inverse | val | F | 2.077 | 18 | 320 | 2.231 | 0.006 | 0.111 | 0.012 |
| capped_inverse_10 | train | N | 0.046 | 65436 | 48173 | 66.962 | 0.986 | 0.726 | 0.836 |
| capped_inverse_10 | train | S | 1.662 | 1347 | 16989 | 23.615 | 0.051 | 0.641 | 0.094 |
| capped_inverse_10 | train | V | 0.630 | 4747 | 6010 | 8.354 | 0.744 | 0.942 | 0.832 |
| capped_inverse_10 | train | F | 1.662 | 411 | 769 | 1.069 | 0.407 | 0.762 | 0.531 |
| capped_inverse_10 | val | N | 0.046 | 11854 | 7959 | 55.483 | 0.940 | 0.631 | 0.755 |
| capped_inverse_10 | val | S | 1.662 | 1404 | 2632 | 18.348 | 0.372 | 0.698 | 0.486 |
| capped_inverse_10 | val | V | 0.630 | 1069 | 3713 | 25.884 | 0.267 | 0.926 | 0.414 |
| capped_inverse_10 | val | F | 1.662 | 18 | 41 | 0.286 | 0.000 | 0.000 | 0.000 |
| full_inverse | train | N | 0.275 | 65436 | 48220 | 67.027 | 0.983 | 0.724 | 0.834 |
| full_inverse | train | S | 13.352 | 1347 | 16904 | 23.497 | 0.052 | 0.649 | 0.096 |
| full_inverse | train | V | 3.789 | 4747 | 5100 | 7.089 | 0.818 | 0.879 | 0.848 |
| full_inverse | train | F | 43.760 | 411 | 1717 | 2.387 | 0.201 | 0.839 | 0.324 |
| full_inverse | val | N | 0.275 | 11854 | 8489 | 59.177 | 0.963 | 0.690 | 0.804 |
| full_inverse | val | S | 13.352 | 1404 | 2785 | 19.414 | 0.469 | 0.931 | 0.624 |
| full_inverse | val | V | 3.789 | 1069 | 2512 | 17.511 | 0.327 | 0.769 | 0.459 |
| full_inverse | val | F | 43.760 | 18 | 559 | 3.897 | 0.004 | 0.111 | 0.007 |

### LR/RF 与 CNN 既有加权/无权重验证对照

下表直接复用此前保存的 validation-only 消融；该文件记录未加载 test。它用于判断权重效应是否跨模型一致。

| model | condition | accuracy | macro_f1 | recall_S | predicted_share_S | recall_F | predicted_share_F |
| --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | weighted | 0.486 | 0.264 | 0.092 | 22.356 | 0.167 | 3.005 |
| logistic_regression | unweighted | 0.795 | 0.337 | 0.000 | 0.230 | 0.000 | 0.551 |
| random_forest | weighted | 0.855 | 0.402 | 0.005 | 0.098 | 0.000 | 0.000 |
| random_forest | unweighted | 0.858 | 0.409 | 0.001 | 0.160 | 0.000 | 0.000 |
| cnn_1d | weighted | 0.719 | 0.473 | 0.931 | 19.414 | 0.111 | 3.897 |
| cnn_1d | unweighted | 0.852 | 0.391 | 0.000 | 0.000 | 0.000 | 0.000 |

![权重方案的训练与验证指标及预测份额](../../figures/11_four_class_diagnosis/cnn_weight_strategies_train_val.png)
![传统模型与 CNN 既有加权验证对照](../../figures/11_four_class_diagnosis/existing_model_weight_ablation_validation.png)

绝对权重不能单独证明原因；更强的证据是同一 CNN 与相同 train/validation 下的策略对照。如果全逆频率提升 S/F Recall，却显著提高少数类预测占比并压低 Precision，则“过度预测”是可观测的代价。平滑/截断方案应结合 Macro-F1、类别 Recall/Precision 与训练-验证差值判断，不按 Accuracy 单项选择。

## 严格受试者分组交叉验证

使用固定配置的五折 `StratifiedGroupKFold`，只输入原 train 与 validation 的 86,286 拍、37 个患者组；实际样本/患者总数以 `group_cv_training_log.json` 为准。外层每位患者只作一次 OOF 评估，外层训练与验证患者集合无交集。CNN 早停内层也按患者分组，并使用内层最佳 epoch 在完整外层训练组上重拟合。每折均只使用该折训练患者拟合标量归一化与类别权重。

| model | accuracy_mean | accuracy_std | macro_f1_mean | macro_f1_std | pooled_oof_macro_f1_present_classes | recall_N_mean | recall_S_mean | recall_V_mean | recall_F_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | 0.604 | 0.091 | 0.305 | 0.038 | 0.293 | 0.621 | 0.250 | 0.596 | 0.148 |
| random_forest | 0.901 | 0.033 | 0.417 | 0.042 | 0.405 | 0.945 | 0.035 | 0.805 | 0.000 |
| cnn_1d | 0.642 | 0.187 | 0.356 | 0.062 | 0.354 | 0.642 | 0.245 | 0.880 | 0.063 |

### 每折样本支持与 Macro-F1

| model | fold | validation_subject_count | validation_sample_count | support_N | support_S | support_V | support_F | macro_f1_present_classes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | 1 | 8 | 18457 | 16702 | 380 | 1370 | 5 | 0.249 |
| random_forest | 1 | 8 | 18457 | 16702 | 380 | 1370 | 5 | 0.358 |
| cnn_1d | 1 | 8 | 18457 | 16702 | 380 | 1370 | 5 | 0.345 |
| logistic_regression | 2 | 8 | 17914 | 15405 | 1452 | 1040 | 17 | 0.319 |
| random_forest | 2 | 8 | 17914 | 15405 | 1452 | 1040 | 17 | 0.436 |
| cnn_1d | 2 | 8 | 17914 | 15405 | 1452 | 1040 | 17 | 0.447 |
| logistic_regression | 3 | 7 | 16267 | 15207 | 163 | 892 | 5 | 0.290 |
| random_forest | 3 | 7 | 16267 | 15207 | 163 | 892 | 5 | 0.414 |
| cnn_1d | 3 | 7 | 16267 | 15207 | 163 | 892 | 5 | 0.386 |
| logistic_regression | 4 | 7 | 16609 | 15043 | 313 | 1216 | 37 | 0.316 |
| random_forest | 4 | 7 | 16609 | 15043 | 313 | 1216 | 37 | 0.405 |
| cnn_1d | 4 | 7 | 16609 | 15043 | 313 | 1216 | 37 | 0.290 |
| logistic_regression | 5 | 7 | 17039 | 14933 | 443 | 1298 | 365 | 0.350 |
| random_forest | 5 | 7 | 17039 | 14933 | 443 | 1298 | 365 | 0.474 |
| cnn_1d | 5 | 7 | 17039 | 14933 | 443 | 1298 | 365 | 0.313 |

![五折患者分组 CV 指标](../../figures/11_four_class_diagnosis/group_cv_fold_metrics.png)

![五折患者分组 CV 混淆矩阵](../../figures/11_four_class_diagnosis/group_cv_confusion_matrices.png)

fold 间 F 的验证支持数差异很大；Macro-F1 与类别 Recall 的折间波动是稳定性信息，而非单个最高折表现。分层以心拍为辅助目标但不拆患者；患者组成不均仍然限制估计。

## 预处理、导联、窗口与标签程序审计

| 检查项 | 结果 |
|---|---|
| WFDB 原始 annotation 样本位置与 symbol 对照 | True |
| 显式 AAMI 映射与 N/S/V/F 整数标签对照 | True / True |
| 非心拍、Q 类、未知标注进入四分类 NPZ | 不进入；只保留在 metadata 与排除计数 |
| MLII 选择规则与实际使用导联 | True / MLII only = True |
| 0.3 秒前、0.4 秒后，253 样本，中心索引 108 | True |
| NPZ 顺序、标签与 metadata | True |
| 受试者交叉与 201/202 同组 | overlap=0；pair same split=True |
| 归一化拟合分区 | train |
| 滤波通带 | [0.5, 40.0] Hz，双向零相位离线滤波 |
| LR/RF/CNN 正式权重文件读取 | True；CNN best epoch=11 |

没有发现 AAMI 目标映射、专家标注位置、导联选择、窗口长度或 NPZ 行对齐的程序性不一致。发现的程序性统计问题限于 `split_class_counts.csv` 中 `subject_count`/`record_count` 字段：原代码对每类重复写了 split 总数；现已修复生成逻辑，并按现有 metadata 更新此派生表。该问题不影响模型使用的 `train/val/test.npz` 或实验指标。

## 发现分级与建议

### 已由实验支持的发现

- 类别明显不平衡，尤其 F 仅 800 个有效心拍、集中于 16 位受试者；测试 F 几乎全来自一个患者。
- S/F 患者覆盖比总心拍数更关键：相同类别在 train/validation/test 的患者覆盖和患者占比变化明显。
- 全逆频率 CNN 验证时少数类 Recall 提高，但 N Recall/Macro-F1 与 Precision 会交换；CNN 与 RF 的响应不同，因此不能笼统归因为“所有类别权重都太大”。
- 逐拍窗口仅包含局部形态，不含显式前后 RR 或节律上下文；N→S 与 F→N/V 形态混淆在已查看预测中确实发生。
- 除 `split_class_counts.csv` 的统计字段外，源标注、标签映射、MLII、窗口与数据行对齐审计通过。

### 需要进一步验证的猜想

- 训练 F 主要来自患者 213，而留出 F 主要来自患者 208，模型可能把患者/记录特有形态学到为 F 判据；需要更多独立 F 患者或外部 ECG 数据验证。
- N→S 错误可能受 S/N 形态重叠、节律信息缺失、记录增益与患者差异共同影响；仅凭静态波形不能拆分其贡献。
- F 作为融合心拍本身包含不同形态成分，单个 253 点窗口可能不足以表征其与前后心拍的关系；需要对 beat-centered context/RR 特征做受试者分组实验。
- 全逆频率下 F 预测的校准可能不佳；本阶段未做阈值选择、概率校准或测试集优化。

### 数据说明

- MIT-BIH 是有限的历史 Holter 数据库，受试者数量和罕见类别的患者覆盖有限。
- 四类任务的患者切分沿用了 N/V 分区，未针对 S/F 覆盖设计；当前验证/测试留出的稀有类别支持数非常小且高度患者集中。
- AAMI N 是聚合组，包含多种原始 expert beat 符号；F/S 并非每位受试者均有标注。
- 双向滤波是离线处理，部署到实时系统需重新设计因果滤波与延迟控制。

### 课程项目最值得实施的改进

1. 以患者为最小评估单位继续报告 Macro-F1、各类 Recall/Precision、患者覆盖和折间方差；保留现有测试结果为历史结果，后续只新增患者级外部或嵌套分组验证。
2. 优先增加 F 与 S 的患者多样性；课程项目可先使用固定手工权重方案做 train/validation 消融，并报告少数类 Precision/Recall 的取舍，不根据测试集选权重。
3. 对 F、S 比较单心拍与短序列/RR 上下文特征，以及 patient-balanced 的训练采样；只在训练折内部估计任何重采样和变换。
4. 加入按患者/记录的错误案例复核、置信度校准和敏感性分析；不要把更高 Accuracy 当作唯一成功标准。
5. 冻结当前已暴露的测试集结果，未来若需无偏最终评估，应收集未参与探索的新受试者或使用预先锁定的外部数据。

## 诊断图逐图说明

- [`subject_class_counts_heatmap.png`](../../figures/11_four_class_diagnosis/subject_class_counts_heatmap.png) — 每位受试者各类心拍支持数。使用 log10(count+1) 显示数量级，空格代表该受试者在该类没有可训练样本。
- [`top_subject_class_concentration.png`](../../figures/11_four_class_diagnosis/top_subject_class_concentration.png) — 各类别心拍最多的受试者，展示 F、S 等类别由少数患者主导的程度。
- [`per_subject_test_metrics_descriptive_only.png`](../../figures/11_four_class_diagnosis/per_subject_test_metrics_descriptive_only.png) — 既有锁定测试集按受试者分解的 Accuracy、present-class Macro-F1 与 Recall；无该类样本时留空。仅回顾性诊断。
- [`cnn_test_error_waveforms_descriptive_only.png`](../../figures/11_four_class_diagnosis/cnn_test_error_waveforms_descriptive_only.png) — CNN 测试集 N→S、F→N 与 F→V 代表波形及误分类分析。
- [`cnn_weight_strategies_train_val.png`](../../figures/11_four_class_diagnosis/cnn_weight_strategies_train_val.png) — 同一 CNN 的 train/validation 指标及预测类别占比，比较无权重、平方根平滑、10 倍截断和全逆频率。
- [`group_cv_fold_metrics.png`](../../figures/11_four_class_diagnosis/group_cv_fold_metrics.png) — train+validation 的五折患者分组 CV，每折 Macro-F1 与 Accuracy，展示受试者间波动。
- [`group_cv_confusion_matrices.png`](../../figures/11_four_class_diagnosis/group_cv_confusion_matrices.png) — 每个分组 CV 外折的行归一化混淆矩阵，同时标出原始计数和 F 支持数。
- [`existing_model_weight_ablation_validation.png`](../../figures/11_four_class_diagnosis/existing_model_weight_ablation_validation.png) — 复用既有验证集加权/无权重消融，比较 LR、RF、CNN 对 S/F 的预测份额变化。

## 输出文件

- 受试者类计数/覆盖/集中度：`results/classification/nsvf44_v1/diagnosis/subject_*.csv`
- 患者级测试指标与误分类：`results/classification/nsvf44_v1/diagnosis/per_subject_test_*_descriptive_only.csv`
- 权重策略及训练日志：`results/classification/nsvf44_v1/diagnosis/weight_strategy_*.csv/json`
- 分组 CV 指标、OOF 预测、fold 患者清单：`results/classification/nsvf44_v1/diagnosis/group_cv_*`
- 诊断图片目录：`figures/11_four_class_diagnosis/`
- 完整诊断检查清单：`results/classification/nsvf44_v1/diagnosis/preprocessing_audit.json`
