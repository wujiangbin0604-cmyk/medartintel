# ECG-AI · MIT-BIH 心电教学与人工智能实验平台

包含 ECG 波形浏览、六个已训练模型的心拍分类、科研结果与图集、Heartbeat Hunter 心电互动游戏，以及完整的实验源码和课程论文资料。前端为 React/Umi，后端为 FastAPI/PyTorch。仅用于课程教学与算法研究。

- **线上体验**：[打开 ECG-AI 工作台](http://47.83.150.55:8000/dashboard)
- **GitHub 仓库**：[wujiangbin0604-cmyk/medartintel](https://github.com/wujiangbin0604-cmyk/medartintel)
- **本地部署**：[Windows / Linux / Docker 完整说明](DEPLOY_LOCAL.md)
- **云服务器部署**：[Ubuntu 22.04 部署说明](deploy/ubuntu22/README_UBUNTU_22.04.md)

## 从 GitHub 下载并本地运行

```bash
git clone https://github.com/wujiangbin0604-cmyk/medartintel.git
cd medartintel
```

Windows 安装 **Python 3.12** 后，在 PowerShell 执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```

Linux（Python 3.12）执行 `bash start-local.sh`。首次自动建立虚拟环境并安装固定的 CPU 推理依赖，以后使用本地环境启动。无需重新训练模型，也无需安装 Node.js。页面打开 [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)，按 Ctrl+C 停止。

已有 Docker Desktop（Linux containers）或 Docker Engine + Compose 时，也可在项目根目录执行：

```bash
docker compose up -d --build --wait --wait-timeout 240
```

仓库随附前端构建、48 条 MIT-BIH 原始记录、六个正式模型及网页需要的结果文件；不上传虚拟环境、node_modules、个人游戏记录或可重新生成的大型训练 NPZ/metadata.csv。需要训练时按下面的研究流程从原始数据重建。科研阶段记录保留在后文，其中早期阶段的范围只描述当时工作。

## 研究流程与阶段记录

项目按阶段包含全库数据探索、可复现的信号预处理与受试者独立分类基线。第一阶段只分析记录 100、200；第二阶段建立 48 条记录的预处理审计数据；第三阶段另用排除起搏记录后的 44 条数据完成 N/V 和 N/S/V/F 基线实验。原始 WFDB 文件保持不变。

## 第二阶段：预处理与受试者独立数据集

第二阶段使用官方 **全部 48 条记录**，构建 N/V 数据文件，仍不训练任何分类器或深度模型、不开发前端。

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# 原始数据不完整时先补齐（官方 S3 镜像，官方 SHA256 核验，已有原始文件不覆盖）
.\.venv\Scripts\python.exe -m src.download --records all --mirror s3 --workers 4
# 完全离线构建/复跑全部记录
.\.venv\Scripts\python.exe -m src.preprocess --offline
```

成果位于 `data/processed/nv_v1/`：

| 文件 | 用途 |
| --- | --- |
| `train.npz`、`val.npz`、`test.npz` | 归一化单导联数组及逐样本来源 |
| `metadata.csv` | 全部原始标注，包括未入训练数据的类别与被排除窗口；`npz_row` 指向对应文件行号 |
| `split_manifest.csv`、`split_plan.json` | 全部记录的受试者及锁定分区，201/202 共享一组 |
| `processing_config.json` | 原始标签映射、滤波 SOS 系数、窗口及质量规则、种子和防泄漏政策 |
| `normalization.json` | 仅训练集拟合的均值/标准差、训练样本 ID 哈希及来源清单 |
| `training_class_weights.json` | 仅按训练标签计算的可选类权重，尚未应用 |
| `verification.json` | 数组/元数据/原标注一致、数据有限、受试者无交集等校验 |

查看 [预处理报告](reports/preprocessing_report.md)；图位于 `figures/preprocessing/`；全库原始标签计数、形态变化审计、排除计数和完整性信息位于 `results/preprocessing/`。

处理流程：实际 MLII 优先，否则首导联；先对连续有限信号执行 0.5–40 Hz Butterworth SOS 双向滤波，再用专家标注前 0.3 s、后 0.4 s 的**含端点 253 点窗口**截取。记录两端和非有限缺口两侧设 5 s 滤波保护区。边界/非有限/平直/重复目标位置等技术问题被明确记录；幅值大、ADC 触轨和形态变化只作保留样本的复核标记，不按外观改标签。

N←N/L/R/e/j，V←V/E，默认编码 N=0、V=1；其余类别仍保留原始文件与元数据。100、200 已被前期探索，固定放训练集；其余按受试者与预声明的 V 类覆盖约束一次性分层划分，约 70/15/15 对应受试者比例。201/202 必须在同一集合。分区在滤波比较前写入并锁定，不允许静默更换种子或依据测试表现重新划分。候选滤波比较仅用训练记录；没有过采样、欠采样或 SMOTE。

`X` 形状为 `(样本数, 1, 253)`，float32；`X_filtered` 为对应的滤波后 mV 信号；`y` 为 int64。所有分区使用同一个训练集标量均值/标准差，未逐拍缩放或按测试范围裁剪。加载示例：

```python
from pathlib import Path
import numpy as np

dataset_dir = Path('data/processed/nv_v1')
with np.load(dataset_dir / 'train.npz', allow_pickle=False) as data:
    X, y = data['X'], data['y']
    record_ids = data['record_id']
    original_positions = data['annotation_sample']
```

未来多分类可在新版本目录复用同一受试者分区：

```powershell
.\.venv\Scripts\python.exe -m src.preprocess --offline --classes N S V F --output-dir data/processed/nsvf_v1 --split-plan data/processed/nv_v1/split_plan.json
```

原始 `.dat/.hea/.atr` 始终保留；N 组不等于全部医学正常，N/V 任务也不覆盖所有异常。双向滤波依赖未来采样，当前成果是离线数据集，实时任务需要另行设计因果滤波。保留的质量问题、导联差异、稀有类与患者差异应在下一阶段训练/验证侧处理；测试集继续锁定。

## 第三阶段：44 条记录基线分类实验

在保留上述 48 条全库审计与预处理产物的基础上，分类实验另建**排除 102、104、107、217 的 44 条非起搏记录版本**。PhysioNet 目录说明这四条记录含起搏心拍，原始模拟记录对常见起搏器伪迹识别方式保真不足；原始文件仍完整保留。新实验的滤波窗口与归一化在 44 条记录上独立重做，避免把被排除记录的信号用于当前模型。

```powershell
# 建 N/V 数据集；生成 44 条记录的锁定患者划分与全库/44条标签计数
.\.venv\Scripts\python.exe -m src.datasets.build --classes N V --output-dir data/processed/mitdb44_nv_v1 --offline

# 必须先通过小规模烟雾运行，再训练完整 N/V 基线
.\.venv\Scripts\python.exe -m src.classify --task nv --smoke-test
.\.venv\Scripts\python.exe -m src.classify --task nv

# 只有 N/V 正式训练、验证、预测与指标复核完成后才允许继续
.\.venv\Scripts\python.exe -m src.datasets.build --classes N S V F --output-dir data/processed/mitdb44_nsvf_v1 --split-plan data/processed/mitdb44_nv_v1/split_plan.json --offline
.\.venv\Scripts\python.exe -m src.classify --task nsvf --smoke-test
.\.venv\Scripts\python.exe -m src.classify --task nsvf
```

44 条实验以患者组为单位，按约 70/15/15 的目标比例得到 31/6/6 个 train/validation/test 患者组，对应 32/6/6 条记录；100、200 因前期已经查看而预先只放训练集。记录 201、202 合并成一个受试者组。稀有类在留出患者的覆盖有限，特别是四分类 S/F 需要结合实际 support、各类 Recall、Macro-F1 和混淆矩阵解释。模型配置位于 `configs/`；模型及日志分别保存在 `checkpoints/`、`results/classification/`。实验总报告为 `reports/classification/experiment_summary.md`；预处理与分类图分别位于 `figures/07_preprocessing/`、`figures/08_binary_classification/`、`figures/09_multiclass_classification/`。

`requirements.txt` 记录跨环境的兼容版本范围；`requirements-lock.txt` 是本次验证环境的精确包版本快照（Python 3.12.10、Windows、CPU-only PyTorch）。项目代码面向 Python 3.10+，但本次未在 Python 3.10 运行验证。

模型限于 Logistic Regression、Random Forest 与 1D-CNN 基线。CNN 使用加权 CrossEntropyLoss 与验证集 Macro-F1 早停；类别权重只从训练集计算。测试集只在三个模型完成拟合、保存检查点后评估一次；代码从测试预测 CSV 独立重算并核对指标。CNN 的概率和类别分数是课程实验输出，不是临床诊断结果。

## 四分类失败诊断（新增）

对已完成的 N/S/V/F 四分类做患者类别覆盖、患者级既有测试错误回顾、CNN 权重策略 train/validation 对照和五折受试者分组 CV。默认命令会重新运行权重对照与 CV，二者只使用 train/validation；历史正式测试预测只用于已查看结果的分患者统计和典型错误波形，不参与新拟合/调参。报告及交叉验证会显式说明原验证集已经用于早停，因此 CV 属探索性结果。

```powershell
.\.venv\Scripts\python.exe -m src.evaluation.four_class_diagnosis
# 如果只需重建报告和图，复用已保存的训练/交叉验证结果：
.\.venv\Scripts\python.exe -m src.evaluation.four_class_diagnosis --skip-weights --skip-cv
```

查看 [四分类失败诊断报告](reports/classification/four_class_failure_diagnosis.md)；统计表、患者级指标、OOF 预测、权重策略日志和完整性核验位于 `results/classification/nsvf44_v1/diagnosis/`；诊断图位于 `figures/11_four_class_diagnosis/`。

## 最终实验结果核验与课程报告（新增）

独立复算已保存的 N/V 与 N/S/V/F 测试预测、核验 split 统计并生成整合报告；不重新训练模型。测试集此前已查看，本工具只用于指标核对和错误示例描述，不用于新拟合或调参。

```powershell
.\.venv\Scripts\python.exe -m src.evaluation.final_report
```

完整报告、核验记录、图表索引和项目完成情况位于 `reports/final/`。结果复算表位于 `results/classification/final_*`；新增报告图片位于 `figures/12_final_report/`。

## A–F 可视化图集（新增）

新版入口生成分布、原始波形、单心拍形态、节律、质量、PCA/t-SNE 六类图集，并为**本轮每张图**自动写出用途、计算结果、解释边界和数据范围。

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.visualize --records 100 200 --offline
```

阅读 [逐图可视化报告](reports/visualization_summary.md)。本轮新图统一在 `figures/A_distribution/`、`B_waveforms/`、`C_morphology/`、`D_rhythm/`、`E_quality/`、`F_embedding/`，均为 300 dpi PNG。统计与追溯表独立放在 `results/visualization/`；`figure_catalog.csv` 是本轮全部图的唯一清单，`verification.json` 是完整性检查结果。此前第一阶段报告和输出继续保留。

```powershell
# 固定随机种子与 t-SNE 参数，完全离线重跑
.\.venv\Scripts\python.exe -m src.visualize --records 100 200 --offline --seed 20261027 --perplexities 15 40

# 扩展至全库；需联网下载尚未存在的原始文件
.\.venv\Scripts\python.exe -m src.visualize --records all

# 调整探索性降维的抽样计算量
.\.venv\Scripts\python.exe -m src.visualize --records 100 200 --offline --embedding-per-stratum 500 --embedding-max 3000
```

模块组织：加载复用 `src/io.py`，映射复用 `src/labels.py`，片段截取与描述量为 `src/heartbeat.py`；六类绘图位于 `src/visuals/`；报告生成为 `src/visualization_report.py`；主入口为 `src/visualize.py`。

随机 20 拍采用固定种子、不放回抽取；不足 20 拍全取，缺失类别显示缺失，绝不复制生成假样本。`plotted_heartbeat_windows.csv` 保存叠图/网格所选每拍的记录、导联、原始样本和时间。网格以距类均值最近及不同峰峰值排序位置选例，所有波形都来自真实信号。

形态与降维按同一导联名称独立处理；窗口默认前 0.25 s、后 0.45 s。`heartbeat_features.csv` 含有效窗口的峰峰值、最大/最小值、`sum(x²)/fs` 物理能量和减中位数后的能量。`all_beat_metadata.csv` 保留未能提取窗口的心拍、边界原因及完整 RR；RR 不跨记录、不把非心拍当邻居。图中的非 N 比例是 `(S+V+F+Q)/已映射心拍`，并非临床异常患病率。

PCA 对全部有效同导联窗口投影；t-SNE 按记录×类别各最多 500 拍，再在总数超过 3000 时按层均衡分配，保留小样本层，不放回抽取。降维前比较“各窗减中位数”和“再除以各窗 RMS”两个版本；t-SNE 预先 PCA 到最多 50 维。相同投影分别按类别、记录着色，并比较 perplexity=15/40。精确点坐标、原始标签、参数与解释率分别保存在 `embedding_coordinates.csv`、`embedding_parameters.csv`、`pca_explained_variance.csv`。这只是无监督探索，不是训练分类器，投影分离或 KL 数值不能当作分类性能。小数据运行时，perplexity 必须小于抽样窗口数。

质量图中的 1 s 块中位数仅是基线/幅值漂移候选代理；宽心拍与突变伪迹也可能影响它。阈值 0.5 mV 只用于选择示意片段，不自动判定噪声或删样本。报告的额外视觉核查绑定原始数据哈希和运行配置，不同数据或参数不会套用旧观察。

## 环境与安装

Python 3.10+，推荐 Windows PowerShell。请将项目放在当前用户有修改权限的目录；脚本不会修改原始数据。首次下载约 4 MB 的两条记录，需联网到 PhysioNet；全 48 条信号约 94 MB（另加头文件和标注）。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src --records 100 200
```

不需要激活虚拟环境，因此不受 PowerShell Activate.ps1 执行策略影响。Linux/macOS 对应使用 `.venv/bin/python`。`requirements.txt` 给出兼容范围；已验证环境的精确版本在 `requirements-lock.txt`，需要尽量复现本次环境时使用 `pip install -r requirements-lock.txt`。

## 重复运行与扩展

```powershell
# 本地原始文件与官方校验清单齐全后，完全离线重跑
.\.venv\Scripts\python.exe -m src --records 100 200 --offline

# 扩展至官方 RECORDS 清单中的全部 48 条记录
.\.venv\Scripts\python.exe -m src --records all

# 更换片段范围；按实际采样率取最近整数采样点
.\.venv\Scripts\python.exe -m src --records 100 200 --offline --pre-s 0.25 --post-s 0.45

# 独立输出目录；已下载原始数据需在该目录的 data/mitdb 中
.\.venv\Scripts\python.exe -m src --root E:\ecg_results --records 100 200

# 规则与窗口边界检查
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

默认项目根目录由代码位置确定，与终端当前目录无关。命令应在项目根目录执行以找到 `src` 模块。已有 `.dat/.hea/.atr` 永不覆盖：文件哈希不符时直接失败；应另选输出目录获取干净副本，不要改写原文件。派生 CSV、图和报告会被同名新结果替换。切换记录后，以本轮 `results/figure_manifest.csv` 为准，旧轮图片不自动删除。`--records all` 逐条处理下载、绘图，内存中保留全库信号以汇总，建议至少 4 GB 可用内存。当前交付仅实测 100、200，未实际下载分析全库。

## 目录

```text
data/mitdb/       官方 RECORDS、SHA256SUMS.txt、记录 .dat/.hea/.atr
data/processed/  历史全48条数据集；mitdb44_nv_v1 与 mitdb44_nsvf_v1 分类数据
src/             download.py/io.py/labels.py/analysis.py/visuals/visualize.py
src/preprocessing/ 连续滤波、心拍截取、训练集归一化、患者划分与审计
src/datasets/    44条数据构建、全48/44条标签统计与预处理绘图
src/models/      Logistic Regression、Random Forest、1D-CNN
src/training/    固定种子Smoke Test、正式训练、早停与日志
src/evaluation/  预测指标、混淆矩阵、误差图、报告和独立产物核验
configs/         binary_nv.json、multiclass_nsvf.json
checkpoints/     传统模型与CNN权重、Smoke Test和权重消融检查点
figures/         原67张探索图、07_preprocessing、08_binary_classification、09_multiclass_classification
results/         全库标签、划分、预测CSV、训练日志、指标JSON与final_verification.json
reports/         数据探索、可视化、预处理与classification/experiment_summary.md
tests/           标签、滤波、切片、患者划分、CNN形状和指标检查
requirements.txt / requirements-lock.txt
README.md
```

先阅读 [探索报告](reports/data_exploration.md)。重点结果如下：

| 文件 | 内容 |
| --- | --- |
| `results/raw_symbol_counts.csv` | 所有实际出现的原始 symbol 及数量，包含非心拍 |
| `results/label_mapping.csv` | 全部已知符号定义、中文、分组、数量、公开来源；0 次保留 |
| `results/aami_counts.csv` | 五组数量和占比，0 次类别保留；分母仅为已映射心拍 |
| `results/aami_counts_by_record.csv` | 分记录数量和记录内占比 |
| `results/annotations.csv` | 全部原始字段、样本编号、秒数及标注处导联幅值 |
| `results/annotations.jsonl` | 保留原始 aux_note 的 NUL 终止符，提供无损 JSONL 输出及往返验证 |
| `results/non_beat_annotations.csv` | 非心拍逐条记录，包括节律、质量与伪迹信息 |
| `results/unmapped_or_unknown_annotations.csv` | 映射规则以外心拍/未知项，不猜测类别 |
| `results/beats.csv` | 全心拍及窗口有效性、起止样本、相邻 RR、主导联窗口峰峰值 |
| `results/plotted_beats.csv` | 每个示例图中实际绘出的心拍及完整边界 |
| `results/signal_quality.csv` / `quality_windows.csv` | 全导联幅值、缺失、触轨、平直段与 10 秒质量代理 |
| `results/morphology_summary.csv` | 全部有效窗口的幅值范围及相邻 RR 描述统计 |
| `results/record_metadata.csv` | 采样率、导联、时长、头文件注释、对应验证 |
| `results/download_manifest.csv` | 官方来源 URL、字节数和 SHA256 核验 |
| `results/figure_manifest.csv` | 本轮全部图片及记录/导联/时间范围 |
| `results/verification.json` | 输出存在性、计数平衡、标注时间、窗口边界、原始数据未修改等验证 |

CSV 使用 UTF-8 BOM；若用 Excel 查看原始符号/aux_note，应按文本导入，保留 `+`、`=` 等字符串。部分原始 aux_note 含 NUL 终止符，普通 CSV 解析器可能截断；`aux_note_json` 可经 `json.loads` 无损还原，`aux_note_text` 仅去除尾部 NUL 方便显示，完整原始标注也保存为 `annotations.jsonl`。`sample` 从 0 开始；秒数为记录内相对时间；窗口 stop 列为 Python 切片的右开端点。

## 标签和观察约束

严格使用指定映射：N←N,L,R,e,j；S←A,a,J,S；V←V,E；F←F；Q←/,f,Q。`symbol` 与 `aami_group` 分列，大小写敏感。非心拍单独保存；不依赖模型或形态改写专家标注。N 组并不等于全是正常心拍，Q 组并不等于全是伪迹。`!` 和 `x` 按官方定义为非心拍，扩展全库时不会误当作心拍。

双导联原始幅值图与带标注图均用实际物理单位。类间对比优先 MLII，缺少时才使用首导联。片段以原始专家标注为中心，**没有重新定位 R 峰**。默认前 0.25 s、后 0.45 s，360 Hz 时 253 点（含中心和末点）；越界只跳过绘图窗口，不删计数。组内图左侧原始幅值，右侧仅减去窗口中位数方便观察；未更改原始数据。固定窗口可能含邻拍，峰峰值不能当作 QRS 宽度或单拍幅值。

质量指标仅供探索：大幅值/高差分不必然是噪声，未触轨不代表无伪迹；没有自动删样本。报告将统计、实际视觉观察和可能解释分开。开发助手的视觉备注只在所绑定原始文件哈希及窗口参数完全匹配时加入报告，扩展全库不会误套用 100/200 的观察；未经过额外心电专家复核。

未来模型划分应按患者独立，**201 和 202 同属一位受试者**。本项目没有随机心拍级划分，也不输出模型结果。

## 来源

- [MIT-BIH 官方数据库 1.0.0、许可与引用要求](https://physionet.org/content/mitdb/1.0.0/)
- [PhysioNet 原始标注符号定义](https://physionet.org/static/lightwave/doc/annotations.html)
- [官方记录目录及记录 100/200 说明](https://physionet.org/files/mitdb/1.0.0/mitdbdir/records.htm)
- [WFDB Python 官方读入接口](https://wfdb.readthedocs.io/en/latest/io.html)
- [de Chazal et al. 2004，AAMI 五组映射文献](https://doi.org/10.1109/TBME.2004.827359)

数据原作者：Moody GB, Mark RG. The impact of the MIT-BIH Arrhythmia Database. IEEE Eng Med Biol Mag. 2001;20(3):45–50. DOI: 10.1109/51.932724。使用数据发表成果时请遵循官方页面的许可与引用要求。

## 第二阶段：本地 ECG-AI 教学工作台

第二阶段 Web/API 实现在 `web/`：真实 MIT-BIH 记录浏览、专家标注心拍选择、已保存 LR/RF/1D-CNN 模型推理、同拍比较和历史片段回放。不会在 Web 工作台中训练模型或更改数据文件。模型推理限定既有 44 条受试者分组记录及 MLII；其他本地完整记录只用于波形浏览。回放是历史数据展示，不是实时监护。

安装/启动、API、模型验证和演示说明见 [`web/docs/phase2_testing.md`](web/docs/phase2_testing.md)、[`web/docs/phase2_api.md`](web/docs/phase2_api.md) 和 [`web/docs/phase2_demo_guide.md`](web/docs/phase2_demo_guide.md)。最终交付记录在 [`web/docs/phase2_final_report.md`](web/docs/phase2_final_report.md)。

## 第三阶段：科研平台与课程答辩

新增 `/dashboard`、`/experiments`、`/generalization`、`/gallery` 和 `/presentation-demo`，统一蓝白医学科研界面，保留 `/ai-detection` 的真实 ECG、三模型推理和历史回放。研究页面只读已有核验指标与图像；模型、原始数据与正式实验结果没有重新训练或改写。

推荐课堂演示采用本地生产构建：

```powershell
npm --prefix web/frontend run build
.venv\Scripts\python.exe -m uvicorn web.backend.production:app --host 127.0.0.1 --port 8002
```

打开 `http://127.0.0.1:8002/presentation-demo`。完整过程、截图、实测性能与依赖残留风险见 [第三阶段交付报告](web/docs/phase3_final_report.md) 和 [答辩指南](web/docs/phase3_demo_guide.md)。该服务只面向本机课程研究教学。

## 第四阶段：浅色医学科技风与交互动画

全站采用白色顶栏和可收起侧栏，增加三级动画设置、系统减少动画支持、Dashboard 联动、真实心拍高亮、三模型动态概率、RAF 历史回放、错误案例跳转和图库键盘浏览。`/ai-inference` 提供单拍检测入口，既有 API 与正式模型结果保留。

启动方式沿用上述生产命令，首页为 `http://127.0.0.1:8002/dashboard`。交付与实际验证见 [第四阶段交付报告](web/docs/phase4_final_report.md)、[动画设计](web/docs/phase4_animation_design.md)、[交互矩阵](web/docs/phase4_interaction_matrix.md)、[性能测量](web/docs/phase4_performance.md) 和 [视觉审查与截图](web/docs/phase4_visual_review.md)。

## 第五阶段：基于设计稿的视觉还原

参考包保存在 `web/design/reference/`。Dashboard 改为四 KPI 与三列分析区，ECG 工作台采用控制/主波形/节拍详情三列及独立回放栏，AI 检测采用单拍/推理结果分区与横向三模型卡。窄屏菜单提供 Tooltip 与完整名称展开，图表增加真实数量、百分比和对数视图。

启动方式不变。五尺寸修改前后截图、设计稿并排对照和实际测试结果见 [第五阶段交付](web/docs/visual_fidelity/final_report.md) 与 [视觉对照](web/docs/visual_fidelity/visual_comparison.md)。
