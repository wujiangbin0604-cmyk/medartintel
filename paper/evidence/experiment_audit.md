# ECG-AI 实验素材审计

核验时间：2026-11-05T00:27:09.588526+08:00

本次仅读取现有工件、重算指标并核对源码；没有重新训练、改变模型、修改原始数据或重新选择方案。

## 核验方法与证据等级

1. 数据数量从两个数据集的 `metadata.csv` 中筛选 included=True 后重新分组统计；逐一核对六个 NPZ 的行顺序、样本 ID、标签、患者 ID、形状和归一化。
2. 正式测试指标从六个逐模型 `test_predictions_*.csv` 重新计算 Accuracy、各类 Precision/Recall/F1、Macro-F1 和混淆矩阵，均与保存的 JSON 一致（数值容差 1e-12）。
3. 四种 CNN 权重验证指标从 `weight_strategy_validation_predictions.csv` 重算；五折的15组指标及 pooled OOF 从三个 OOF CSV 重算；检查每位患者组外层无交叉、每个样本恰好一次 OOF、正式测试患者不进入 CV。
4. 历史训练设置和早停来自 config.json、training_logs.json 与源码。已有传统模型权重对照及权重实验训练集指标仅核对保存表，不声称此次从预测逐条重算。
5. 原始 WFDB 标注逐条读取与哈希核对沿用项目已有 preprocessing_audit.json/verification.json；此次另外重新检查 metadata 与 NPZ 对齐，不把历史审计描述为本次全流程重跑。

逐文件哈希及所有数据表保存在 `paper/evidence/verified_metrics.json` 的 source_inventory 与各节。

## 数据与标签

正式数据入口为 `src/datasets/build.py`；`src/preprocessing/pipeline.py` 是早期48记录流程，不应用其配置代替正式44记录实验。官方48条记录中排除102、104、107、217。44记录对应43个受试者组，201与202共用subject_201_202。组ID由记录推导；这是已知重复患者的显式合并，并非另外取得的身份识别结果。

AAMI映射：N={N,L,R,e,j}；S={A,a,J,S}；V={V,E}；F={F}；Q={/,f,Q}。Q与非心拍、未映射符号不进入当前二/四分类。N不能解释为绝对健康，N/V分类不覆盖S、F、Q及所有心脏病。

### NV 实际样本划分

| 划分 | 心拍数 | 受试者 | 记录 | N | V |
|---|---:|---:|---:|---:|---:|
| train | 70183 | 31 | 32 | 65436 | 4747 |
| val | 12923 | 6 | 6 | 11854 | 1069 |
| test | 13448 | 6 | 6 | 12287 | 1161 |

### NSVF 实际样本划分

| 划分 | 心拍数 | 受试者 | 记录 | N | S | V | F |
|---|---:|---:|---:|---:|---:|---:|---:|
| train | 71941 | 31 | 32 | 65436 | 1347 | 4747 | 411 |
| val | 14345 | 6 | 6 | 11854 | 1404 | 1069 | 18 |
| test | 13829 | 6 | 6 | 12287 | 10 | 1161 | 371 |

两任务共享完全相同患者划分与N/V样本ID。训练/验证/测试受试者31/6/6，无交叉；100和200因已探索固定为训练记录。分配协议为单次固定seed 20261027、约70%/15%/15%，按V注释数≥100分层，并预设留出V数量，不做性能驱动的反复分割。

### 四分类总体及患者覆盖

| 类别 | 有效心拍 | 占比% | 有该类的受试者 | 最大患者 | 该患者份额% |
|---|---:|---:|---:|---|---:|
| N | 89577 | 89.4741 | 43 | subject_201_202 | 4.1015 |
| S | 2761 | 2.7578 | 31 | subject_232 | 49.8370 |
| V | 6977 | 6.9690 | 32 | subject_208 | 14.1178 |
| F | 800 | 0.7991 | 16 | subject_208 | 46.2500 |

| 划分 | 类别 | 心拍 | 有该类的受试者/划分总数 | 记录 | 最大患者 | 其份额% |
|---|---|---:|---:|---:|---|---:|
| train | N | 65436 | 31/31 | 32 | subject_201_202 | 5.6146 |
| train | S | 1347 | 23/31 | 24 | subject_209 | 28.4336 |
| train | V | 4747 | 23/31 | 24 | subject_200 | 17.3162 |
| train | F | 411 | 10/31 | 11 | subject_213 | 88.0779 |
| val | N | 11854 | 6/6 | 6 | subject_215 | 26.7926 |
| val | S | 1404 | 5/6 | 5 | subject_232 | 98.0057 |
| val | V | 1069 | 4/6 | 4 | subject_233 | 77.1749 |
| val | F | 18 | 4/6 | 4 | subject_233 | 61.1111 |
| test | N | 12287 | 6/6 | 6 | subject_212 | 22.2430 |
| test | S | 10 | 3/6 | 3 | subject_219 | 70.0000 |
| test | V | 1161 | 5/6 | 5 | subject_208 | 84.8407 |
| test | F | 371 | 2/6 | 2 | subject_208 | 99.7305 |

`split_class_counts.csv`中各类subject_count/record_count已与metadata独立重算一致，使用的是修正后的类别覆盖数，不能用split总记录数替代。

## 预处理与模型结构

实际全部有效样本使用MLII导联、360Hz、mV。先对连续有限信号段以0.5–40Hz Butterworth SOS作sosfiltfilt离线双向滤波；原型阶数4，对应单次带通8阶，双向幅频响应为单次响应绝对值的平方。每段两端保留5秒保护区，因此不能称为因果实时滤波。

以专家注释位置r为中心截取[r−108,r+145)共253点，包含−0.3秒与+0.4秒端点，中心索引108。窗口越界、滤波边界/间断保护区、非有限、平坦、重复目标位置等技术失败会排除；大振幅或形态质量标记本身不等同于排除。

归一化为单一标量z-score：(x_filtered−μ_train)/σ_train，均值/标准差仅由有效训练心拍的全部采样点估计，ddof=0，不进行逐拍重缩放或截断。LR在253维向量上另用仅训练集拟合的逐维StandardScaler；RF直接用已做标量标准化的253维向量。

| 任务 | μ_train mV | σ_train mV | 训练心拍 |
|---|---:|---:|---:|
| NV | 0.010122829269 | 0.342252550699 | 70183 |
| NSVF | 0.010091383343 | 0.343942295235 | 71941 |

| CNN层 | 输出 | 参数量 |
|---|---|---:|
| Input | B × 1 × 253 | 0 |
| Conv1d 1→16 k7 p3 + ReLU | B × 16 × 253 | 128 |
| MaxPool1d k2 stride2 | B × 16 × 126 | 0 |
| Conv1d 16→32 k5 p2 + ReLU | B × 32 × 126 | 2592 |
| MaxPool1d k2 stride2 | B × 32 × 63 | 0 |
| Conv1d 32→64 k3 p1 + ReLU | B × 64 × 63 | 6208 |
| AdaptiveAvgPool1d 1 + squeeze | B × 64 | 0 |
| Linear 64→K | B × K | 65K |

B为批量、K为类别数；总参数N/V为9058，四分类9188。无BatchNorm、Dropout、LSTM或显式RR间期分支。softmax用于推理概率，训练接收logits。

LR：C=1、balanced、lbfgs、max_iter=1000、tol=0.001。RF：100棵树、max_depth=18、min_samples_leaf=2、max_features=sqrt、balanced_subsample、bootstrap=True、max_samples=0.8、n_jobs=−1。三模型seed=20261027。CNN使用Adam、学习率0.001、weight_decay=1e−5、batch=256、最多25轮、patience=5、加权交叉熵；权重n/(K n_c)仅由训练集计算，按验证Macro-F1保存最佳检查点。

| 任务 | 实际轮次 | 最佳轮次 | 最佳验证Macro-F1 | CPU/权重向量 |
|---|---:|---:|---:|---|
| NV | 17 | 12 | 0.663009 | cpu / [0.5362721085548401, 7.392353057861328] |
| NSVF | 16 | 11 | 0.473463 | cpu / [0.2748525142669678, 13.352078437805176, 3.7887613773345947, 43.75973129272461] |

## 正式测试指标 独立重算

以下均为test_predictions文件，不是验证集指标；只沿用历史测试，不重新调参。

### NV

| 模型 | Accuracy | Macro-F1 | 类别 | Precision | Recall | F1 | 支持数 |
|---|---:|---:|---|---:|---:|---:|---:|
| logistic_regression | 0.836927 | 0.696073 | N | 0.989240 | 0.830553 | 0.902977 | 12287 |
| logistic_regression | 0.836927 | 0.696073 | V | 0.335249 | 0.904393 | 0.489168 | 1161 |
| random_forest | 0.983492 | 0.949409 | N | 0.994508 | 0.987385 | 0.990934 | 12287 |
| random_forest | 0.983492 | 0.949409 | V | 0.875901 | 0.942291 | 0.907884 | 1161 |
| cnn_1d | 0.995687 | 0.986520 | N | 0.999102 | 0.996175 | 0.997636 | 12287 |
| cnn_1d | 0.995687 | 0.986520 | V | 0.960735 | 0.990525 | 0.975403 | 1161 |

### NSVF

| 模型 | Accuracy | Macro-F1 | 类别 | Precision | Recall | F1 | 支持数 |
|---|---:|---:|---|---:|---:|---:|---:|
| logistic_regression | 0.742281 | 0.359915 | N | 0.980436 | 0.754537 | 0.852780 | 12287 |
| logistic_regression | 0.742281 | 0.359915 | S | 0.004178 | 0.600000 | 0.008299 | 10 |
| logistic_regression | 0.742281 | 0.359915 | V | 0.352855 | 0.830319 | 0.495248 | 1161 |
| logistic_regression | 0.742281 | 0.359915 | F | 0.117073 | 0.064690 | 0.083333 | 371 |
| random_forest | 0.953648 | 0.465616 | N | 0.972888 | 0.987141 | 0.979963 | 12287 |
| random_forest | 0.953648 | 0.465616 | S | 0.000000 | 0.000000 | 0.000000 | 10 |
| random_forest | 0.953648 | 0.465616 | V | 0.854722 | 0.912145 | 0.882500 | 1161 |
| random_forest | 0.953648 | 0.465616 | F | 0.000000 | 0.000000 | 0.000000 | 371 |
| cnn_1d | 0.769036 | 0.445969 | N | 0.976320 | 0.771791 | 0.862091 | 12287 |
| cnn_1d | 0.769036 | 0.445969 | S | 0.000000 | 0.000000 | 0.000000 | 10 |
| cnn_1d | 0.769036 | 0.445969 | V | 0.854491 | 0.991387 | 0.917863 | 1161 |
| cnn_1d | 0.769036 | 0.445969 | F | 0.007194 | 0.002695 | 0.003922 | 371 |

N/V CNN混淆矩阵（行真值N,V；列预测N,V）=[[12240,47],[11,1150]]，共58错。四分类CNN主要错误N→S=2626、F→N=216、F→V=154。四分类RF虽然Accuracy更高，但S与F召回均为0；CNN的S召回为0，F仅1/371。不能据总体准确率推导各类别均有效。

N/V CNN验证Macro-F1仅0.663009而正式测试为0.986520，应说明固定划分患者组成明显影响结果；高测试分数不能单独证明患者间稳定性。

## 类别权重消融

四种CNN权重策略都在既有train训练、validation比较，检查点同样使用validation早停，因此这是探索性调参与诊断证据。平方根策略是sqrt(n/(K n_c))后除以权重均值；截断策略先min(n/(K n_c),10)再除以均值；全逆频率策略不作均值归一化。不能声称截断前已mean-one。

| 策略 | 验证Accuracy | 验证Macro-F1 | N召回 | S精确率/召回 | F精确率/召回 | 预测S/F占比% |
|---|---:|---:|---:|---:|---:|---:|
| unweighted | 0.851934 | 0.391421 | 0.975957 | 0.000000/0.000000 | 0.000000/0.000000 | 0.0000/0.0000 |
| sqrt_inverse | 0.833461 | 0.396188 | 0.948962 | 0.000000/0.000000 | 0.006250/0.111111 | 0.0000/2.2307 |
| capped_inverse_10 | 0.658975 | 0.413761 | 0.631264 | 0.372340/0.698006 | 0.000000/0.000000 | 18.3479/0.2858 |
| full_inverse | 0.718508 | 0.473463 | 0.689725 | 0.469300/0.930912 | 0.003578/0.111111 | 19.4144/3.8968 |

传统模型既有加权/无权重验证表见JSON的existing_model_weight_reference。其效应不同：LR Macro-F1从加权0.2637到无权重0.3371；RF从0.4019到0.4090；CNN从加权0.4735到无权重0.3914。均只描述此划分与配置，不能断言任何权重普遍有效或普遍有害。

## 五折受试者分组交叉验证

只用原train+validation的86286拍、37患者组，StratifiedGroupKFold五折、shuffle=True、seed=20261028。每个外折中患者无交叉；CNN以外层训练患者的四折分组方案选一个有效内层早停划分，再按该内层最佳epoch在完整外层训练集重拟合。标量归一化与类别权重都只由相应训练组拟合；正式test六患者完全未进入CV。

| 模型 | 外折Macro-F1均值 | 样本标准差 ddof=1 | pooled OOF Macro-F1 | 各折Macro-F1 |
|---|---:|---:|---:|---|
| logistic_regression | 0.304687 | 0.037711 | 0.293136 | 0.2489, 0.3186, 0.2900, 0.3161, 0.3499 |
| random_forest | 0.417258 | 0.042395 | 0.405385 | 0.3581, 0.4360, 0.4136, 0.4050, 0.4736 |
| cnn_1d | 0.356418 | 0.062353 | 0.353530 | 0.3453, 0.4473, 0.3864, 0.2904, 0.3127 |

各折F支持为5、17、5、37、365，极不均匀。各折所有四类均有真实支持，所以本次macro_f1_present_classes与固定四类Macro-F1相同；不应推广到缺类患者指标。配置此前已依据原验证行为确定，故CV虽无患者重叠，仍是探索性稳定性诊断，不是完全未触碰的独立或外部验证。

## 真实错误案例

可直接引用的四分类最终选择表：`results/classification/nsvf44_v1/diagnosis/final_error_case_samples_descriptive_only.csv`。212:1427（record212，329145，原符号R）N→S；208:1482（313756，F）F→N；208:1293（271553，F）F→V；116:1799（488586，V）V→N。均为既有测试回顾，用于定性展示，不作为选模依据。

诊断六面板图源 `figures/11_four_class_diagnosis/cnn_test_error_waveforms_descriptive_only.png` 对应的案例表为 `cnn_test_error_waveform_cases_descriptive_only.csv`；勿把不同选择表中的ID误配给该图。最终重绘样本另见 figures/12_final_report 下的索引（由主写作流程核对）。N/V错误候选及原始预测概率已保存在JSON的error_examples.nv。

## 环境与可复现边界

数据构建environment.json记录Python 3.12.10、NumPy 2.5.4、Pandas 3.1.0、WFDB 4.3.1、SciPy 1.18.1、Scikit-learn 1.9.1；requirements-lock.txt固定torch 2.14.1。训练日志明确device=cpu。锁文件描述可复现依赖，不是训练当时逐包运行时探针；操作系统和CPU具体型号若无额外日志，不应凭空填写。当前捆绑审计解释器版本与历史训练依赖不同。

复查命令：使用捆绑Python运行 `paper/tools/audit_experiments.py`。脚本只读取原有数据/结果，更新paper/evidence下两个核验文件，不训练。

## 应写入论文的限制

- Fixed test already exposed historically; present audit is retrospective and does not restore independence.
- Cross-validation uses previously explored train+validation and fixed choices, so it is exploratory rather than external validation.
- N includes L/R/e/j and does not mean clinical health; NV excludes S/F/Q from task.
- Test F 370/371 beats are from subject_208; test S has only 10 beats and 3 subjects.
- N/V CNN validation Macro-F1 is 0.6630 versus test 0.9865, evidencing substantial split-dependent behavior.
- Filter is offline noncausal continuous-segment sosfiltfilt with five-second edge guards; not a causal online algorithm.
- Models require expert annotation centers, and contain no explicit RR interval or rhythm-context input.
- Legacy src/preprocessing/pipeline.py is an older 48-record pipeline; final 44-record artifact is src/datasets/build.py.
- Recorded environment JSON and lockfile describe historical runs; current bundled audit environment differs and is not the training environment.

## 核验结论

六个正式测试预测文件、四策略验证预测、十五个外折指标均重算匹配；元数据与NPZ对齐、患者互斥、201/202合并及修正后的类别患者/记录覆盖均通过。不能由此推断模型有临床有效性，也不能把已暴露测试再次命名为全新盲测。
