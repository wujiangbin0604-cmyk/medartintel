# MIT-BIH 数据构建与心拍分类实验总结

本报告由代码从实际数据集 manifest、预测 CSV 和指标 JSON 生成。该项目用于课程数据探索和算法实验，不构成临床诊断。

## 数据处理与划分

数据集版本 1.0.0 共 48 条记录、47 位受试者；分析和分类数据使用 44 条非起搏记录，排除 102、104、107、217。PhysioNet 官方目录说明这四条记录包含起搏心拍，并指出原始模拟记录对起搏器伪迹的常见识别线索保真不足；44 条方案是常见 AAMI 实验约定，不意味着原始记录被删除。 [PhysioNet 数据集说明](https://physionet.org/content/mitdb/1.0.0/)；[MIT-BIH 目录说明](https://physionet.org/physiobank/database/html/mitdbdir/intro.htm)。

44 记录的 AAMI 目标心拍有效窗口数量：

| aami_label | class_id | sample_count | percentage |
| --- | --- | --- | --- |
| N | 0 | 89577 | 92.7740 |
| V | 1 | 6977 | 7.2260 |

原始标注中 AAMI 心拍总数（此处仅计心拍，不计节律/信号质量符号）：

| record_cohort | N | S | V | F | Q |
| --- | --- | --- | --- | --- | --- |
| 44 included | 90125 | 2781 | 7009 | 803 | 15 |
| 4 paced excluded | 506 | 0 | 227 | 0 | 8028 |
| All 48 | 90631 | 2781 | 7236 | 803 | 8043 |

全 48 条记录的原始 symbol 频数（包含不入心拍类别的非心拍标注）：

| symbol | count | aami_label | annotation_kind |
| --- | --- | --- | --- |
| N | 75052 | N | mapped_beat |
| L | 8075 | N | mapped_beat |
| R | 7259 | N | mapped_beat |
| V | 7130 | V | mapped_beat |
| / | 7028 | Q | mapped_beat |
| A | 2546 | S | mapped_beat |
| + | 1291 |  | non_beat_or_unmapped |
| f | 982 | Q | mapped_beat |
| F | 803 | F | mapped_beat |
| ~ | 616 |  | non_beat_or_unmapped |
| ! | 472 |  | non_beat_or_unmapped |
| " | 437 |  | non_beat_or_unmapped |
| j | 229 | N | mapped_beat |
| x | 193 |  | non_beat_or_unmapped |
| a | 150 | S | mapped_beat |
| \| | 132 |  | non_beat_or_unmapped |
| E | 106 | V | mapped_beat |
| J | 83 | S | mapped_beat |
| Q | 33 | Q | mapped_beat |
| e | 16 | N | mapped_beat |
| [ | 6 |  | non_beat_or_unmapped |
| ] | 6 |  | non_beat_or_unmapped |
| S | 2 | S | mapped_beat |

固定种子 20261027 的患者级划分：

| split | subject_count | record_count | records |
| --- | --- | --- | --- |
| train | 31 | 32 | 100, 101, 103, 105, 106, 108, 112, 115, 117, 118, 119, 121, 122, 124, 200, 201, 202, 203, 205, 207, 209, 210, 213, 214, 220, 221, 222, 223, 228, 230, 231, 234 |
| val | 6 | 6 | 109, 113, 114, 215, 232, 233 |
| test | 6 | 6 | 111, 116, 123, 208, 212, 219 |

记录 201/202 同属一个受试者分组并进入同一集合；100/200 因前期已经用于数据探索而预先固定在训练集。受试者交集检查必须为零。

N/V 数据集的分区类别数：

| split | aami_label | class_id | sample_count | subject_count | record_count |
| --- | --- | --- | --- | --- | --- |
| train | N | 0 | 65436 | 31 | 32 |
| train | V | 1 | 4747 | 31 | 32 |
| val | N | 0 | 11854 | 6 | 6 |
| val | V | 1 | 1069 | 6 | 6 |
| test | N | 0 | 12287 | 6 | 6 |
| test | V | 1 | 1161 | 6 | 6 |


复用同一患者分区后的四分类样本数量：

| split | aami_label | class_id | sample_count | subject_count | record_count |
| --- | --- | --- | --- | --- | --- |
| train | N | 0 | 65436 | 31 | 32 |
| train | S | 1 | 1347 | 31 | 32 |
| train | V | 2 | 4747 | 31 | 32 |
| train | F | 3 | 411 | 31 | 32 |
| val | N | 0 | 11854 | 6 | 6 |
| val | S | 1 | 1404 | 6 | 6 |
| val | V | 2 | 1069 | 6 | 6 |
| val | F | 3 | 18 | 6 | 6 |
| test | N | 0 | 12287 | 6 | 6 |
| test | S | 1 | 10 | 6 | 6 |
| test | V | 2 | 1161 | 6 | 6 |
| test | F | 3 | 371 | 6 | 6 |

各类别在每个患者分区中出现的患者数与每患者心拍数量范围：

| split | mapped_label | subject_count | heartbeat_count | minimum_per_subject | maximum_per_subject |
| --- | --- | --- | --- | --- | --- |
| test | F | 2 | 371 | 1 | 370 |
| test | N | 6 | 12287 | 1506 | 2733 |
| test | S | 3 | 10 | 1 | 7 |
| test | V | 5 | 1161 | 1 | 985 |
| train | F | 10 | 411 | 1 | 362 |
| train | N | 31 | 65436 | 1498 | 3674 |
| train | S | 23 | 1347 | 1 | 383 |
| train | V | 23 | 4747 | 1 | 822 |
| val | F | 4 | 18 | 1 | 11 |
| val | N | 6 | 11854 | 395 | 3176 |
| val | S | 5 | 1404 | 3 | 1376 |
| val | V | 4 | 1069 | 37 | 825 |

预处理复用 `src.io.load_record`、`src.labels.AAMI_MAP` 和 `src.preprocessing`。先在连续 MLII（不存在时明确回退并记录实际首导联）上进行 0.5–40 Hz Butterworth SOS 双向滤波，标注前 0.3 秒、后 0.4 秒、含端点共 253 点；窗口越界、滤波保护区、非有限或平直窗按预定义技术规则排除并留在 metadata。通道/记录/样本/原标签均可追溯。全局均值与标准差仅在训练集有效过滤后样本拟合；Logistic Regression 的特征缩放同样只在训练数据拟合。类别权重只由训练标签计算。原始 48 条记录均保留且逐文件 SHA256 复核。

### 数据构建与预处理图片

- [label_distribution_all48_and_44.png](../../figures/07_preprocessing/label_distribution_all48_and_44.png) — MIT-BIH original labels and AAMI distribution。
- [record_aami_counts_44.png](../../figures/07_preprocessing/record_aami_counts_44.png) — AAMI counts across the 44 included records。
- [split_class_distribution_44.png](../../figures/07_preprocessing/split_class_distribution_44.png) — 44-record target-class distribution by split。
- [100_raw_vs_filtered_first10s.png](../../figures/07_preprocessing/100_raw_vs_filtered_first10s.png) — Record 100 | MLII | first 10 seconds: filter comparison。
- [200_raw_vs_filtered_first10s.png](../../figures/07_preprocessing/200_raw_vs_filtered_first10s.png) — Record 200 | MLII | first 10 seconds: filter comparison。
- [split_class_distribution_44_nsvf.png](../../figures/07_preprocessing/split_class_distribution_44_nsvf.png) — 44-record target-class distribution by split。


## N/V 二分类结果

数据规模：训练 70,183，验证 12,923，测试 13,448 拍。

测试指标（由保存预测 CSV 独立重算核对）：

| model | accuracy | macro-F1 | N precision | N recall | N F1 | N n | V precision | V recall | V F1 | V n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | 0.8369 | 0.6961 | 0.9892 | 0.8306 | 0.9030 | 12287 | 0.3352 | 0.9044 | 0.4892 | 1161 |
| random_forest | 0.9835 | 0.9494 | 0.9945 | 0.9874 | 0.9909 | 12287 | 0.8759 | 0.9423 | 0.9079 | 1161 |
| cnn_1d | 0.9957 | 0.9865 | 0.9991 | 0.9962 | 0.9976 | 12287 | 0.9607 | 0.9905 | 0.9754 | 1161 |

### 混淆矩阵

- **logistic_regression**（行=参考标签、列=预测标签，类别顺序 N, V）：`[[10205, 2082], [111, 1050]]`。
- **random_forest**（行=参考标签、列=预测标签，类别顺序 N, V）：`[[12132, 155], [67, 1094]]`。
- **cnn_1d**（行=参考标签、列=预测标签，类别顺序 N, V）：`[[12240, 47], [11, 1150]]`。

### 误分类观察

- **logistic_regression**：共 2,193/13,448 个测试样本误分类；主要方向：N→V 2082 拍、V→N 111 拍。
- **random_forest**：共 222/13,448 个测试样本误分类；主要方向：N→V 155 拍、V→N 67 拍。
- **cnn_1d**：共 58/13,448 个测试样本误分类；主要方向：N→V 47 拍、V→N 11 拍。

### 可追溯的错误样本

- `logistic_regression`：111 / subject_111 / MLII，样本 2040（5.667s），N→V。
- `logistic_regression`：116 / subject_116 / MLII，样本 150063（416.842s），V→N。
- `logistic_regression`：208 / subject_208 / MLII，样本 23128（64.244s），V→N。
- `logistic_regression`：212 / subject_212 / MLII，样本 176649（490.692s），N→V。
- `logistic_regression`：219 / subject_219 / MLII，样本 42233（117.314s），N→V。
- `random_forest`：111 / subject_111 / MLII，样本 53521（148.669s），N→V。
- `random_forest`：116 / subject_116 / MLII，样本 218527（607.019s），V→N。
- `random_forest`：208 / subject_208 / MLII，样本 46211（128.364s），V→N。
- `random_forest`：212 / subject_212 / MLII，样本 73011（202.808s），N→V。
- `random_forest`：219 / subject_219 / MLII，样本 365144（1014.289s），V→N。
- `cnn_1d`：111 / subject_111 / MLII，样本 67329（187.025s），N→V。
- `cnn_1d`：116 / subject_116 / MLII，样本 360251（1000.697s），N→V。
- `cnn_1d`：208 / subject_208 / MLII，样本 438077（1216.881s），N→V。
- `cnn_1d`：219 / subject_219 / MLII，样本 13863（38.508s），V→N。

### 图像

- [test_accuracy_comparison.png](../../figures/08_binary_classification/test_accuracy_comparison.png) — test accuracy comparison。
- [test_precision_recall_f1_comparison.png](../../figures/08_binary_classification/test_precision_recall_f1_comparison.png) — test precision recall f1 comparison。
- [test_macro_f1_comparison.png](../../figures/08_binary_classification/test_macro_f1_comparison.png) — test macro f1 comparison。
- [test_confusion_matrix_logistic_regression.png](../../figures/08_binary_classification/test_confusion_matrix_logistic_regression.png) — test confusion matrix logistic regression。
- [test_confusion_matrix_random_forest.png](../../figures/08_binary_classification/test_confusion_matrix_random_forest.png) — test confusion matrix random forest。
- [test_confusion_matrix_cnn_1d.png](../../figures/08_binary_classification/test_confusion_matrix_cnn_1d.png) — test confusion matrix cnn 1d。
- [cnn_train_validation_loss.png](../../figures/08_binary_classification/cnn_train_validation_loss.png) — cnn train validation loss。
- [cnn_validation_macro_f1.png](../../figures/08_binary_classification/cnn_validation_macro_f1.png) — cnn validation macro f1。
- [test_probability_distribution_logistic_regression.png](../../figures/08_binary_classification/test_probability_distribution_logistic_regression.png) — test probability distribution logistic regression。
- [test_probability_distribution_random_forest.png](../../figures/08_binary_classification/test_probability_distribution_random_forest.png) — test probability distribution random forest。
- [test_probability_distribution_cnn_1d.png](../../figures/08_binary_classification/test_probability_distribution_cnn_1d.png) — test probability distribution cnn 1d。
- [test_ecg_examples_logistic_regression.png](../../figures/08_binary_classification/test_ecg_examples_logistic_regression.png) — test ecg examples logistic regression。
- [test_ecg_examples_random_forest.png](../../figures/08_binary_classification/test_ecg_examples_random_forest.png) — test ecg examples random forest。
- [test_ecg_examples_cnn_1d.png](../../figures/08_binary_classification/test_ecg_examples_cnn_1d.png) — test ecg examples cnn 1d。
- [test_directional_errors_logistic_regression.png](../../figures/08_binary_classification/test_directional_errors_logistic_regression.png) — test directional errors logistic regression。
- [test_directional_errors_random_forest.png](../../figures/08_binary_classification/test_directional_errors_random_forest.png) — test directional errors random forest。
- [test_directional_errors_cnn_1d.png](../../figures/08_binary_classification/test_directional_errors_cnn_1d.png) — test directional errors cnn 1d。

重点 V 类指标：

| model | V precision | V recall | V F1 | V support |
| --- | --- | --- | --- | --- |
| logistic_regression | 0.3352 | 0.9044 | 0.4892 | 1161 |
| random_forest | 0.8759 | 0.9423 | 0.9079 | 1161 |
| cnn_1d | 0.9607 | 0.9905 | 0.9754 | 1161 |

## N/S/V/F 四分类结果

数据规模：训练 71,941，验证 14,345，测试 13,829 拍。

测试指标（由保存预测 CSV 独立重算核对）：

| model | accuracy | macro-F1 | N precision | N recall | N F1 | N n | S precision | S recall | S F1 | S n | V precision | V recall | V F1 | V n | F precision | F recall | F F1 | F n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | 0.7423 | 0.3599 | 0.9804 | 0.7545 | 0.8528 | 12287 | 0.0042 | 0.6000 | 0.0083 | 10 | 0.3529 | 0.8303 | 0.4952 | 1161 | 0.1171 | 0.0647 | 0.0833 | 371 |
| random_forest | 0.9536 | 0.4656 | 0.9729 | 0.9871 | 0.9800 | 12287 | 0.0000 | 0.0000 | 0.0000 | 10 | 0.8547 | 0.9121 | 0.8825 | 1161 | 0.0000 | 0.0000 | 0.0000 | 371 |
| cnn_1d | 0.7690 | 0.4460 | 0.9763 | 0.7718 | 0.8621 | 12287 | 0.0000 | 0.0000 | 0.0000 | 10 | 0.8545 | 0.9914 | 0.9179 | 1161 | 0.0072 | 0.0027 | 0.0039 | 371 |

### 混淆矩阵

- **logistic_regression**（行=参考标签、列=预测标签，类别顺序 N, S, V, F）：`[[9271, 1405, 1577, 34], [4, 6, 0, 0], [41, 9, 964, 147], [140, 16, 191, 24]]`。
- **random_forest**（行=参考标签、列=预测标签，类别顺序 N, S, V, F）：`[[12129, 122, 36, 0], [10, 0, 0, 0], [102, 0, 1059, 0], [226, 1, 144, 0]]`。
- **cnn_1d**（行=参考标签、列=预测标签，类别顺序 N, S, V, F）：`[[9483, 2626, 42, 136], [10, 0, 0, 0], [4, 4, 1151, 2], [216, 0, 154, 1]]`。

### 误分类观察

- **logistic_regression**：共 3,564/13,829 个测试样本误分类；主要方向：N→V 1577 拍、N→S 1405 拍、F→V 191 拍、V→F 147 拍、F→N 140 拍。
- **random_forest**：共 641/13,829 个测试样本误分类；主要方向：F→N 226 拍、F→V 144 拍、N→S 122 拍、V→N 102 拍、N→V 36 拍。
- **cnn_1d**：共 3,194/13,829 个测试样本误分类；主要方向：N→S 2626 拍、F→N 216 拍、F→V 154 拍、N→F 136 拍、N→V 42 拍。

### 可追溯的错误样本

- `logistic_regression`：111 / subject_111 / MLII，样本 2040（5.667s），N→V。
- `logistic_regression`：116 / subject_116 / MLII，样本 298940（830.389s），S→N。
- `logistic_regression`：123 / subject_123 / MLII，样本 153555（426.542s），N→S。
- `logistic_regression`：208 / subject_208 / MLII，样本 4097（11.381s），F→N。
- `logistic_regression`：212 / subject_212 / MLII，样本 10716（29.767s），N→S。
- `logistic_regression`：219 / subject_219 / MLII，样本 3864（10.733s），N→S。
- `random_forest`：111 / subject_111 / MLII，样本 19450（54.028s），N→S。
- `random_forest`：116 / subject_116 / MLII，样本 298940（830.389s），S→N。
- `random_forest`：123 / subject_123 / MLII，样本 6073（16.869s），N→S。
- `random_forest`：208 / subject_208 / MLII，样本 4097（11.381s），F→V。
- `random_forest`：212 / subject_212 / MLII，样本 44196（122.767s），N→S。
- `random_forest`：219 / subject_219 / MLII，样本 63190（175.528s），F→N。
- `cnn_1d`：111 / subject_111 / MLII，样本 19143（53.175s），N→S。
- `cnn_1d`：116 / subject_116 / MLII，样本 178507（495.853s），N→S。
- `cnn_1d`：123 / subject_123 / MLII，样本 38394（106.650s），N→S。
- `cnn_1d`：208 / subject_208 / MLII，样本 4097（11.381s），F→V。
- `cnn_1d`：212 / subject_212 / MLII，样本 1953（5.425s），N→S。
- `cnn_1d`：219 / subject_219 / MLII，样本 7800（21.667s），N→F。

### 图像

- [test_accuracy_comparison.png](../../figures/09_multiclass_classification/test_accuracy_comparison.png) — test accuracy comparison。
- [test_precision_recall_f1_comparison.png](../../figures/09_multiclass_classification/test_precision_recall_f1_comparison.png) — test precision recall f1 comparison。
- [test_macro_f1_comparison.png](../../figures/09_multiclass_classification/test_macro_f1_comparison.png) — test macro f1 comparison。
- [test_confusion_matrix_logistic_regression.png](../../figures/09_multiclass_classification/test_confusion_matrix_logistic_regression.png) — test confusion matrix logistic regression。
- [test_confusion_matrix_random_forest.png](../../figures/09_multiclass_classification/test_confusion_matrix_random_forest.png) — test confusion matrix random forest。
- [test_confusion_matrix_cnn_1d.png](../../figures/09_multiclass_classification/test_confusion_matrix_cnn_1d.png) — test confusion matrix cnn 1d。
- [cnn_train_validation_loss.png](../../figures/09_multiclass_classification/cnn_train_validation_loss.png) — cnn train validation loss。
- [cnn_validation_macro_f1.png](../../figures/09_multiclass_classification/cnn_validation_macro_f1.png) — cnn validation macro f1。
- [test_probability_distribution_logistic_regression.png](../../figures/09_multiclass_classification/test_probability_distribution_logistic_regression.png) — test probability distribution logistic regression。
- [test_probability_distribution_random_forest.png](../../figures/09_multiclass_classification/test_probability_distribution_random_forest.png) — test probability distribution random forest。
- [test_probability_distribution_cnn_1d.png](../../figures/09_multiclass_classification/test_probability_distribution_cnn_1d.png) — test probability distribution cnn 1d。
- [test_ecg_examples_logistic_regression.png](../../figures/09_multiclass_classification/test_ecg_examples_logistic_regression.png) — test ecg examples logistic regression。
- [test_ecg_examples_random_forest.png](../../figures/09_multiclass_classification/test_ecg_examples_random_forest.png) — test ecg examples random forest。
- [test_ecg_examples_cnn_1d.png](../../figures/09_multiclass_classification/test_ecg_examples_cnn_1d.png) — test ecg examples cnn 1d。

### 训练集类别权重的验证集消融

为观察训练类权重的作用，使用同一训练集/验证集、固定结构与种子另跑无权重 LR/RF/CNN 对照；该消融只读取训练和验证文件，**未读取测试文件，也未更换/挑选正式模型**。下面 Δ=正式训练权重模型验证 Recall − 无权重验证 Recall，不能视作测试效果或独立验证集。

| model | class | weighted Recall | unweighted Recall | Recall Δ | weighted F1 | unweighted F1 | weighted support |
| --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | N | 0.5112 | 0.9085 | -0.3972 | 0.6294 | 0.8804 | 11854 |
| logistic_regression | S | 0.0919 | 0.0000 | 0.0919 | 0.0560 | 0.0000 | 1404 |
| logistic_regression | V | 0.7287 | 0.5893 | 0.1394 | 0.3563 | 0.4679 | 1069 |
| logistic_regression | F | 0.1667 | 0.0000 | 0.1667 | 0.0134 | 0.0000 | 18 |
| random_forest | N | 0.9731 | 0.9729 | 0.0002 | 0.9177 | 0.9192 | 11854 |
| random_forest | S | 0.0050 | 0.0014 | 0.0036 | 0.0099 | 0.0028 | 1404 |
| random_forest | V | 0.6726 | 0.7184 | -0.0458 | 0.6802 | 0.7141 | 1069 |
| random_forest | F | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 18 |
| cnn_1d | N | 0.6897 | 0.9760 | -0.2862 | 0.8038 | 0.9160 | 11854 |
| cnn_1d | S | 0.9309 | 0.0000 | 0.9309 | 0.6240 | 0.0000 | 1404 |
| cnn_1d | V | 0.7689 | 0.6099 | 0.1590 | 0.4591 | 0.6497 | 1069 |
| cnn_1d | F | 0.1111 | 0.0000 | 0.1111 | 0.0069 | 0.0000 | 18 |

按训练集频数计算的正式类权重（N/S/V/F）为：`0.2749, 13.3521, 3.7888, 43.7597`。消融图：[`class_weight_validation_ablation.png`](../../figures/09_multiclass_classification/class_weight_validation_ablation.png)。

## 当前限制与下一阶段建议

- 结果仅反映本次固定受试者划分和 44 条非起搏 MIT-BIH 记录；数据源包含有意选择的少见心律片段，不是普通人群患病率样本。不能把分类结果描述为临床诊断。
- 模型使用单导联 253 点心拍窗口，固定窗可能含邻拍；记录之间导联、患者形态和滤波影响仍存在。除患者级隔离外，窗口标注位置仍沿用专家 `.atr`，没有另做 R 峰检测或临床专家复核。
- 44 记录的 S/F 在记录与患者之间分布稀疏；解释四分类时需同时报告每类样本支持数、患者数、Recall、Macro-F1 与混淆矩阵。不能通过随机心拍拆分增加稀有类测试量。
- 下一阶段可开发课程演示用只读 Web 可视化：记录/导联/时间窗浏览、原始与滤波信号并列、标注位置及原始符号/AAMI 映射说明、可筛选类别分布、患者级分区说明、测试混淆矩阵和模型概率。明确注明版本/划分/模型哈希、概率非临床诊断，默认禁止浏览器上传或覆写原始数据；模型阈值/校准只在验证集拟定，测试集保持锁定。
## 文件入口

- 数据预处理：`data/processed/mitdb44_nv_v1/` 与 `data/processed/mitdb44_nsvf_v1/`。
- 训练日志和预测：`results/classification/nv44_v1/`、`results/classification/nsvf44_v1/`。
- 模型权重：`checkpoints/nv44_v1/`、`checkpoints/nsvf44_v1/`。
- 图像：`figures/07_preprocessing/`、`figures/08_binary_classification/`、`figures/09_multiclass_classification/`。
